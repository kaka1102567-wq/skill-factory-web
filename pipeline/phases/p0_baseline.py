"""Phase 0 — Baseline: Build knowledge base from official documentation."""

import json
import os
import re
import time
from datetime import datetime, timezone

from ..core.types import BuildConfig, PhaseResult
from ..core.logger import PipelineLogger
from ..core.utils import write_json
from ..core.errors import SeekersError
from ..clients.web_client import WebClient
from ..seekers.scraper import SeeksScraper
from ..seekers.parser import SeekersParser
from ..seekers.cache import SeekersCache
from ..seekers.lookup import SeekersLookup
from ..seekers.adapter import SkillSeekersAdapter


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for mixed content."""
    return len(text) // 4


def _score_baseline_quality(
    references: list[dict], domain: str, topics: list[str] = None,
) -> float:
    """Score baseline quality using measurable heuristics (no Claude API).

    Components:
      1. Content depth  (40%) — refs have sufficient content
      2. Content diversity (30%) — refs cover different aspects
      3. Relevance signal (30%) — refs contain domain keywords

    Returns score 0-100.
    """
    if not references:
        return 30.0

    # ── 1. Content depth (40%) ──
    depth_scores = []
    for ref in references:
        content = ref.get("content", "")
        word_count = len(content.split())
        if 200 <= word_count <= 5000:
            depth_scores.append(1.0)
        elif 50 <= word_count < 200:
            depth_scores.append(0.5)
        elif word_count > 5000:
            depth_scores.append(0.7)
        else:
            depth_scores.append(0.1)
    content_depth = (sum(depth_scores) / len(depth_scores)) * 100

    # ── 2. Content diversity (30%) ──
    per_ref_keywords = []
    for ref in references:
        content = ref.get("content", "")
        words = re.findall(r'\b\w{4,}\b', content.lower())
        freq = {}
        for w in words:
            if not w.isdigit() and len(w) <= 30:
                freq[w] = freq.get(w, 0) + 1
        top_kw = sorted(freq, key=freq.get, reverse=True)[:20]
        per_ref_keywords.append(set(top_kw))

    if len(per_ref_keywords) >= 2:
        total_overlap = 0
        pairs = 0
        for i in range(len(per_ref_keywords)):
            for j in range(i + 1, len(per_ref_keywords)):
                if per_ref_keywords[i] and per_ref_keywords[j]:
                    overlap = len(per_ref_keywords[i] & per_ref_keywords[j])
                    max_possible = min(
                        len(per_ref_keywords[i]), len(per_ref_keywords[j]),
                    )
                    total_overlap += overlap / max(max_possible, 1)
                    pairs += 1
        avg_overlap = total_overlap / max(pairs, 1)
        content_diversity = (1.0 - avg_overlap) * 100
    else:
        content_diversity = 0.0

    # ── 3. Relevance signal (30%) ──
    domain_keywords = set(
        re.findall(r'\b\w{3,}\b', domain.lower().replace('-', ' ')),
    )
    if topics:
        for t in topics[:10]:
            domain_keywords.update(re.findall(r'\b\w{3,}\b', t.lower()))
    generic = {
        'the', 'and', 'for', 'this', 'with', 'that', 'from', 'your',
        'các', 'của', 'cho', 'với', 'trong', 'được', 'không', 'một',
    }
    domain_keywords -= generic

    if domain_keywords:
        refs_with_match = 0
        for ref in references:
            content_lower = ref.get("content", "").lower()
            matches = sum(1 for kw in domain_keywords if kw in content_lower)
            if matches >= 2:
                refs_with_match += 1
        relevance_signal = (refs_with_match / len(references)) * 100
    else:
        relevance_signal = 50.0

    score = (
        content_depth * 0.40
        + content_diversity * 0.30
        + relevance_signal * 0.30
    )
    return min(100.0, max(0.0, score))


def _run_p0_skill_seekers(config, logger):
    """Load baseline from skill-seekers output directory."""
    phase_id = "p0"
    phase_name = "Baseline"

    adapter = SkillSeekersAdapter(logger=logger)
    data = adapter.load_baseline(config.seekers_output_dir)

    # Build references with token counts
    references = []
    total_tokens = _estimate_tokens(data["skill_md"])
    for ref in data["references"]:
        tokens = _estimate_tokens(ref["content"])
        total_tokens += tokens
        references.append({
            "path": ref["filename"],
            "content": ref["content"],
            "tokens": tokens,
        })

    # Score: relevance-based quality assessment
    score = _score_baseline_quality(
        references, config.domain, data.get("topics", []),
    )

    baseline = {
        "source": "skill_seekers",
        "skill_md": data["skill_md"],
        "references": references,
        "topics": data["topics"],
        "total_tokens": total_tokens,
        "score": score,
    }

    write_json(baseline, f"{config.output_dir}/baseline_summary.json")

    logger.info(
        f"Skill Seekers baseline: {len(references)} refs, "
        f"{len(data['topics'])} topics, {total_tokens} tokens",
        phase=phase_id,
    )

    return score, total_tokens, baseline


def _run_p0_prebuilt(config, logger):
    """Load baseline from a pre-built baseline_summary.json (auto-discovery output)."""
    phase_id = "p0"

    for src in config.baseline_sources:
        if isinstance(src, str) and src.endswith(".json") and os.path.exists(src):
            with open(src, "r", encoding="utf-8") as f:
                data = json.load(f)

            write_json(data, f"{config.output_dir}/baseline_summary.json")

            refs = data.get("references", [])
            refs_count = len(refs)
            topics_count = len(data.get("topics", []))
            total_tokens = data.get("total_tokens", 0)
            # Re-score instead of trusting discovery's count-based score
            domain = data.get(
                "domain",
                config.domain if hasattr(config, 'domain') else "",
            )
            score = _score_baseline_quality(
                refs, domain, data.get("topics", []),
            )

            logger.info(
                f"Pre-built baseline loaded: {refs_count} refs, "
                f"{topics_count} topics, {total_tokens} tokens",
                phase=phase_id,
            )
            return score, refs_count, data

    logger.warn("No valid baseline JSON files found", phase=phase_id)
    return 50.0, 0, None


def _run_p0_legacy(config, cache, logger):
    """Legacy baseline via web scraping (original flow)."""
    phase_id = "p0"
    phase_name = "Baseline"

    sources = config.baseline_sources or []

    if not sources:
        logger.warn(
            "No baseline_sources configured — creating empty baseline",
            phase=phase_id,
        )
        return 50.0, 0, None

    web_client = WebClient(rpm=10, timeout=30)
    scraper = SeeksScraper(web_client, logger)
    parser = SeekersParser()

    if cache is None:
        cache = SeekersCache(
            config.seekers_cache_dir, config.seekers_cache_ttl_hours,
        )

    total_entries = 0
    successful_sources = 0
    failed_sources = 0

    for i, src in enumerate(sources):
        url = src.get("url", "")
        source_type = src.get("type", "documentation")
        progress = int((i / len(sources)) * 80)
        logger.phase_progress(phase_id, phase_name, progress)

        if cache.is_fresh(url):
            cached_entries = cache.get_entries_by_source(url)
            total_entries += len(cached_entries)
            successful_sources += 1
            logger.info(
                f"Cache hit for {url} ({len(cached_entries)} entries)",
                phase=phase_id,
            )
            continue

        logger.info(f"Scraping {url}...", phase=phase_id)
        try:
            page = scraper.scrape_url(url, source_type)

            if page.status == "failed":
                logger.warn(
                    f"Scraping failed for {url}: {page.error}",
                    phase=phase_id,
                )
                failed_sources += 1
                continue

            if page.content_html:
                entries = parser.parse_html(
                    page.content_html, url, source_type,
                )
            else:
                entries = []

            if entries:
                cache.store_entries(entries)
                total_entries += len(entries)
                successful_sources += 1
                logger.info(
                    f"Parsed {len(entries)} entries from {url}",
                    phase=phase_id,
                )
            else:
                logger.warn(
                    f"No entries parsed from {url}", phase=phase_id,
                )
                failed_sources += 1

        except SeekersError as e:
            logger.warn(f"Seekers error for {url}: {e}", phase=phase_id)
            failed_sources += 1
        except Exception as e:
            logger.warn(
                f"Unexpected error scraping {url}: {e}", phase=phase_id,
            )
            failed_sources += 1

    try:
        web_client.close()
    except Exception:
        pass

    # Score based on content quality, not just success rate
    refs_as_dicts = []
    if cache:
        for entry in cache.get_all_entries():
            refs_as_dicts.append({"content": entry.get("content", "")})
    if refs_as_dicts:
        score = _score_baseline_quality(refs_as_dicts, config.domain)
    elif len(sources) > 0:
        score = max(40.0, (successful_sources / len(sources)) * 80)
    else:
        score = 30.0

    summary = {
        "total_entries": total_entries,
        "sources_scraped": successful_sources,
        "sources_failed": failed_sources,
        "cache_entries": cache.get_entry_count() if cache else total_entries,
    }
    write_json(summary, f"{config.output_dir}/baseline_summary.json")

    return score, total_entries, summary


def run_p0(config: BuildConfig, claude=None,
           cache: SeekersCache = None, lookup: SeekersLookup = None,
           logger: PipelineLogger = None) -> PhaseResult:
    """Build baseline knowledge base.

    If config.seekers_output_dir is set, loads from skill-seekers output.
    Otherwise falls back to legacy web scraping.
    """
    logger = logger or PipelineLogger()
    phase_id = "p0"
    phase_name = "Baseline"
    logger.phase_start(phase_id, phase_name, tool="Seekers")
    started_at = datetime.now(timezone.utc).isoformat()
    start_time = time.time()

    try:
        use_skill_seekers = bool(config.seekers_output_dir)
        has_prebuilt = (
            config.baseline_sources
            and isinstance(config.baseline_sources[0], str)
            and config.baseline_sources[0].endswith(".json")
        )

        if use_skill_seekers:
            logger.info(
                f"Using Skill Seekers output: {config.seekers_output_dir}",
                phase=phase_id,
            )
            score, atoms_count, summary = _run_p0_skill_seekers(
                config, logger,
            )
        elif has_prebuilt:
            logger.info(
                "Loading pre-built baseline (auto-discovery)",
                phase=phase_id,
            )
            score, atoms_count, summary = _run_p0_prebuilt(
                config, logger,
            )
        else:
            score, atoms_count, summary = _run_p0_legacy(
                config, cache, logger,
            )

        logger.phase_progress(phase_id, phase_name, 95)
        logger.phase_complete(
            phase_id, phase_name, score=score, atoms_count=atoms_count,
        )

        return PhaseResult(
            phase_id=phase_id, status="done", started_at=started_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
            duration_seconds=time.time() - start_time,
            quality_score=score, atoms_count=atoms_count,
            output_files=[f"{config.output_dir}/baseline_summary.json"],
            metrics=summary or {},
        )

    except Exception as e:
        logger.phase_failed(phase_id, phase_name, str(e))
        return PhaseResult(
            phase_id=phase_id, status="failed", started_at=started_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
            duration_seconds=time.time() - start_time,
            error_message=str(e),
        )
