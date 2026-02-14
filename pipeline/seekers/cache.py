"""SQLite-backed cache for Seekers baseline knowledge base."""

import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta

from ..core.types import BaselineEntry


class SeekersCache:
    def __init__(self, cache_dir: str, ttl_hours: int = 168):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = str(self.cache_dir / "seekers_cache.db")
        self.ttl = timedelta(hours=ttl_hours)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS baseline_entries (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, content TEXT NOT NULL,
                source_url TEXT, source_type TEXT, section_path TEXT,
                keywords TEXT, last_scraped TEXT, content_hash TEXT)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS scrape_status (
                url TEXT PRIMARY KEY, last_scraped TEXT,
                entry_count INTEGER, content_hash TEXT, status TEXT)""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_src ON baseline_entries(source_url)")

    def store_entries(self, entries: list[BaselineEntry]) -> int:
        with sqlite3.connect(self.db_path) as conn:
            for e in entries:
                conn.execute("""INSERT OR REPLACE INTO baseline_entries
                    (id, title, content, source_url, source_type, section_path, keywords, last_scraped, content_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (e.id, e.title, e.content, e.source_url, e.source_type,
                     json.dumps(e.section_path), json.dumps(e.keywords),
                     e.last_scraped, e.content_hash))
            # Update scrape status
            if entries:
                url = entries[0].source_url
                conn.execute("""INSERT OR REPLACE INTO scrape_status
                    (url, last_scraped, entry_count, content_hash, status)
                    VALUES (?, ?, ?, ?, ?)""",
                    (url, entries[0].last_scraped, len(entries), entries[0].content_hash, "success"))
        return len(entries)

    def get_all_entries(self) -> list[BaselineEntry]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM baseline_entries").fetchall()
        return [self._row_to_entry(r) for r in rows]

    def get_entries_by_source(self, url: str) -> list[BaselineEntry]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM baseline_entries WHERE source_url = ?", (url,)).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def search_entries(self, keyword: str) -> list[BaselineEntry]:
        kw = f"%{keyword.lower()}%"
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM baseline_entries WHERE LOWER(title) LIKE ? OR LOWER(content) LIKE ? OR LOWER(keywords) LIKE ?",
                (kw, kw, kw)).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def is_fresh(self, url: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT last_scraped FROM scrape_status WHERE url = ?", (url,)).fetchone()
        if not row or not row[0]:
            return False
        scraped = datetime.fromisoformat(row[0].replace('Z', '+00:00'))
        return datetime.now(timezone.utc) - scraped < self.ttl

    def get_entry_count(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM baseline_entries").fetchone()[0]

    def clear(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM baseline_entries")
            conn.execute("DELETE FROM scrape_status")

    def _row_to_entry(self, row) -> BaselineEntry:
        return BaselineEntry(
            id=row[0], title=row[1], content=row[2], source_url=row[3],
            source_type=row[4], section_path=json.loads(row[5] or '[]'),
            keywords=json.loads(row[6] or '[]'), last_scraped=row[7] or "",
            content_hash=row[8] or "",
        )
