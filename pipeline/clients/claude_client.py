"""Claude API wrapper with retry, cost tracking, and JSON response parsing."""

import json
import re
import time
import hashlib
import os
from typing import Optional

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from ..core.logger import PipelineLogger
from ..core.errors import ClaudeAPIError


class ClaudeClient:
    PRICING = {
        "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
        "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.0},
    }

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514",
                 logger: Optional[PipelineLogger] = None, cache_dir: Optional[str] = None):
        if not api_key:
            raise ClaudeAPIError("CLAUDE_API_KEY not set", retryable=False)
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.logger = logger or PipelineLogger()
        self.cache_dir = cache_dir  # Optional response cache

        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost_usd = 0.0
        self.call_count = 0

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

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception_type((anthropic.RateLimitError, anthropic.APIStatusError)),
    )
    def call(self, system: str, user: str, max_tokens: int = 4096,
             temperature: float = 0.0, phase: str = None) -> str:
        """Call Claude API. Returns response text."""
        # Check cache
        cache_key = self._cache_key(system, user)
        cached = self._get_cached(cache_key)
        if cached:
            self.logger.debug(f"Cache hit: {cache_key}", phase=phase)
            return cached

        start = time.time()
        try:
            response = self.client.messages.create(
                model=self.model, max_tokens=max_tokens,
                temperature=temperature, system=system,
                messages=[{"role": "user", "content": user}],
            )
        except anthropic.RateLimitError:
            self.logger.warn("Rate limited, retrying...", phase=phase)
            raise
        except anthropic.APIStatusError as e:
            if e.status_code >= 500:
                self.logger.warn(f"Server error ({e.status_code}), retrying...", phase=phase)
                raise
            raise ClaudeAPIError(str(e), status_code=e.status_code, retryable=False)

        # Track cost
        inp_tok = response.usage.input_tokens
        out_tok = response.usage.output_tokens
        self.total_input_tokens += inp_tok
        self.total_output_tokens += out_tok
        pricing = self.PRICING.get(self.model, {"input": 3.0, "output": 15.0})
        cost = (inp_tok * pricing["input"] + out_tok * pricing["output"]) / 1_000_000
        self.total_cost_usd += cost
        self.call_count += 1

        self.logger.debug(
            f"API #{self.call_count}: {inp_tok}+{out_tok} tok, ${cost:.4f}, {time.time()-start:.1f}s",
            phase=phase)
        self.logger.report_cost(self.total_cost_usd, self.total_input_tokens + self.total_output_tokens)

        text = response.content[0].text
        self._set_cache(cache_key, text)
        return text

    def call_json(self, system: str, user: str, max_tokens: int = 4096,
                  phase: str = None) -> dict | list:
        """Call Claude expecting JSON. Strips code fences, retries on parse failure."""
        raw = self.call(system, user, max_tokens=max_tokens, temperature=0.0, phase=phase)
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
            # Fallback: extract JSON from mixed content
            match = re.search(r'[\[{].*[\]}]', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            raise ClaudeAPIError(f"Non-JSON response: {text[:200]}...", retryable=True)

    def get_cost_summary(self) -> dict:
        return {
            "calls": self.call_count,
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "cost_usd": round(self.total_cost_usd, 4),
        }
