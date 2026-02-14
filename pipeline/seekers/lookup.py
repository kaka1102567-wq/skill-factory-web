"""Query interface for the Seekers knowledge base."""

from .cache import SeekersCache
from ..core.types import BaselineEntry
from ..core.logger import PipelineLogger


class SeekersLookup:
    def __init__(self, cache: SeekersCache, logger: PipelineLogger):
        self.cache = cache
        self.logger = logger

    def lookup_by_topic(self, topic: str, max_results: int = 5) -> list[BaselineEntry]:
        keywords = [w for w in topic.lower().split() if len(w) >= 3]
        results = []
        seen = set()
        for kw in keywords:
            for entry in self.cache.search_entries(kw):
                if entry.id not in seen:
                    seen.add(entry.id)
                    results.append(entry)
        return results[:max_results]

    def lookup_by_keyword(self, keyword: str) -> list[BaselineEntry]:
        return self.cache.search_entries(keyword)

    def verify_claim(self, claim: str, topic: str) -> dict:
        relevant = self.lookup_by_topic(topic, max_results=3)
        if not relevant:
            return {"verified": False, "confidence": 0.0, "evidence": "",
                    "source_url": "", "match_type": "no_match"}

        claim_words = set(claim.lower().split())
        best, best_score = None, 0.0
        for entry in relevant:
            words = set(entry.content.lower().split())
            score = len(claim_words & words) / max(len(claim_words), 1)
            if score > best_score:
                best_score, best = score, entry

        return {
            "verified": best_score > 0.3,
            "confidence": round(best_score, 2),
            "evidence": best.content[:500] if best else "",
            "source_url": best.source_url if best else "",
            "match_type": "exact" if best_score > 0.7 else "partial" if best_score > 0.3 else "no_match",
        }

    def get_coverage_matrix(self, topics: list[str]) -> list[dict]:
        results = []
        for topic in topics:
            hits = self.lookup_by_topic(topic, max_results=1)
            results.append({
                "topic": topic,
                "covered": len(hits) > 0,
                "entries_count": len(hits),
                "confidence": hits[0].keywords.__len__() / 10 if hits else 0,
            })
        return results
