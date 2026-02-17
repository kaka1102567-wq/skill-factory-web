"""URL Discoverer — finds documentation URLs via DuckDuckGo HTML, sitemap, and link crawl."""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse, quote_plus, unquote, parse_qs

from ..core.errors import SeekersError


@dataclass
class CandidateURL:
    url: str
    title: str = ""
    description: str = ""
    source: str = ""  # "search" | "sitemap" | "crawl"


# URLs that are clearly not documentation
_EXCLUDE_PATTERNS = [
    "/login", "/signup", "/register", "/cart", "/checkout",
    "/search?", "/tag/", "#comment", "/privacy", "/terms",
    "/cookie", "accounts.google", "facebook.com/login",
    ".pdf", ".zip", ".exe", "youtube.com", "twitter.com",
]


def discover_urls(analysis, web_client, logger, max_candidates=100) -> list[CandidateURL]:
    """Find URLs from 3 sources: DuckDuckGo, sitemaps, and link crawl.

    Uses synchronous WebClient. Deduplicates by normalized URL.
    """
    candidates = []

    # Strategy 1: DuckDuckGo HTML search
    for query in analysis.search_queries[:6]:
        try:
            results = _search_duckduckgo(query, web_client)
            candidates.extend(results)
            logger.info(f"DDG search '{query}': {len(results)} results", phase="discovery")
        except Exception as e:
            logger.warn(f"DDG search failed for '{query}': {e}", phase="discovery")

    # Strategy 2: Sitemap crawl
    for site in analysis.official_sites[:3]:
        try:
            sitemap_urls = _parse_sitemap(site, web_client, analysis.doc_patterns)
            candidates.extend(sitemap_urls)
            logger.info(f"Sitemap {site}: {len(sitemap_urls)} URLs", phase="discovery")
        except Exception as e:
            logger.warn(f"Sitemap failed for {site}: {e}", phase="discovery")

    # Strategy 3: Landing page link crawl
    for site in analysis.official_sites[:2]:
        try:
            linked = _crawl_links(site, web_client, analysis.doc_patterns)
            candidates.extend(linked)
            logger.info(f"Link crawl {site}: {len(linked)} URLs", phase="discovery")
        except Exception as e:
            logger.warn(f"Link crawl failed for {site}: {e}", phase="discovery")

    # Deduplicate
    seen = set()
    unique = []
    for c in candidates:
        normalized = _normalize_url(c.url)
        if normalized not in seen:
            seen.add(normalized)
            unique.append(c)

    logger.info(f"Total unique candidates: {len(unique)}", phase="discovery")
    return unique[:max_candidates]


def _search_duckduckgo(query: str, web_client) -> list[CandidateURL]:
    """GET DuckDuckGo HTML search (no API key needed)."""
    encoded_query = quote_plus(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

    try:
        html = web_client.get(url)
    except SeekersError:
        return []

    results = []
    link_pattern = re.compile(
        r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>', re.DOTALL,
    )
    snippet_pattern = re.compile(
        r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>', re.DOTALL,
    )

    links = link_pattern.findall(html)
    snippets = snippet_pattern.findall(html)

    for i, (href, title) in enumerate(links[:15]):
        actual_url = _extract_ddg_url(href)
        if actual_url and _is_valid_doc_url(actual_url):
            snippet = snippets[i] if i < len(snippets) else ""
            results.append(CandidateURL(
                url=actual_url,
                title=re.sub(r'<[^>]+>', '', title).strip(),
                description=re.sub(r'<[^>]+>', '', snippet).strip(),
                source="search",
            ))

    return results


def _extract_ddg_url(href: str) -> str:
    """Extract actual URL from DuckDuckGo redirect."""
    if "uddg=" in href:
        parsed = urlparse(href)
        params = parse_qs(parsed.query)
        if "uddg" in params:
            return unquote(params["uddg"][0])
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        return "https:" + href
    return ""


def _parse_sitemap(base_url: str, web_client, patterns: list[str]) -> list[CandidateURL]:
    """Parse sitemap.xml, falling back to robots.txt Sitemap: directive."""
    sitemap_url = urljoin(base_url.rstrip("/") + "/", "sitemap.xml")

    try:
        xml_text = web_client.get(sitemap_url)
    except SeekersError:
        # Try robots.txt
        try:
            robots_url = urljoin(base_url.rstrip("/") + "/", "robots.txt")
            robots_text = web_client.get(robots_url)
            sitemap_url = None
            for line in robots_text.splitlines():
                if line.strip().lower().startswith("sitemap:"):
                    sitemap_url = line.split(":", 1)[1].strip()
                    break
            if not sitemap_url:
                return []
            xml_text = web_client.get(sitemap_url)
        except SeekersError:
            return []

    results = []
    try:
        root = ET.fromstring(xml_text)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

        # Check sitemap index (one level deep)
        for sitemap_loc in root.findall(".//sm:sitemap/sm:loc", ns):
            try:
                sub_xml = web_client.get(sitemap_loc.text)
                sub_root = ET.fromstring(sub_xml)
                for url_elem in sub_root.findall(".//sm:url/sm:loc", ns):
                    if _matches_patterns(url_elem.text, patterns):
                        results.append(CandidateURL(url=url_elem.text, source="sitemap"))
            except (SeekersError, ET.ParseError):
                pass

        # Regular sitemap URLs
        for url_elem in root.findall(".//sm:url/sm:loc", ns):
            if _matches_patterns(url_elem.text, patterns):
                results.append(CandidateURL(url=url_elem.text, source="sitemap"))
    except ET.ParseError:
        pass

    return results[:50]


def _crawl_links(base_url: str, web_client, patterns: list[str]) -> list[CandidateURL]:
    """Crawl landing page for internal links matching doc patterns (1 level only)."""
    try:
        html = web_client.get(base_url)
    except SeekersError:
        return []

    results = []
    parsed_base = urlparse(base_url)
    link_pattern = re.compile(r'<a[^>]*href="([^"]*)"[^>]*>', re.DOTALL)

    for href in link_pattern.findall(html):
        if href.startswith("#") or href.startswith("mailto:"):
            continue
        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)
        if parsed.netloc == parsed_base.netloc and _matches_patterns(full_url, patterns):
            results.append(CandidateURL(url=full_url, source="crawl"))

    return results[:30]


def _matches_patterns(url: str, patterns: list[str]) -> bool:
    """Check if URL matches any doc pattern. Empty patterns = match all."""
    if not patterns:
        return True
    return any(p in url for p in patterns)


def _normalize_url(url: str) -> str:
    """Normalize URL for deduplication."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}{path}".lower()


def _is_valid_doc_url(url: str) -> bool:
    """Filter out non-documentation URLs."""
    return not any(x in url.lower() for x in _EXCLUDE_PATTERNS)
