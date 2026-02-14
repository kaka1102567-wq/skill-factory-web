"""Rate-limited HTTP client for scraping documentation."""

import time
import httpx
from ..core.errors import SeekersError


class WebClient:
    def __init__(self, rpm: int = 10, timeout: int = 30):
        self.min_interval = 60.0 / rpm
        self._last = 0.0
        self._client = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": "SkillFactory/1.0 (knowledge-base-builder)"},
            follow_redirects=True,
        )

    def get(self, url: str) -> str:
        elapsed = time.time() - self._last
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        try:
            r = self._client.get(url)
            self._last = time.time()
            r.raise_for_status()
            return r.text
        except httpx.HTTPStatusError as e:
            raise SeekersError(f"HTTP {e.response.status_code}: {url}")
        except httpx.RequestError as e:
            raise SeekersError(f"Request failed: {url} — {e}")

    def get_batch(self, urls: list[str]) -> dict[str, str | None]:
        results = {}
        for url in urls:
            try:
                results[url] = self.get(url)
            except SeekersError:
                results[url] = None
        return results

    def close(self):
        self._client.close()
