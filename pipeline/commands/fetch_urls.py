"""CLI command: fetch-urls — Fetch URLs and convert to Markdown files for pipeline input.

Usage: cli.py fetch-urls --urls "url1,url2" --output-dir ./input
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

from bs4 import BeautifulSoup

# Content selectors in priority order for finding main content
CONTENT_SELECTORS = [
    'article',
    '[role="main"]',
    'main',
    '.post-content',
    '.article-body',
    '.entry-content',
    '#content',
    '.content',
]

# Elements to always remove before extraction
REMOVE_SELECTORS = [
    'nav', 'header', 'footer',
    '.sidebar', '.advertisement', '.ads',
    '.cookie-banner', '.popup',
    'script', 'style', 'noscript',
    '.social-share', '.comments',
]

MAX_CONTENT_LENGTH = 50_000


def _log(level: str, message: str) -> None:
    """Print JSON log line to stdout."""
    print(json.dumps({
        "event": "log", "level": level,
        "phase": "fetch", "message": message,
    }, ensure_ascii=False), flush=True)


def _parse_urls(urls_str: str) -> list[str]:
    """Parse comma-separated or newline-separated URLs, validate each."""
    raw = re.split(r'[,\n]+', urls_str)
    valid = []
    for u in raw:
        u = u.strip()
        if not u:
            continue
        if not u.startswith(('http://', 'https://')):
            _log("warn", f"Skipping invalid URL (no http/https): {u}")
            continue
        try:
            parsed = urlparse(u)
            if not parsed.netloc:
                _log("warn", f"Skipping invalid URL (no domain): {u}")
                continue
        except Exception:
            _log("warn", f"Skipping unparseable URL: {u}")
            continue
        valid.append(u)
    return valid


def _extract_title(soup: BeautifulSoup) -> str:
    """Extract page title from HTML."""
    # Try <title> tag
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    # Try <h1>
    h1 = soup.find('h1')
    if h1:
        return h1.get_text(strip=True)
    return "Untitled"


def _find_main_content(soup: BeautifulSoup) -> BeautifulSoup:
    """Find main content element using priority selectors."""
    for selector in CONTENT_SELECTORS:
        el = soup.select_one(selector)
        if el:
            return el
    return soup.body or soup


def _remove_noise(soup: BeautifulSoup) -> None:
    """Remove navigation, ads, scripts, etc."""
    for selector in REMOVE_SELECTORS:
        for el in soup.select(selector):
            el.decompose()


def _html_to_markdown(element) -> str:
    """Convert HTML element to Markdown text."""
    lines = []
    _walk_element(element, lines)
    text = '\n'.join(lines)
    # Clean up excessive blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _walk_element(el, lines: list, depth: int = 0) -> None:
    """Recursively walk HTML elements and convert to Markdown."""
    from bs4 import NavigableString, Tag

    if isinstance(el, NavigableString):
        text = str(el).strip()
        if text:
            lines.append(text)
        return

    if not isinstance(el, Tag):
        return

    tag = el.name

    # Headings
    if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
        level = int(tag[1])
        text = el.get_text(strip=True)
        if text:
            lines.append('')
            lines.append(f"{'#' * level} {text}")
            lines.append('')
        return

    # Paragraphs
    if tag == 'p':
        text = _inline_to_md(el)
        if text:
            lines.append('')
            lines.append(text)
            lines.append('')
        return

    # Lists
    if tag in ('ul', 'ol'):
        lines.append('')
        for i, li in enumerate(el.find_all('li', recursive=False)):
            prefix = f"{i + 1}." if tag == 'ol' else "-"
            text = _inline_to_md(li)
            if text:
                lines.append(f"{prefix} {text}")
        lines.append('')
        return

    # Code blocks
    if tag == 'pre':
        code = el.find('code')
        text = (code or el).get_text()
        lines.append('')
        lines.append('```')
        lines.append(text.strip())
        lines.append('```')
        lines.append('')
        return

    # Tables
    if tag == 'table':
        _table_to_md(el, lines)
        return

    # Images
    if tag == 'img':
        alt = el.get('alt', '')
        src = el.get('src', '')
        if alt or src:
            lines.append(f"![{alt}]({src})")
        return

    # Blockquote
    if tag == 'blockquote':
        text = el.get_text(strip=True)
        if text:
            lines.append('')
            for bq_line in text.split('\n'):
                lines.append(f"> {bq_line}")
            lines.append('')
        return

    # Recurse into other elements
    for child in el.children:
        _walk_element(child, lines, depth + 1)


def _inline_to_md(el) -> str:
    """Convert inline HTML to Markdown (bold, italic, links, code)."""
    from bs4 import NavigableString, Tag

    parts = []
    for child in el.children:
        if isinstance(child, NavigableString):
            parts.append(str(child))
        elif isinstance(child, Tag):
            text = child.get_text(strip=True)
            if child.name in ('strong', 'b'):
                parts.append(f"**{text}**")
            elif child.name in ('em', 'i'):
                parts.append(f"*{text}*")
            elif child.name == 'code':
                parts.append(f"`{text}`")
            elif child.name == 'a':
                href = child.get('href', '')
                parts.append(f"[{text}]({href})")
            elif child.name == 'br':
                parts.append('\n')
            else:
                parts.append(text)
    return ' '.join(parts).strip()


def _table_to_md(table, lines: list) -> None:
    """Convert HTML table to Markdown table."""
    rows = table.find_all('tr')
    if not rows:
        return

    lines.append('')
    for i, row in enumerate(rows):
        cells = row.find_all(['th', 'td'])
        cell_texts = [c.get_text(strip=True).replace('|', '\\|') for c in cells]
        lines.append('| ' + ' | '.join(cell_texts) + ' |')
        if i == 0:
            lines.append('| ' + ' | '.join(['---'] * len(cell_texts)) + ' |')
    lines.append('')


def fetch_and_convert(url: str, web_client) -> tuple[str | None, str | None]:
    """Fetch a URL and convert its HTML to Markdown.

    Returns (markdown_content, title) or (None, None) on failure.
    """
    try:
        html = web_client.get(url)
    except Exception as e:
        _log("warn", f"Failed to fetch {url}: {e}")
        return None, None

    soup = BeautifulSoup(html, 'lxml')
    title = _extract_title(soup)
    _remove_noise(soup)
    main_el = _find_main_content(soup)
    content = _html_to_markdown(main_el)

    # Truncate if too long
    if len(content) > MAX_CONTENT_LENGTH:
        content = content[:MAX_CONTENT_LENGTH] + "\n\n*[Content truncated]*"

    if not content or len(content) < 50:
        _log("warn", f"Extracted content too short for {url}")
        return None, None

    return content, title


def run_fetch_urls(urls_str: str, output_dir: str) -> int:
    """Main entry point for the fetch-urls command.

    Returns exit code: 0 on success (even partial), 1 on total failure.
    """
    from pipeline.clients.web_client import WebClient

    urls = _parse_urls(urls_str)
    if not urls:
        _log("error", "No valid URLs provided")
        return 1

    os.makedirs(output_dir, exist_ok=True)
    _log("info", f"Fetching {len(urls)} URLs...")

    client = WebClient(rpm=10, timeout=30)
    created_files = []

    try:
        for i, url in enumerate(urls):
            _log("info", f"Fetching {i + 1}/{len(urls)}: {url}")
            content, title = fetch_and_convert(url, client)
            if content is None:
                continue

            # Build output filename: url_001_<domain>.md
            domain = urlparse(url).netloc.replace('www.', '').split('.')[0]
            filename = f"url_{i + 1:03d}_{domain}.md"
            filepath = os.path.join(output_dir, filename)

            # Add YAML frontmatter
            now = datetime.now(timezone.utc).isoformat()
            output = f"""---
source_url: {url}
fetched_at: {now}
title: "{title}"
---

# {title}

{content}
"""
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(output)

            created_files.append(filepath)
            _log("info", f"Saved {filename} ({len(content)} chars)")
    finally:
        client.close()

    if created_files:
        _log("info", f"Fetched {len(created_files)}/{len(urls)} URLs successfully")
        # Print result as JSON for build-runner to parse
        print(json.dumps({
            "event": "fetch-urls-done",
            "files": created_files,
            "total": len(urls),
            "success": len(created_files),
        }, ensure_ascii=False), flush=True)
        return 0
    else:
        _log("error", "All URL fetches failed")
        return 1
