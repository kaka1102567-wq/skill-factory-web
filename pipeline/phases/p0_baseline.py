"""Phase 0 — Baseline: Build knowledge base from official documentation."""

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

    # Score: 85 base + up to 10 based on reference count (cap at 10 refs)
    ref_bonus = min(len(references), 10)
    score = 85.0 + ref_bonus

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

    if len(sources) > 0:
        success_rate = successful_sources / len(sources)
        score = max(50.0, success_rate * 100)
    else:
        score = 50.0

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

        if use_skill_seekers:
            logger.info(
                f"Using Skill Seekers output: {config.seekers_output_dir}",
                phase=phase_id,
            )
            score, atoms_count, summary = _run_p0_skill_seekers(
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
