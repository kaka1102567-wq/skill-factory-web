"""URL Evaluator — uses Claude Haiku to score and rank candidate URLs."""

import json
from dataclasses import dataclass


@dataclass
class RankedURL:
    url: str
    title: str = ""
    relevance_score: float = 0.0
    quality_score: float = 0.0
    authority_score: float = 0.0
    combined_score: float = 0.0
    reason: str = ""


# URLs obviously not documentation
_EXCLUDE_SUBSTRINGS = [
    "/login", "/signup", "/register", "/cart", "/checkout",
    "/search?q=", "#comment", "/privacy-policy", "/terms-of-service",
    "/cookie", "accounts.google.com", "facebook.com/login",
    "youtube.com/watch", "twitter.com/", "x.com/",
    ".pdf", ".zip", ".exe", ".dmg", ".pkg",
    "/wp-admin", "/wp-login", "/feed/", "/rss",
]

_SYSTEM_PROMPT = """You are a Documentation Quality Evaluator. Score each URL for:
- RELEVANCE (0-10): How relevant to the target domain?
- QUALITY (0-10): Likely content quality based on URL structure, title, source
- AUTHORITY (0-10): Source authority (official=10, known tech blog=6, forum=3)

Be strict — only high-quality official docs should score > 7.
RESPOND IN VALID JSON ARRAY ONLY. No markdown."""


def evaluate_urls(candidates, analysis, claude_client, logger, max_refs=15) -> list[RankedURL]:
    """Pre-filter, then use Claude Haiku to score and rank URLs.

    combined_score = relevance*0.4 + quality*0.3 + authority*0.3
    Returns top max_refs URLs sorted by combined_score.
    """
    filtered = _prefilter(candidates)
    if not filtered:
        logger.warn("No URLs left after pre-filter", phase="discovery")
        return []

    logger.info(
        f"Evaluating {len(filtered)} URLs (pre-filtered from {len(candidates)})",
        phase="discovery",
    )

    all_ranked = []
    batches = [filtered[i:i + 50] for i in range(0, len(filtered), 50)]

    for batch_idx, batch in enumerate(batches):
        urls_text = "\n".join(
            f"- {c.url} | title: {c.title or 'N/A'} | source: {c.source}"
            for c in batch
        )
        user = (
            f"Domain: {analysis.domain}\n"
            f"Key topics: {', '.join(analysis.expected_topics[:15])}\n\n"
            f"Evaluate these URLs:\n{urls_text}\n\n"
            'Return JSON array:\n'
            '[{"url": "...", "relevance": N, "quality": N, "authority": N, "reason": "brief"}]'
        )

        try:
            response = claude_client.call(
                system=_SYSTEM_PROMPT, user=user,
                max_tokens=4000, use_light_model=True,
            )
            items = json.loads(response)
            if not isinstance(items, list):
                items = [items]
            for item in items:
                all_ranked.append(RankedURL(
                    url=item["url"],
                    title=next((c.title for c in batch if c.url == item["url"]), ""),
                    relevance_score=float(item.get("relevance", 0)),
                    quality_score=float(item.get("quality", 0)),
                    authority_score=float(item.get("authority", 0)),
                    combined_score=(
                        float(item.get("relevance", 0)) * 0.4
                        + float(item.get("quality", 0)) * 0.3
                        + float(item.get("authority", 0)) * 0.3
                    ),
                    reason=item.get("reason", ""),
                ))
        except (json.JSONDecodeError, Exception) as e:
            logger.warn(f"Evaluation batch {batch_idx} parse error: {e}", phase="discovery")
            for c in batch:
                all_ranked.append(RankedURL(url=c.url, title=c.title, combined_score=5.0))

    all_ranked.sort(key=lambda x: x.combined_score, reverse=True)
    selected = all_ranked[:max_refs]

    if selected:
        logger.info(
            f"Selected {len(selected)} URLs "
            f"(scores: {selected[0].combined_score:.1f} - {selected[-1].combined_score:.1f})",
            phase="discovery",
        )
    return selected


def _prefilter(candidates) -> list:
    """Remove URLs that are clearly not documentation."""
    return [
        c for c in candidates
        if not any(x in c.url.lower() for x in _EXCLUDE_SUBSTRINGS)
    ]
