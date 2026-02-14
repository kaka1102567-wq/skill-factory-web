"""Phase 1 — Audit: Build topic inventory from transcripts via Claude."""

import time
from datetime import datetime, timezone

from ..core.types import BuildConfig, PhaseResult, InventoryItem
from ..core.logger import PipelineLogger
from ..core.utils import read_all_transcripts, chunk_text, write_json
from ..core.errors import PhaseError
from ..clients.claude_client import ClaudeClient
from ..seekers.cache import SeekersCache
from ..seekers.lookup import SeekersLookup
from ..seekers.taxonomy import get_all_categories
from ..prompts.p1_audit_prompts import P1_SYSTEM, P1_USER_TEMPLATE


def run_p1(config: BuildConfig, claude: ClaudeClient,
           cache: SeekersCache = None, lookup: SeekersLookup = None,
           logger: PipelineLogger = None) -> PhaseResult:
    """Audit transcripts to build a topic inventory.

    Calls Claude API for each transcript chunk, merges results,
    and cross-references with baseline coverage.
    """
    logger = logger or PipelineLogger()
    phase_id = "p1"
    phase_name = "Audit"
    logger.phase_start(phase_id, phase_name, tool="Claude")
    started_at = datetime.now(timezone.utc).isoformat()
    start_time = time.time()

    try:
        # Read transcripts
        transcripts = read_all_transcripts(config.transcript_paths)
        if not transcripts:
            raise PhaseError(phase_id, "No transcripts found")

        valid_transcripts = [t for t in transcripts if t.get("content")]
        if not valid_transcripts:
            raise PhaseError(phase_id, "All transcripts are empty or failed to read")

        logger.info(f"Found {len(valid_transcripts)} transcripts to audit", phase=phase_id)

        categories = get_all_categories(config.domain)
        all_topics = []
        total_chunks = 0

        # Count total chunks for progress tracking
        for t in valid_transcripts:
            chunks = chunk_text(t["content"], max_tokens=6000)
            total_chunks += len(chunks)

        processed_chunks = 0

        for t in valid_transcripts:
            filename = t["filename"]
            content = t["content"]
            chunks = chunk_text(content, max_tokens=6000)

            logger.info(f"Auditing {filename} ({len(chunks)} chunks)...", phase=phase_id)

            for chunk in chunks:
                progress = int((processed_chunks / max(total_chunks, 1)) * 85)
                logger.phase_progress(phase_id, phase_name, progress)

                user_prompt = P1_USER_TEMPLATE.format(
                    filename=filename,
                    language=config.language,
                    domain=config.domain,
                    categories=", ".join(categories),
                    content=chunk,
                )

                try:
                    result = claude.call_json(
                        system=P1_SYSTEM, user=user_prompt,
                        max_tokens=4096, phase=phase_id,
                    )
                    topics = result.get("topics", [])
                    for topic in topics:
                        topic["source_file"] = filename
                    all_topics.extend(topics)
                except Exception as e:
                    logger.warn(f"Claude call failed for chunk in {filename}: {e}", phase=phase_id)

                processed_chunks += 1

        # Merge duplicate topics across chunks
        merged = _merge_topics(all_topics)

        # Cross-reference with baseline
        if lookup:
            for item in merged:
                hits = lookup.lookup_by_topic(item["topic"], max_results=1)
                item["baseline_coverage"] = len(hits) > 0

        # Build inventory items
        inventory = []
        for item in merged:
            inventory.append({
                "topic": item["topic"],
                "category": item.get("category", ""),
                "quality_score": item.get("quality_score", 0),
                "mentions": item.get("mentions", 1),
                "summary": item.get("summary", ""),
                "depth": item.get("depth", "surface"),
                "baseline_coverage": item.get("baseline_coverage", False),
                "source_files": item.get("source_files", []),
            })

        # Calculate score
        if inventory:
            avg_quality = sum(i["quality_score"] for i in inventory) / len(inventory)
            score = min(100.0, avg_quality)
        else:
            score = 0.0

        # Save output
        output_path = f"{config.output_dir}/inventory.json"
        write_json({"topics": inventory, "total_topics": len(inventory),
                     "score": round(score, 1)}, output_path)

        logger.phase_progress(phase_id, phase_name, 95)
        logger.phase_complete(phase_id, phase_name, score=score, atoms_count=len(inventory))

        cost = claude.get_cost_summary()
        return PhaseResult(
            phase_id=phase_id, status="done", started_at=started_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
            duration_seconds=time.time() - start_time,
            quality_score=score, atoms_count=len(inventory),
            api_cost_usd=cost["cost_usd"],
            tokens_used=cost["input_tokens"] + cost["output_tokens"],
            output_files=[output_path],
            metrics={"topics_found": len(inventory), "transcripts_audited": len(valid_transcripts)},
        )

    except Exception as e:
        logger.phase_failed(phase_id, phase_name, str(e))
        return PhaseResult(
            phase_id=phase_id, status="failed", started_at=started_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
            duration_seconds=time.time() - start_time,
            error_message=str(e),
        )


def _merge_topics(topics: list[dict]) -> list[dict]:
    """Merge duplicate topics by name, combining scores and source files."""
    merged = {}
    for t in topics:
        key = t.get("topic", "").lower().strip()
        if not key:
            continue
        if key in merged:
            existing = merged[key]
            existing["mentions"] = existing.get("mentions", 1) + t.get("mentions", 1)
            existing["quality_score"] = max(
                existing.get("quality_score", 0), t.get("quality_score", 0))
            src = t.get("source_file", "")
            if src and src not in existing.get("source_files", []):
                existing.setdefault("source_files", []).append(src)
        else:
            t.setdefault("source_files", [])
            src = t.get("source_file", "")
            if src and src not in t["source_files"]:
                t["source_files"].append(src)
            merged[key] = t
    return list(merged.values())
