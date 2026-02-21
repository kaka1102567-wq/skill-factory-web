"""Phase 3 — Dedup: Deduplicate atoms and detect conflicts via Claude."""

import json
import re
import time
from collections import Counter
from datetime import datetime, timezone

from ..core.types import BuildConfig, PhaseResult, KnowledgeAtom, Conflict
from ..core.logger import PipelineLogger
from ..core.utils import read_json, write_json
from ..core.errors import PhaseError
from ..clients.claude_client import ClaudeClient, CreditExhaustedError
from ..seekers.cache import SeekersCache
from ..seekers.lookup import SeekersLookup
from ..prompts.p3_dedup_prompts import P3_SYSTEM, P3_USER_TEMPLATE


def _get_adaptive_threshold(base_threshold: float, atom_count: int) -> float:
    """Lower the overlap threshold when atom count is small to avoid over-dedup.

    With few atoms, aggressive dedup removes too much unique content.
    - < 30 atoms: threshold -= 0.15
    - 30-50 atoms: threshold -= 0.10
    - 50-100 atoms: threshold -= 0.05
    - > 100 atoms: keep base threshold

    Minimum threshold: 0.5 (never below 50% overlap to merge).
    """
    if atom_count < 30:
        adjusted = base_threshold - 0.15
    elif atom_count < 50:
        adjusted = base_threshold - 0.10
    elif atom_count < 100:
        adjusted = base_threshold - 0.05
    else:
        adjusted = base_threshold
    return max(adjusted, 0.5)


def run_p3(config: BuildConfig, claude: ClaudeClient,
           cache: SeekersCache = None, lookup: SeekersLookup = None,
           logger: PipelineLogger = None) -> PhaseResult:
    """Deduplicate Knowledge Atoms and detect conflicts.

    Reads atoms_raw.json from P2, groups by category, calls Claude
    for each group, merges duplicates, and flags conflicts.
    """
    logger = logger or PipelineLogger()
    phase_id = "p3"
    phase_name = "Deduplicate"
    logger.phase_start(phase_id, phase_name, tool="Claude")
    started_at = datetime.now(timezone.utc).isoformat()
    start_time = time.time()

    try:
        # Read P2 output
        input_path = f"{config.output_dir}/atoms_raw.json"
        try:
            raw_data = read_json(input_path)
        except FileNotFoundError:
            raise PhaseError(phase_id, f"P2 output not found: {input_path}")

        raw_atoms = raw_data.get("atoms", [])
        if not raw_atoms:
            logger.warn("No atoms to deduplicate — skipping", phase=phase_id)
            logger.phase_complete(phase_id, phase_name, score=0.0, atoms_count=0)
            return PhaseResult(
                phase_id=phase_id, status="done", started_at=started_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
                duration_seconds=time.time() - start_time,
                quality_score=0.0, atoms_count=0,
            )

        logger.info(f"Deduplicating {len(raw_atoms)} raw atoms", phase=phase_id)

        # Normalize empty categories
        for atom in raw_atoms:
            if not atom.get("category", "").strip():
                atom["category"] = "general"
                logger.debug(
                    f"Atom {atom.get('id', '?')} missing category — assigned 'general'",
                    phase=phase_id,
                )

        # ── Cross-source dedup (transcript vs baseline) ──
        # Use adaptive threshold based on atom count
        adaptive = _get_adaptive_threshold(0.6, len(raw_atoms))
        logger.info(
            f"Cross-source threshold: 0.6 -> {adaptive} "
            f"(adaptive, {len(raw_atoms)} atoms)",
            phase=phase_id,
        )
        cross_result = _cross_source_dedup(raw_atoms, logger, dup_threshold=adaptive)
        raw_atoms = cross_result["atoms"]
        cross_conflicts = cross_result["conflicts"]
        cross_stats = cross_result["stats"]

        if cross_stats["total_actions"] > 0:
            logger.info(
                f"Cross-source: {cross_stats['duplicates_merged']} merged, "
                f"{cross_stats['contradictions_flagged']} conflicts, "
                f"{cross_stats['outdated_replaced']} outdated replaced",
                phase=phase_id,
            )

        # Group atoms by category
        groups = {}
        for atom in raw_atoms:
            cat = atom.get("category", "uncategorized")
            groups.setdefault(cat, []).append(atom)

        all_unique_atoms = []
        all_conflicts = []
        total_duplicates = cross_stats["duplicates_merged"]

        # Split into solo groups (>= MIN_ATOMS_FOR_SOLO) and mini groups
        MIN_ATOMS_FOR_SOLO = 15
        solo_groups = {k: v for k, v in groups.items() if len(v) >= MIN_ATOMS_FOR_SOLO}
        medium_groups = {k: v for k, v in groups.items()
                         if 3 <= len(v) < MIN_ATOMS_FOR_SOLO}
        tiny_groups = {k: v for k, v in groups.items() if len(v) <= 2}

        # Tiny groups — keep as-is, no Claude call needed
        for category, atoms in tiny_groups.items():
            for a in atoms:
                a["status"] = "deduplicated"
            all_unique_atoms.extend(atoms)

        # Batch mini groups into one Claude call
        if medium_groups:
            mini_total = sum(len(v) for v in medium_groups.values())
            logger.info(
                f"Batch dedup {len(medium_groups)} small groups ({mini_total} atoms)",
                phase=phase_id,
            )
            combined_atoms = []
            for cat, atoms in medium_groups.items():
                for a in atoms:
                    a["_batch_category"] = cat
                combined_atoms.extend(atoms)

            all_unique_atoms, all_conflicts, total_duplicates = (
                _dedup_group(
                    "combined_batch", combined_atoms, raw_atoms,
                    config, claude, lookup, logger,
                    all_unique_atoms, all_conflicts, total_duplicates,
                    phase_id,
                )
            )

        # Solo groups — each gets its own Claude call
        total_solo = len(solo_groups)
        for gi, (category, atoms) in enumerate(solo_groups.items()):
            progress = int(((gi + 1) / max(total_solo, 1)) * 80)
            logger.phase_progress(phase_id, phase_name, progress)
            logger.info(f"Dedup group '{category}': {len(atoms)} atoms", phase=phase_id)

            all_unique_atoms, all_conflicts, total_duplicates = (
                _dedup_group(
                    category, atoms, raw_atoms,
                    config, claude, lookup, logger,
                    all_unique_atoms, all_conflicts, total_duplicates,
                    phase_id,
                )
            )

        # Separate unresolved conflicts
        unresolved = [c for c in all_conflicts if not c.auto_resolved]

        # Calculate score — higher kept ratio = cleaner extraction = better
        if raw_atoms:
            kept_ratio = len(all_unique_atoms) / len(raw_atoms)
            score = min(100.0, 65.0 + kept_ratio * 35.0)
        else:
            score = 0.0

        # Save outputs
        dedup_path = f"{config.output_dir}/atoms_deduplicated.json"
        dedup_output = {
            "atoms": all_unique_atoms,
            "total_atoms": len(all_unique_atoms),
            "duplicates_merged": total_duplicates,
            "score": round(score, 1),
        }
        if cross_conflicts:
            dedup_output["conflict_summary"] = {
                "conflicts": cross_conflicts,
                "stats": cross_stats,
            }
        write_json(dedup_output, dedup_path)

        conflicts_path = f"{config.output_dir}/conflicts.json"
        conflicts_data = [c.to_dict() for c in all_conflicts]
        write_json({
            "conflicts": conflicts_data,
            "total": len(all_conflicts),
            "unresolved": len(unresolved),
            "auto_resolved": len(all_conflicts) - len(unresolved),
        }, conflicts_path)

        output_files = [dedup_path, conflicts_path]

        # Log summary
        input_count = raw_data.get("total_atoms", len(raw_atoms))
        parts = []
        if total_duplicates > 0:
            parts.append(f"{total_duplicates} merged")
        if cross_stats["contradictions_flagged"] > 0:
            parts.append(
                f"{cross_stats['contradictions_flagged']} conflict flagged"
            )
        if cross_stats["outdated_replaced"] > 0:
            parts.append(
                f"{cross_stats['outdated_replaced']} outdated replaced"
            )
        detail = ", ".join(parts) if parts else "no changes"
        logger.info(
            f"Dedup: {input_count} -> {len(all_unique_atoms)} atoms"
            f" ({detail})",
            phase=phase_id,
        )

        # Emit conflict event if unresolved conflicts exist → pipeline PAUSES
        if unresolved:
            logger.warn(
                f"{len(unresolved)} unresolved conflicts detected"
                " — pausing for review",
                phase=phase_id,
            )
            logger.report_conflicts([c.to_dict() for c in unresolved])

        logger.phase_progress(phase_id, phase_name, 95)
        logger.phase_complete(
            phase_id, phase_name,
            score=score, atoms_count=len(all_unique_atoms),
        )

        cost = claude.get_cost_summary()
        return PhaseResult(
            phase_id=phase_id, status="done", started_at=started_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
            duration_seconds=time.time() - start_time,
            quality_score=score, atoms_count=len(all_unique_atoms),
            api_cost_usd=cost["cost_usd"],
            tokens_used=cost["input_tokens"] + cost["output_tokens"],
            output_files=output_files,
            metrics={
                "input_atoms": raw_data.get("total_atoms", len(raw_atoms)),
                "output_atoms": len(all_unique_atoms),
                "duplicates_merged": total_duplicates,
                "conflicts_total": len(all_conflicts),
                "conflicts_unresolved": len(unresolved),
                "is_paused": len(unresolved) > 0,
                "cross_source_duplicates": cross_stats["duplicates_merged"],
                "cross_source_contradictions": cross_stats["contradictions_flagged"],
                "cross_source_outdated": cross_stats["outdated_replaced"],
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


def _dedup_group(category, atoms, raw_atoms, config, claude, lookup,
                  logger, all_unique_atoms, all_conflicts,
                  total_duplicates, phase_id):
    """Call Claude to dedup a single group, return updated accumulators."""
    atoms_json = json.dumps(atoms, ensure_ascii=False, indent=1)
    user_prompt = P3_USER_TEMPLATE.format(
        atom_count=len(atoms),
        language=config.language,
        domain=config.domain,
        atoms_json=atoms_json,
    )

    try:
        result = claude.call_json(
            system=P3_SYSTEM, user=user_prompt,
            max_tokens=4096, phase=phase_id,
            use_light_model=True,
        )

        unique = result.get("unique_atoms", [])
        conflicts = result.get("conflicts", [])
        stats = result.get("stats", {})

        total_duplicates += stats.get("duplicates_found", 0)
        all_unique_atoms.extend(unique)

        for c in conflicts:
            conflict = Conflict(
                id=f"conflict_{len(all_conflicts)+1:03d}",
                atom_a=_find_atom(raw_atoms, c.get("atom_a_id", "")),
                atom_b=_find_atom(raw_atoms, c.get("atom_b_id", "")),
                conflict_type=c.get("conflict_type", "contradictory_data"),
                description=c.get("description", ""),
            )
            if lookup:
                topic = conflict.description[:100]
                check = lookup.verify_claim(conflict.description, topic)
                conflict.baseline_evidence = check.get("evidence", "")[:500]
                if (check.get("verified")
                        and check.get("confidence", 0) > config.auto_resolve_threshold):
                    conflict.auto_resolved = True
                    conflict.resolution = "keep_a"
                    conflict.resolution_note = (
                        f"Auto-resolved: baseline supports atom_a "
                        f"(confidence {check['confidence']})"
                    )
            all_conflicts.append(conflict)

        logger.debug(
            f"Group '{category}': {len(atoms)}->{len(unique)} atoms, "
            f"{len(conflicts)} conflicts",
            phase=phase_id,
        )

    except CreditExhaustedError:
        raise
    except Exception as e:
        logger.warn(
            f"Claude dedup failed for group '{category}': {e}",
            phase=phase_id,
        )
        for a in atoms:
            a["status"] = "deduplicated"
        all_unique_atoms.extend(atoms)

    return all_unique_atoms, all_conflicts, total_duplicates


def _find_atom(atoms: list[dict], atom_id: str) -> dict:
    """Find atom dict by ID, return empty dict if not found."""
    for a in atoms:
        if a.get("id") == atom_id:
            return a
    return {"id": atom_id, "title": "Unknown", "content": ""}


# ── Cross-source dedup helpers ──

STOP_WORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "and",
    "or", "not", "in", "on", "at", "to", "for", "of", "with", "by",
    "this", "that", "it", "as", "if", "but", "so", "than", "from",
    "là", "và", "của", "cho", "với", "trong", "khi", "để", "từ",
    "các", "một", "có", "được", "không", "này", "đó", "về", "theo",
    "như", "cũng", "hoặc", "nếu", "thì", "hay", "do", "vì", "bởi",
})

NEGATION_WORDS = frozenset({
    "not", "no", "never", "none", "without", "cannot", "can't",
    "don't", "doesn't", "isn't", "aren't", "won't", "shouldn't",
    "không", "chưa", "chẳng", "không có", "không nên", "không thể",
    "đừng", "hết", "thiếu",
})


def _extract_keywords(text: str) -> set[str]:
    """Extract keyword set from text (title + content)."""
    words = re.findall(r'\b\w{3,}\b', text.lower())
    return {w for w in words if w not in STOP_WORDS and not w.isdigit()}


def _keyword_overlap(kw_a: set, kw_b: set) -> float:
    """Calculate keyword overlap ratio (0.0 - 1.0)."""
    if not kw_a or not kw_b:
        return 0.0
    intersection = len(kw_a & kw_b)
    smaller = min(len(kw_a), len(kw_b))
    return intersection / smaller if smaller > 0 else 0.0


def _extract_numbers(text: str) -> set[str]:
    """Extract all numbers from text."""
    return set(re.findall(r'\b\d+(?:\.\d+)?%?\b', text))


def _has_negation(text: str) -> bool:
    """Check if text contains negation words."""
    text_lower = text.lower()
    return any(neg in text_lower for neg in NEGATION_WORDS)


def _detect_issue_type(
    atom_t: dict, atom_b: dict, overlap: float,
    dup_threshold: float = 0.6,
) -> str | None:
    """Detect issue type between a transcript and baseline atom pair.

    Returns: "duplicate", "contradiction", "outdated", or None.
    """
    # Contradiction detection starts at 2/3 of dup threshold
    contra_threshold = dup_threshold * 2 / 3
    if overlap < contra_threshold:
        return None

    text_t = atom_t.get("content", "")
    text_b = atom_b.get("content", "")

    # DUPLICATE: >= dup_threshold keyword overlap
    if overlap >= dup_threshold:
        return "duplicate"

    # CONTRADICTION: between contra_threshold and dup_threshold + negation/number mismatch
    if contra_threshold <= overlap < dup_threshold:
        neg_t = _has_negation(text_t)
        neg_b = _has_negation(text_b)
        if neg_t != neg_b:
            return "contradiction"

        nums_t = _extract_numbers(text_t)
        nums_b = _extract_numbers(text_b)
        if nums_t and nums_b and nums_t != nums_b:
            # Same topic with different numbers → could be outdated or contradiction
            if atom_b.get("gap_filled"):
                return "outdated"
            return "contradiction"

    return None


def _cross_source_dedup(
    atoms: list[dict], logger,
    dup_threshold: float = 0.6,
) -> dict:
    """Compare transcript vs baseline atoms, detect issues.

    Returns dict with:
      - atoms: cleaned atom list (after merges/replacements)
      - conflicts: list of conflict entries
      - stats: summary counts
    """
    phase_id = "p3"

    transcript_atoms = [
        a for a in atoms if a.get("source", "transcript") == "transcript"
    ]
    baseline_atoms = [
        a for a in atoms if a.get("source") == "baseline"
    ]

    # No cross-source comparison needed
    if not transcript_atoms or not baseline_atoms:
        return {
            "atoms": atoms,
            "conflicts": [],
            "stats": _empty_stats(),
        }

    # Pre-compute keywords
    kw_map = {}
    for a in atoms:
        text = f"{a.get('title', '')} {a.get('content', '')}"
        kw_map[a.get("id", "")] = _extract_keywords(text)

    conflicts = []
    merged_ids = set()
    replaced_ids = set()
    stats = _empty_stats()

    for at in transcript_atoms:
        at_id = at.get("id", "")
        if at_id in merged_ids or at_id in replaced_ids:
            continue

        for ab in baseline_atoms:
            ab_id = ab.get("id", "")
            if ab_id in merged_ids or ab_id in replaced_ids:
                continue

            kw_a = kw_map.get(at_id, set())
            kw_b = kw_map.get(ab_id, set())
            overlap = _keyword_overlap(kw_a, kw_b)

            issue = _detect_issue_type(at, ab, overlap, dup_threshold)
            if not issue:
                continue

            if issue == "duplicate":
                # Keep higher confidence atom, mark other for removal
                conf_t = float(at.get("confidence", 0))
                conf_b = float(ab.get("confidence", 0))
                if conf_t >= conf_b:
                    merged_ids.add(ab_id)
                    keeper = at_id
                else:
                    merged_ids.add(at_id)
                    keeper = ab_id

                conflicts.append({
                    "type": "duplicate",
                    "atom_a": at_id,
                    "atom_b": ab_id,
                    "action": "merged",
                    "kept": keeper,
                    "overlap": round(overlap, 2),
                })
                stats["duplicates_merged"] += 1
                title = at.get("title", "")[:50]
                logger.debug(
                    f"Merged: '{title}' (transcript + baseline)",
                    phase=phase_id,
                )
                break  # transcript atom handled

            elif issue == "contradiction":
                at["conflict_type"] = "contradiction"
                at["conflict_pair"] = [at_id, ab_id]
                ab["conflict_type"] = "contradiction"
                ab["conflict_pair"] = [at_id, ab_id]

                conflicts.append({
                    "type": "contradiction",
                    "atom_a": at_id,
                    "atom_b": ab_id,
                    "action": "flagged",
                })
                stats["contradictions_flagged"] += 1
                logger.debug(
                    f"Conflict: '{at.get('title', '')[:40]}' "
                    f"vs '{ab.get('title', '')[:40]}'",
                    phase=phase_id,
                )

            elif issue == "outdated":
                replaced_ids.add(at_id)
                conflicts.append({
                    "type": "outdated",
                    "atom_a": at_id,
                    "atom_b": ab_id,
                    "action": "replaced_by_baseline",
                })
                stats["outdated_replaced"] += 1
                logger.debug(
                    f"Outdated: '{at.get('title', '')[:50]}'"
                    " -> using baseline version",
                    phase=phase_id,
                )
                break  # transcript atom replaced

    stats["total_actions"] = (
        stats["duplicates_merged"]
        + stats["contradictions_flagged"]
        + stats["outdated_replaced"]
    )

    # Build cleaned atom list
    remove_ids = merged_ids | replaced_ids
    cleaned = [a for a in atoms if a.get("id", "") not in remove_ids]

    return {
        "atoms": cleaned,
        "conflicts": conflicts,
        "stats": stats,
    }


def _empty_stats() -> dict:
    return {
        "duplicates_merged": 0,
        "contradictions_flagged": 0,
        "outdated_replaced": 0,
        "total_actions": 0,
    }
