"""Parse HTML/Markdown into structured BaselineEntry objects."""

import re
import hashlib
from datetime import datetime, timezone
from bs4 import BeautifulSoup

from ..core.types import BaselineEntry


# Vietnamese + English stop words
STOP_WORDS = frozenset({
    'là', 'và', 'của', 'các', 'có', 'được', 'cho', 'trong', 'với', 'này', 'một', 'để',
    'không', 'khi', 'thì', 'từ', 'đã', 'sẽ', 'như', 'nhưng', 'cũng', 'về', 'theo',
    'the', 'a', 'an', 'and', 'or', 'is', 'in', 'to', 'for', 'of', 'with', 'on', 'at',
    'by', 'this', 'that', 'it', 'be', 'as', 'are', 'was', 'were', 'been', 'has', 'have',
})


class SeekersParser:

    def parse_html(self, html: str, url: str, source_type: str) -> list[BaselineEntry]:
        soup = BeautifulSoup(html, 'lxml')
        for tag in soup.find_all(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            tag.decompose()

        main = soup.find('main') or soup.find('article') or soup.find('div', class_=re.compile(r'content|body|main'))
        if not main:
            main = soup.body or soup

        sections = self._split_by_headings(main, url)
        entries = []
        for sec in sections:
            if len(sec['content'].strip()) < 50:
                continue
            entry_id = hashlib.md5((url + sec['title']).encode()).hexdigest()[:10]
            entries.append(BaselineEntry(
                id=f"bl_{entry_id}",
                title=sec['title'],
                content=sec['content'],
                source_url=url,
                source_type=source_type,
                section_path=sec['path'],
                keywords=self._extract_keywords(sec['content']),
                last_scraped=datetime.now(timezone.utc).isoformat(),
                content_hash=hashlib.sha256(sec['content'].encode()).hexdigest()[:16],
            ))
        return entries

    def _split_by_headings(self, element, base_url: str) -> list[dict]:
        sections = []
        current_title = "Introduction"
        current_content = []
        current_path = [current_title]

        for child in element.children:
            if hasattr(child, 'name') and child.name and re.match(r'^h[1-3]$', child.name):
                # Save previous section
                if current_content:
                    text = '\n'.join(current_content).strip()
                    if text:
                        sections.append({
                            'title': current_title,
                            'content': text,
                            'path': list(current_path),
                        })
                current_title = child.get_text(strip=True) or "Untitled"
                current_content = []
                level = int(child.name[1])
                current_path = current_path[:level-1] + [current_title]
            else:
                text = child.get_text(strip=True) if hasattr(child, 'get_text') else str(child).strip()
                if text:
                    current_content.append(text)

        # Last section
        if current_content:
            text = '\n'.join(current_content).strip()
            if text:
                sections.append({'title': current_title, 'content': text, 'path': list(current_path)})

        return sections

    def _extract_keywords(self, text: str, max_kw: int = 10) -> list[str]:
        words = re.findall(r'\b\w{3,}\b', text.lower())
        freq = {}
        for w in words:
            if w not in STOP_WORDS and not w.isdigit():
                freq[w] = freq.get(w, 0) + 1
        return sorted(freq, key=freq.get, reverse=True)[:max_kw]

    def parse_markdown(self, markdown: str, url: str) -> list[BaselineEntry]:
        """Parse Markdown by splitting on # headings."""
        sections = []
        current_title = "Introduction"
        current_lines = []

        for line in markdown.split('\n'):
            match = re.match(r'^(#{1,3})\s+(.+)', line)
            if match:
                if current_lines:
                    content = '\n'.join(current_lines).strip()
                    if content:
                        sections.append({'title': current_title, 'content': content, 'path': [current_title]})
                current_title = match.group(2).strip()
                current_lines = []
            else:
                current_lines.append(line)

        if current_lines:
            content = '\n'.join(current_lines).strip()
            if content:
                sections.append({'title': current_title, 'content': content, 'path': [current_title]})

        entries = []
        for sec in sections:
            if len(sec['content']) < 50:
                continue
            eid = hashlib.md5((url + sec['title']).encode()).hexdigest()[:10]
            entries.append(BaselineEntry(
                id=f"bl_{eid}", title=sec['title'], content=sec['content'],
                source_url=url, source_type="markdown", section_path=sec['path'],
                keywords=self._extract_keywords(sec['content']),
                last_scraped=datetime.now(timezone.utc).isoformat(),
                content_hash=hashlib.sha256(sec['content'].encode()).hexdigest()[:16],
            ))
        return entries
