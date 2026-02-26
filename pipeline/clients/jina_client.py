"""HTTP client wrapper for Jina Reader API — convert URLs to clean Markdown."""

import re
import time

import httpx

# Jina API endpoints
JINA_READER_BASE = "https://r.jina.ai/"
JINA_SEARCH_BASE = "https://s.jina.ai/"

# Default headers: strip nav/footer/ads, skip images
DEFAULT_HEADERS = {
    "Accept": "text/plain",
    "X-No-Cache": "false",
    "X-Remove-Selector": "nav,footer,.sidebar,.ads,.cookie-banner,.popup,.social-share",
    "X-Retain-Images": "none",
}

# Rate limits: free ~85 RPM, paid ~400 RPM
FREE_MIN_INTERVAL = 0.7
PAID_MIN_INTERVAL = 0.15


def _parse_search_results(text: str, max_results: int = 5) -> list[dict]:
    """Parse Jina search response (Markdown format) into structured results."""
    blocks = re.split(r"\n(?=Title:\s)", text)
    results = []
    for block in blocks[:max_results]:
        title_m = re.search(r"^Title:\s*(.+)$", block, re.MULTILINE)
        url_m = re.search(r"^URL Source:\s*(.+)$", block, re.MULTILINE)
        content_m = re.search(r"Markdown Content:\s*\n(.*)", block, re.DOTALL)
        if not title_m or not url_m:
            continue
        content = content_m.group(1).strip() if content_m else ""
        results.append({
            "url": url_m.group(1).strip(),
            "title": title_m.group(1).strip(),
            "snippet": content[:200],
            "content": content,
        })
    return results


class JinaClient:
    """Rate-limited client for Jina Reader (URL→Markdown) and Search APIs."""

    def __init__(self, api_key: str = "", timeout: int = 30, max_retries: int = 2):
        self.max_retries = max_retries
        self._last = 0.0

        # Auth header + interval based on API key presence
        headers = {**DEFAULT_HEADERS}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
            self.min_interval = PAID_MIN_INTERVAL
        else:
            self.min_interval = FREE_MIN_INTERVAL

        self._client = httpx.Client(
            timeout=timeout,
            headers=headers,
            follow_redirects=True,
        )

    def _rate_limit(self):
        """Sleep if not enough time has passed since last request."""
        elapsed = time.time() - self._last
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)

    def fetch(self, url: str, target_selector: str = "") -> str | None:
        """Fetch URL content as Markdown via Jina Reader. Returns None on failure."""
        req_url = JINA_READER_BASE + url
        extra_headers = {}
        if target_selector:
            extra_headers["X-Target-Selector"] = target_selector

        for attempt in range(self.max_retries + 1):
            self._rate_limit()
            try:
                r = self._client.get(req_url, headers=extra_headers)
                self._last = time.time()

                if r.status_code == 200:
                    return r.text if len(r.text) > 50 else None
                if r.status_code == 429:
                    time.sleep(min(5 * (attempt + 1), 30))
                    continue
                if r.status_code >= 500:
                    time.sleep(2 * (attempt + 1))
                    continue
                # 4xx (not 429) → give up
                return None
            except (httpx.TimeoutException, httpx.ConnectError):
                continue
            except httpx.RequestError:
                break

        return None

    def search(self, query: str, max_results: int = 5) -> list[dict]:
        """Search via Jina Search API. Returns list of {url, title, snippet, content}."""
        req_url = JINA_SEARCH_BASE + query.replace(" ", "+")
        self._rate_limit()
        try:
            r = self._client.get(req_url)
            self._last = time.time()
            r.raise_for_status()
            return _parse_search_results(r.text, max_results)
        except httpx.HTTPError:
            return []

    def close(self):
        self._client.close()
