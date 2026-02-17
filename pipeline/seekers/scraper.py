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


# ── Smart Crawl (for auto-discovery) ─────────────────────


_MAX_CONTENT_CHARS = 50_000


def smart_crawl(ranked_urls, output_dir, web_client, logger, parser=None):
    """Crawl ranked URLs with fallback strategies.

    Per URL: direct fetch → Google Cache → Wayback Machine.
    Saves successful results as references/*.md files.
    Returns list of dicts: {path, url, word_count, status}.
    """
    import os
    refs_dir = os.path.join(output_dir, "references")
    os.makedirs(refs_dir, exist_ok=True)

    results = []
    for i, ranked in enumerate(ranked_urls):
        logger.info(f"Crawling [{i + 1}/{len(ranked_urls)}]: {ranked.url}", phase="discovery")

        content = None
        title = ranked.title or ""

        # Strategy 1: Direct fetch
        try:
            content, title = _fetch_and_parse(ranked.url, web_client)
        except Exception:
            pass

        # Strategy 2: Google Cache
        if not content or len(content.strip()) < 200:
            try:
                cache_url = (
                    "https://webcache.googleusercontent.com/search?q=cache:"
                    + ranked.url
                )
                content, _ = _fetch_and_parse(cache_url, web_client)
            except Exception:
                pass

        # Strategy 3: Wayback Machine
        if not content or len(content.strip()) < 200:
            try:
                wb_url = f"https://web.archive.org/web/2024/{ranked.url}"
                content, _ = _fetch_and_parse(wb_url, web_client)
            except Exception:
                pass

        if content and len(content.strip()) >= 200:
            filename = _url_to_safe_filename(ranked.url)
            filepath = os.path.join(refs_dir, f"{filename}.md")
            header = f"# {title}\n\n> Source: {ranked.url}\n\n---\n\n"
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(header + content[:_MAX_CONTENT_CHARS])
            word_count = len(content.split())
            results.append({
                "path": filepath, "url": ranked.url,
                "word_count": word_count, "status": "success",
            })
        else:
            logger.warn(f"All strategies failed: {ranked.url}", phase="discovery")
            results.append({"url": ranked.url, "status": "failed"})

    ok = sum(1 for r in results if r.get("status") == "success")
    logger.info(f"Crawled {ok}/{len(ranked_urls)} successfully", phase="discovery")
    return results


def _fetch_and_parse(url, web_client):
    """Fetch URL and extract text content. Returns (content, title)."""
    html = web_client.get(url)

    title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.DOTALL)
    title = title_match.group(1).strip() if title_match else ""

    # Remove non-content tags
    cleaned = re.sub(
        r'<(script|style|nav|footer|header)[^>]*>.*?</\1>',
        '', html, flags=re.DOTALL | re.IGNORECASE,
    )
    text = re.sub(r'<[^>]+>', '\n', cleaned)
    text = re.sub(r'\n{3,}', '\n\n', text).strip()

    return text, title


def _url_to_safe_filename(url):
    """Convert URL to a safe, short filename."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    path = parsed.path.strip("/").replace("/", "-")
    name = re.sub(r'[^a-zA-Z0-9\-]', '', path)
    return name[:80] or "page"
