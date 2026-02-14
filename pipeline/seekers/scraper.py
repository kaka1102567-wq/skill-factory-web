"""Fetch content from documentation URLs."""

import hashlib
import re
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional

from ..clients.web_client import WebClient
from ..core.logger import PipelineLogger
from ..core.errors import SeekersError


@dataclass
class ScrapedPage:
    url: str
    title: str
    content_html: str
    content_text: str
    source_type: str
    scraped_at: str
    content_hash: str
    status: str  # "success" | "failed"
    error: Optional[str] = None


class SeeksScraper:
    def __init__(self, web_client: WebClient, logger: PipelineLogger):
        self.client = web_client
        self.logger = logger

    def scrape_url(self, url: str, source_type: str = "auto") -> ScrapedPage:
        if source_type == "auto":
            source_type = self._detect_type(url)

        try:
            if source_type == "github":
                html = self._fetch_github(url)
            else:
                html = self.client.get(url)

            # Extract title from <title> tag
            import re as _re
            title_match = _re.search(r'<title[^>]*>([^<]+)</title>', html, _re.IGNORECASE)
            title = title_match.group(1).strip() if title_match else url.split('/')[-1]

            # Basic text extraction for content_text
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'lxml')
            text = soup.get_text(separator='\n', strip=True)

            return ScrapedPage(
                url=url, title=title, content_html=html, content_text=text,
                source_type=source_type,
                scraped_at=datetime.now(timezone.utc).isoformat(),
                content_hash=hashlib.sha256(html.encode()).hexdigest()[:16],
                status="success",
            )
        except Exception as e:
            return ScrapedPage(
                url=url, title="", content_html="", content_text="",
                source_type=source_type,
                scraped_at=datetime.now(timezone.utc).isoformat(),
                content_hash="", status="failed", error=str(e),
            )

    def scrape_batch(self, sources: list[dict]) -> list[ScrapedPage]:
        results = []
        for src in sources:
            url = src.get("url", "")
            stype = src.get("type", "documentation")
            self.logger.debug(f"Scraping {url}...")
            results.append(self.scrape_url(url, stype))
        return results

    def _detect_type(self, url: str) -> str:
        if "github.com" in url:
            return "github"
        if "developers.facebook.com" in url:
            return "api_docs"
        if "business/help" in url:
            return "help_center"
        return "html"

    def _fetch_github(self, url: str) -> str:
        """Convert GitHub blob URL to raw content URL."""
        raw_url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
        return self.client.get(raw_url)
