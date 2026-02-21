"""Phase 1 — Audit: Build topic inventory from transcripts via Claude."""

import json
import re
import time
from collections import Counter
from datetime import datetime, timezone

from ..core.types import BuildConfig, PhaseResult, InventoryItem
from ..core.logger import PipelineLogger
from ..core.utils import read_all_transcripts, chunk_text, write_json, read_json
from ..core.errors import PhaseError
from ..clients.claude_client import ClaudeClient, CreditExhaustedError
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
                        max_tokens=16384, phase=phase_id,
                    )
                    topics = result.get("topics", [])
                    for topic in topics:
                        topic["source_file"] = filename
                    all_topics.extend(topics)
                except CreditExhaustedError:
                    raise
                except Exception as e:
                    logger.warn(f"Claude call failed for chunk in {filename}: {e}", phase=phase_id)

                processed_chunks += 1

        # Merge duplicate topics across chunks
        merged = _merge_topics(all_topics)

        # Cross-reference with baseline
        baseline = _load_skill_seekers_baseline(config.output_dir)
        coverage_matrix = None

        if baseline:
            # Skill-seekers path: build coverage matrix
            logger.info(
                "Comparing topics against skill-seekers baseline",
                phase=phase_id,
            )
            coverage_matrix = _build_coverage_matrix(merged, baseline)
            s = coverage_matrix["summary"]
            logger.info(
                f"Coverage: {s['overlap_count']} overlap, "
                f"{s['unique_expert_count']} unique expert, "
                f"{s['gap_count']} gaps to fill",
                phase=phase_id,
            )

            # Mark baseline_coverage on merged topics
            overlap_names = {
                e["topic"].lower() for e in coverage_matrix["overlap"]
            }
            for item in merged:
                item["baseline_coverage"] = (
                    item.get("topic", "").lower() in overlap_names
                )
        elif lookup:
            # Legacy fallback: cross-reference with SeekersLookup
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

        # ── Calculate score from MEASURABLE metrics ──
        if inventory:
            # Component 1: Topic density (30%)
            topics_per_transcript = len(inventory) / max(
                len(valid_transcripts), 1,
            )
            if 8 <= topics_per_transcript <= 25:
                density_score = 100.0
            elif topics_per_transcript < 8:
                density_score = max(
                    40.0, (topics_per_transcript / 8) * 100,
                )
            else:
                density_score = max(
                    70.0, 100.0 - (topics_per_transcript - 25) * 2,
                )

            # Component 2: Depth distribution (25%)
            depth_counts = {
                "deep": 0, "moderate": 0,
                "surface": 0, "mention_only": 0,
            }
            for item in inventory:
                d = item.get("depth", "surface")
                if d in depth_counts:
                    depth_counts[d] += 1
                else:
                    depth_counts["surface"] += 1

            total_items = len(inventory)
            deep_ratio = depth_counts["deep"] / total_items
            moderate_ratio = depth_counts["moderate"] / total_items
            mention_ratio = depth_counts["mention_only"] / total_items

            depth_score = min(100.0,
                min(deep_ratio, 0.4) / 0.4 * 40
                + min(moderate_ratio, 0.4) / 0.4 * 35
                + (1.0 - min(mention_ratio, 0.3)) / 0.7 * 25,
            )

            # Component 3: Category coverage (20%)
            unique_categories = set(
                item.get("category", "") for item in inventory
                if item.get("category", "").strip()
            )
            if len(unique_categories) >= 5:
                category_score = 100.0
            elif len(unique_categories) >= 3:
                category_score = 80.0
            elif len(unique_categories) >= 2:
                category_score = 60.0
            elif len(unique_categories) == 1:
                category_score = 40.0
            else:
                category_score = 20.0

            # Component 4: Coverage balance (25%)
            if coverage_matrix:
                s = coverage_matrix["summary"]
                total_cm = s["total"]
                gap_ratio = s["gap_count"] / max(total_cm, 1)
                overlap_ratio = s["overlap_count"] / max(total_cm, 1)
                unique_ratio = (
                    s["unique_expert_count"] / max(total_cm, 1)
                )

                balance_score = 0.0
                if 0.15 <= overlap_ratio <= 0.50:
                    balance_score += 35.0
                else:
                    balance_score += max(
                        0, 35 - abs(overlap_ratio - 0.30) * 80,
                    )
                if 0.25 <= unique_ratio <= 0.60:
                    balance_score += 35.0
                else:
                    balance_score += max(
                        0, 35 - abs(unique_ratio - 0.40) * 70,
                    )
                if 0.05 <= gap_ratio <= 0.35:
                    balance_score += 30.0
                else:
                    balance_score += max(
                        0, 30 - abs(gap_ratio - 0.20) * 60,
                    )

                # High gap warning: >50% gaps = baseline likely mismatched
                if gap_ratio > 0.50:
                    balance_score *= 0.5
                    logger.warn(
                        f"High gap ratio ({gap_ratio:.0%}) — baseline may "
                        f"not match transcript content. Consider re-running "
                        f"with better baseline.",
                        phase=phase_id,
                    )
            else:
                balance_score = 50.0

            score = (
                density_score * 0.30
                + depth_score * 0.25
                + category_score * 0.20
                + balance_score * 0.25
            )
            score = min(100.0, max(0.0, score))
        else:
            score = 0.0

        # Save output
        output_path = f"{config.output_dir}/inventory.json"
        output_data = {
            "topics": inventory,
            "total_topics": len(inventory),
            "score": round(score, 1),
        }
        if coverage_matrix:
            output_data["coverage_matrix"] = coverage_matrix
        write_json(output_data, output_path)

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
            metrics={
                "topics_found": len(inventory),
                "transcripts_audited": len(valid_transcripts),
                "baseline_source": "skill_seekers" if baseline else "legacy",
                **(coverage_matrix["summary"] if coverage_matrix else {}),
            },
        )

    except CreditExhaustedError:
        raise
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


# ── Skill-Seekers coverage matrix helpers ──

STOP_WORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "and",
    "or", "not", "in", "on", "at", "to", "for", "of", "with", "by",
    "from", "this", "that", "it", "as", "if", "but", "so", "than",
    "là", "và", "của", "cho", "với", "trong", "khi", "để", "từ",
    "các", "một", "có", "được", "không", "này", "đó", "về", "theo",
    "như", "cũng", "hoặc", "nếu", "thì", "hay", "do", "vì", "bởi",
})


def _load_skill_seekers_baseline(output_dir: str) -> dict | None:
    """Load baseline from P0 output (skill_seekers or auto-discovery)."""
    try:
        summary = read_json(f"{output_dir}/baseline_summary.json")
        if summary.get("source") in (
            "skill_seekers", "auto-discovery", "auto-discovery-content",
        ):
            return summary
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        pass
    return None


def _extract_keywords(text: str, max_kw: int = 15) -> list[str]:
    """Extract top keywords from text using frequency."""
    words = re.findall(r'\b\w{3,}\b', text.lower())
    filtered = [w for w in words if w not in STOP_WORDS and not w.isdigit()]
    counts = Counter(filtered)
    return [w for w, _ in counts.most_common(max_kw)]


def _extract_baseline_topics(baseline: dict) -> list[str]:
    """Extract topic list from baseline SKILL.md headings + topics field."""
    topics = list(baseline.get("topics", []))
    # Also extract ## and ### headings from skill_md
    skill_md = baseline.get("skill_md", "")
    for line in skill_md.split("\n"):
        line = line.strip()
        if line.startswith("## ") or line.startswith("### "):
            heading = re.sub(r'^#+\s*', '', line).strip()
            if heading and heading not in topics:
                topics.append(heading)
    return topics


def _topic_matches_references(topic_name: str, references: list) -> dict:
    """Check if a transcript topic appears in baseline references."""
    keywords = _extract_keywords(topic_name, max_kw=8)
    if not keywords:
        return {"found": False, "file": "", "match_count": 0}

    best_match = {"found": False, "file": "", "match_count": 0}

    for ref in references:
        content_lower = ref.get("content", "").lower()
        matches = sum(1 for kw in keywords if kw in content_lower)
        if matches > best_match["match_count"]:
            best_match = {
                "found": matches >= 2,
                "file": ref.get("path", ""),
                "match_count": matches,
            }

    return best_match


def _build_coverage_matrix(
    transcript_topics: list[dict],
    baseline: dict,
) -> dict:
    """Build coverage matrix: OVERLAP / UNIQUE_EXPERT / GAP_TO_FILL."""
    references = baseline.get("references", [])
    baseline_topics = _extract_baseline_topics(baseline)

    overlap = []
    unique_expert = []

    # Check each transcript topic against baseline
    for item in transcript_topics:
        topic_name = item.get("topic", "")
        match = _topic_matches_references(topic_name, references)

        entry = {
            "topic": topic_name,
            "category": item.get("category", ""),
            "source": "transcript",
        }

        if match["found"]:
            entry["status"] = "OVERLAP"
            entry["matched_ref"] = match["file"]
            entry["match_count"] = match["match_count"]
            overlap.append(entry)
        else:
            entry["status"] = "UNIQUE_EXPERT"
            unique_expert.append(entry)

    # Check baseline topics not covered by transcript
    transcript_kw_sets = []
    for item in transcript_topics:
        kws = set(_extract_keywords(item.get("topic", ""), max_kw=5))
        transcript_kw_sets.append(kws)

    gap_to_fill = []
    for bt in baseline_topics:
        bt_kws = set(_extract_keywords(bt, max_kw=5))
        if not bt_kws:
            continue
        covered = any(
            len(bt_kws & tkws) >= 2 for tkws in transcript_kw_sets
        )
        if not covered:
            gap_to_fill.append({
                "topic": bt,
                "source": "baseline",
                "status": "GAP_TO_FILL",
            })

    total = len(overlap) + len(unique_expert) + len(gap_to_fill)
    coverage_score = (
        (len(overlap) + len(unique_expert)) / max(total, 1) * 100
    )

    return {
        "overlap": overlap,
        "unique_expert": unique_expert,
        "gap_to_fill": gap_to_fill,
        "summary": {
            "overlap_count": len(overlap),
            "unique_expert_count": len(unique_expert),
            "gap_count": len(gap_to_fill),
            "total": total,
            "coverage_score": round(coverage_score, 1),
        },
    }
