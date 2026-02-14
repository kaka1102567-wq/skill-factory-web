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


def run_p0(config: BuildConfig, claude=None,
           cache: SeekersCache = None, lookup: SeekersLookup = None,
           logger: PipelineLogger = None) -> PhaseResult:
    """Build baseline knowledge base by scraping documentation sources.

    This phase does NOT call Claude API — only Seekers scraping.
    """
    logger = logger or PipelineLogger()
    phase_id = "p0"
    phase_name = "Baseline"
    logger.phase_start(phase_id, phase_name, tool="Seekers")
    started_at = datetime.now(timezone.utc).isoformat()
    start_time = time.time()

    try:
        sources = config.baseline_sources or []

        # No sources configured — create empty baseline
        if not sources:
            logger.warn("No baseline_sources configured — creating empty baseline", phase=phase_id)
            logger.phase_complete(phase_id, phase_name, score=50.0, atoms_count=0)
            return PhaseResult(
                phase_id=phase_id, status="done", started_at=started_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
                duration_seconds=time.time() - start_time,
                quality_score=50.0, atoms_count=0,
            )

        # Initialize scraper and parser
        web_client = WebClient(rpm=10, timeout=30)
        scraper = SeeksScraper(web_client, logger)
        parser = SeekersParser()

        # Ensure cache exists
        if cache is None:
            cache = SeekersCache(config.seekers_cache_dir, config.seekers_cache_ttl_hours)

        total_entries = 0
        successful_sources = 0
        failed_sources = 0

        for i, src in enumerate(sources):
            url = src.get("url", "")
            source_type = src.get("type", "documentation")
            progress = int((i / len(sources)) * 80)
            logger.phase_progress(phase_id, phase_name, progress)

            # Skip if cache is fresh
            if cache.is_fresh(url):
                cached_entries = cache.get_entries_by_source(url)
                total_entries += len(cached_entries)
                successful_sources += 1
                logger.info(f"Cache hit for {url} ({len(cached_entries)} entries)", phase=phase_id)
                continue

            # Scrape
            logger.info(f"Scraping {url}...", phase=phase_id)
            try:
                page = scraper.scrape_url(url, source_type)

                if page.status == "failed":
                    logger.warn(f"Scraping failed for {url}: {page.error}", phase=phase_id)
                    failed_sources += 1
                    continue

                # Parse HTML → BaselineEntries
                if page.content_html:
                    entries = parser.parse_html(page.content_html, url, source_type)
                else:
                    entries = []

                if entries:
                    cache.store_entries(entries)
                    total_entries += len(entries)
                    successful_sources += 1
                    logger.info(f"Parsed {len(entries)} entries from {url}", phase=phase_id)
                else:
                    logger.warn(f"No entries parsed from {url}", phase=phase_id)
                    failed_sources += 1

            except SeekersError as e:
                logger.warn(f"Seekers error for {url}: {e}", phase=phase_id)
                failed_sources += 1
            except Exception as e:
                logger.warn(f"Unexpected error scraping {url}: {e}", phase=phase_id)
                failed_sources += 1

        # Cleanup
        try:
            web_client.close()
        except Exception:
            pass

        # Calculate score
        if len(sources) > 0:
            success_rate = successful_sources / len(sources)
            score = max(50.0, success_rate * 100)
        else:
            score = 50.0

        # Save baseline summary
        summary = {
            "total_entries": total_entries,
            "sources_scraped": successful_sources,
            "sources_failed": failed_sources,
            "cache_entries": cache.get_entry_count() if cache else total_entries,
        }
        write_json(summary, f"{config.output_dir}/baseline_summary.json")

        logger.phase_progress(phase_id, phase_name, 95)
        logger.phase_complete(phase_id, phase_name, score=score, atoms_count=total_entries)

        return PhaseResult(
            phase_id=phase_id, status="done", started_at=started_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
            duration_seconds=time.time() - start_time,
            quality_score=score, atoms_count=total_entries,
            output_files=[f"{config.output_dir}/baseline_summary.json"],
            metrics=summary,
        )

    except Exception as e:
        logger.phase_failed(phase_id, phase_name, str(e))
        return PhaseResult(
            phase_id=phase_id, status="failed", started_at=started_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
            duration_seconds=time.time() - start_time,
            error_message=str(e),
        )
