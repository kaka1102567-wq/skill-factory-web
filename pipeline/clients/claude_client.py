"""Claude API wrapper with retry, cost tracking, and JSON response parsing.

Supports dual SDK: OpenAI-compatible format for custom providers (e.g. Claudible),
Anthropic SDK for direct Anthropic API access.
"""

import json
import re
import time
import hashlib
import os
import unicodedata
from typing import Optional

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from ..core.logger import PipelineLogger
from ..core.errors import ClaudeAPIError

# Import both SDKs — availability determines which format is used
_RETRYABLE_EXCEPTIONS = []

try:
    import anthropic
    _RETRYABLE_EXCEPTIONS.extend([anthropic.RateLimitError, anthropic.APIStatusError])
    HAS_ANTHROPIC = True
except ImportError:
    anthropic = None
    HAS_ANTHROPIC = False

try:
    import openai as _openai_mod
    from openai import OpenAI
    _RETRYABLE_EXCEPTIONS.extend([_openai_mod.RateLimitError, _openai_mod.APIStatusError])
    HAS_OPENAI = True
except ImportError:
    _openai_mod = None
    OpenAI = None
    HAS_OPENAI = False

_RETRYABLE_EXCEPTIONS = tuple(_RETRYABLE_EXCEPTIONS) if _RETRYABLE_EXCEPTIONS else (ConnectionError,)


class CreditExhaustedError(Exception):
    """Raised when API credits are depleted — stops pipeline immediately."""
    pass


class ClaudeClient:
    PRICING = {
        "claude-sonnet-4-5-20250929": {"input": 3.0, "output": 15.0},
        "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
        "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.0},
    }

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5-20250929",
                 model_light: Optional[str] = None, base_url: Optional[str] = None,
                 logger: Optional[PipelineLogger] = None, cache_dir: Optional[str] = None):
        if not api_key:
            raise ClaudeAPIError("CLAUDE_API_KEY not set", retryable=False)

        self.model = model
        self.model_light = model_light or model
        self.base_url = base_url
        self.logger = logger or PipelineLogger()
        self.cache_dir = cache_dir

        # Choose SDK based on base_url
        if base_url:
            if not HAS_OPENAI:
                raise ImportError(
                    "openai package required for custom base_url. "
                    "Run: pip install openai"
                )
            api_base = base_url.rstrip("/")
            if not api_base.endswith("/v1"):
                api_base = api_base + "/v1"
            self.client = OpenAI(api_key=api_key, base_url=api_base)
            self._use_openai_format = True
        else:
            if not HAS_ANTHROPIC:
                raise ImportError(
                    "anthropic package required. Run: pip install anthropic"
                )
            self.client = anthropic.Anthropic(api_key=api_key)
            self._use_openai_format = False

        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost_usd = 0.0
        self.call_count = 0
        self._consecutive_credit_errors = 0
        self._MAX_CREDIT_ERRORS = 3

    def _sanitize_api_text(self, text: str) -> str:
        """Last-resort text cleaning before sending to API.

        Removes characters known to cause 500 errors on proxies
        (null, BOM, control chars, surrogates, PUA, non-BMP).
        """
        if not text:
            return ""

        # UTF-8 roundtrip
        text = text.encode("utf-8", errors="replace").decode("utf-8", errors="replace")

        # NFC normalize (Vietnamese combining diacritics)
        text = unicodedata.normalize("NFC", text)

        # Remove dangerous chars
        text = text.replace("\x00", "")
        text = text.replace("\ufeff", "")
        text = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)
        text = re.sub(r"[\ud800-\udfff]", "", text)
        text = re.sub(r"[\ue000-\uf8ff]", "", text)
        text = re.sub(r"[\ufffd-\uffff]", "", text)

        # Remove non-BMP
        text = re.sub(r"[\U00010000-\U0010FFFF]", "", text)

        return text

    def _cache_key(self, system: str, user: str) -> str:
        return hashlib.sha256((system + user).encode()).hexdigest()[:16]

    def _get_cached(self, key: str) -> Optional[str]:
        if not self.cache_dir:
            return None
        path = os.path.join(self.cache_dir, f"claude_{key}.json")
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f).get("response")
        return None

    def _set_cache(self, key: str, response: str) -> None:
        if not self.cache_dir:
            return
        os.makedirs(self.cache_dir, exist_ok=True)
        path = os.path.join(self.cache_dir, f"claude_{key}.json")
        with open(path, 'w') as f:
            json.dump({"response": response}, f)

    def _check_credit_error(self, error: Exception, phase: str = None) -> None:
        """Detect credit/billing errors and raise CreditExhaustedError after threshold."""
        error_msg = str(error).lower()
        credit_phrases = [
            "credit balance is too low",
            "insufficient_quota",
            "insufficient credits",
            "payment required",
            "billing hard limit",
            "quota exceeded",
        ]
        if any(phrase in error_msg for phrase in credit_phrases):
            self._consecutive_credit_errors += 1
            self.logger.warn(
                f"Credit error ({self._consecutive_credit_errors}/{self._MAX_CREDIT_ERRORS}): {error}",
                phase=phase,
            )
            if self._consecutive_credit_errors >= self._MAX_CREDIT_ERRORS:
                raise CreditExhaustedError(
                    f"API credits exhausted after {self._consecutive_credit_errors} "
                    f"consecutive failures. Add credits and retry."
                )

    def _call_api(self, system: str, user: str, max_tokens: int,
                  temperature: float, active_model: str) -> tuple:
        """Internal: call API using the appropriate SDK format.

        Returns (text, input_tokens, output_tokens).
        """
        if self._use_openai_format:
            response = self.client.chat.completions.create(
                model=active_model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            text = response.choices[0].message.content
            inp_tok = getattr(response.usage, 'prompt_tokens', 0) or 0
            out_tok = getattr(response.usage, 'completion_tokens', 0) or 0
        else:
            response = self.client.messages.create(
                model=active_model, max_tokens=max_tokens,
                temperature=temperature, system=system,
                messages=[{"role": "user", "content": user}],
            )
            text = response.content[0].text
            inp_tok = response.usage.input_tokens
            out_tok = response.usage.output_tokens
        return text, inp_tok, out_tok

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=4, max=120),
        retry=retry_if_exception_type(_RETRYABLE_EXCEPTIONS),
    )
    def call(self, system: str, user: str, max_tokens: int = 4096,
             temperature: float = 0.0, phase: str = None,
             use_light_model: bool = False) -> str:
        """Call Claude API. Returns response text.

        use_light_model=True uses self.model_light (e.g. Haiku — cheaper).
        """
        # Sanitize text before cache key and API call
        system = self._sanitize_api_text(system)
        user = self._sanitize_api_text(user)

        # Check cache
        cache_key = self._cache_key(system, user)
        cached = self._get_cached(cache_key)
        if cached:
            self.logger.debug(f"Cache hit: {cache_key}", phase=phase)
            return cached

        active_model = self.model_light if use_light_model else self.model

        start = time.time()
        try:
            text, inp_tok, out_tok = self._call_api(
                system, user, max_tokens, temperature, active_model
            )
        except Exception as e:
            is_rate_limit = (
                (HAS_ANTHROPIC and isinstance(e, anthropic.RateLimitError))
                or (HAS_OPENAI and isinstance(e, _openai_mod.RateLimitError))
            )
            if is_rate_limit:
                self.logger.warn("Rate limited, retrying...", phase=phase)
                raise

            is_api_error = (
                (HAS_ANTHROPIC and isinstance(e, anthropic.APIStatusError))
                or (HAS_OPENAI and isinstance(e, _openai_mod.APIStatusError))
            )
            if is_api_error:
                self._check_credit_error(e, phase)
                status_code = getattr(e, 'status_code', 0)
                if status_code >= 500:
                    self.logger.warn(f"Server error ({status_code}), retrying...", phase=phase)
                    raise
                raise ClaudeAPIError(str(e), status_code=status_code, retryable=False)

            raise

        # Reset credit error counter on success
        self._consecutive_credit_errors = 0

        # Track cost
        self.total_input_tokens += inp_tok
        self.total_output_tokens += out_tok
        pricing = self.PRICING.get(active_model, {"input": 3.0, "output": 15.0})
        cost = (inp_tok * pricing["input"] + out_tok * pricing["output"]) / 1_000_000
        self.total_cost_usd += cost
        self.call_count += 1

        self.logger.debug(
            f"API #{self.call_count} [{active_model.split('-')[1]}]: "
            f"{inp_tok}+{out_tok} tok, ${cost:.4f}, {time.time()-start:.1f}s",
            phase=phase)
        self.logger.report_cost(self.total_cost_usd, self.total_input_tokens + self.total_output_tokens)

        self._set_cache(cache_key, text)
        return text

    def call_json(self, system: str, user: str, max_tokens: int = 4096,
                  phase: str = None, use_light_model: bool = False) -> dict | list:
        """Call Claude expecting JSON. Strips code fences, retries on parse failure."""
        raw = self.call(system, user, max_tokens=max_tokens, temperature=0.0,
                        phase=phase, use_light_model=use_light_model)
        text = raw.strip()

        # Strip ```json ... ```
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Fallback 1: extract JSON from mixed content
            match = re.search(r'[\[{].*[\]}]', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass

            # Fallback 2: repair truncated JSON (missing closing brackets)
            repaired = self._repair_truncated_json(text)
            if repaired is not None:
                self.logger.warn("Repaired truncated JSON response", phase=phase)
                return repaired

            raise ClaudeAPIError(f"Non-JSON response: {text[:200]}...", retryable=True)

    @staticmethod
    def _repair_truncated_json(text: str) -> dict | list | None:
        """Attempt to repair JSON truncated by max_tokens limit.

        Handles cases like: {"topics": [{"topic": "A"}, {"topic": "B"
        by closing open strings, arrays, and objects.
        """
        # Find the JSON start
        start = -1
        for i, ch in enumerate(text):
            if ch in ('{', '['):
                start = i
                break
        if start < 0:
            return None

        fragment = text[start:]

        # Track bracket depth to know what's missing
        in_string = False
        escape_next = False
        stack = []

        for ch in fragment:
            if escape_next:
                escape_next = False
                continue
            if ch == '\\' and in_string:
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch in ('{', '['):
                stack.append('}' if ch == '{' else ']')
            elif ch in ('}', ']'):
                if stack and stack[-1] == ch:
                    stack.pop()

        if not stack:
            return None  # Not truncated or not repairable

        # Trim trailing incomplete key/value (e.g. `"topic": "incompl`)
        trimmed = fragment.rstrip()
        if in_string:
            trimmed += '"'

        # Remove trailing comma or colon for valid JSON
        trimmed = re.sub(r'[,:\s]+$', '', trimmed)

        # Close all open brackets
        closing = ''.join(reversed(stack))
        candidate = trimmed + closing

        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            return None

    def get_cost_summary(self) -> dict:
        return {
            "calls": self.call_count,
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "cost_usd": round(self.total_cost_usd, 4),
        }
