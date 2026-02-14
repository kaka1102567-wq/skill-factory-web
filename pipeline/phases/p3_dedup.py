"""Phase 3 — Dedup: Deduplicate atoms and detect conflicts via Claude."""

import json
import time
from datetime import datetime, timezone

from ..core.types import BuildConfig, PhaseResult, KnowledgeAtom, Conflict
from ..core.logger import PipelineLogger
from ..core.utils import read_json, write_json
from ..core.errors import PhaseError
from ..clients.claude_client import ClaudeClient
from ..seekers.cache import SeekersCache
from ..seekers.lookup import SeekersLookup
from ..prompts.p3_dedup_prompts import P3_SYSTEM, P3_USER_TEMPLATE


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

        # Group atoms by category
        groups = {}
        for atom in raw_atoms:
            cat = atom.get("category", "uncategorized")
            groups.setdefault(cat, []).append(atom)

        all_unique_atoms = []
        all_conflicts = []
        total_duplicates = 0
        total_groups = len(groups)

        for gi, (category, atoms) in enumerate(groups.items()):
            progress = int((gi / max(total_groups, 1)) * 80)
            logger.phase_progress(phase_id, phase_name, progress)
            logger.info(f"Dedup group '{category}': {len(atoms)} atoms", phase=phase_id)

            # Small groups — keep as-is, no Claude call needed
            if len(atoms) <= 2:
                for a in atoms:
                    a["status"] = "deduplicated"
                all_unique_atoms.extend(atoms)
                continue

            # Call Claude for deduplication
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
                )

                unique = result.get("unique_atoms", [])
                conflicts = result.get("conflicts", [])
                stats = result.get("stats", {})

                total_duplicates += stats.get("duplicates_found", 0)
                all_unique_atoms.extend(unique)

                # Build Conflict objects
                for c in conflicts:
                    conflict = Conflict(
                        id=f"conflict_{len(all_conflicts)+1:03d}",
                        atom_a=_find_atom(raw_atoms, c.get("atom_a_id", "")),
                        atom_b=_find_atom(raw_atoms, c.get("atom_b_id", "")),
                        conflict_type=c.get("conflict_type", "contradictory_data"),
                        description=c.get("description", ""),
                    )
                    # Cross-check with baseline if lookup available
                    if lookup:
                        topic = conflict.description[:100]
                        check = lookup.verify_claim(conflict.description, topic)
                        conflict.baseline_evidence = check.get("evidence", "")[:500]
                        if check.get("verified") and check.get("confidence", 0) > config.auto_resolve_threshold:
                            conflict.auto_resolved = True
                            conflict.resolution = "keep_a"
                            conflict.resolution_note = f"Auto-resolved: baseline supports atom_a (confidence {check['confidence']})"

                    all_conflicts.append(conflict)

                logger.debug(
                    f"Group '{category}': {len(atoms)}→{len(unique)} atoms, "
                    f"{len(conflicts)} conflicts",
                    phase=phase_id,
                )

            except Exception as e:
                logger.warn(f"Claude dedup failed for group '{category}': {e}", phase=phase_id)
                # Fallback: keep all atoms in this group
                for a in atoms:
                    a["status"] = "deduplicated"
                all_unique_atoms.extend(atoms)

        # Separate unresolved conflicts
        unresolved = [c for c in all_conflicts if not c.auto_resolved]

        # Calculate score
        if raw_atoms:
            reduction = 1.0 - (len(all_unique_atoms) / len(raw_atoms))
            score = min(100.0, 70.0 + reduction * 30.0)
        else:
            score = 0.0

        # Save outputs
        dedup_path = f"{config.output_dir}/atoms_deduplicated.json"
        write_json({
            "atoms": all_unique_atoms,
            "total_atoms": len(all_unique_atoms),
            "duplicates_merged": total_duplicates,
            "score": round(score, 1),
        }, dedup_path)

        conflicts_path = f"{config.output_dir}/conflicts.json"
        conflicts_data = [c.to_dict() for c in all_conflicts]
        write_json({
            "conflicts": conflicts_data,
            "total": len(all_conflicts),
            "unresolved": len(unresolved),
            "auto_resolved": len(all_conflicts) - len(unresolved),
        }, conflicts_path)

        output_files = [dedup_path, conflicts_path]

        # Emit conflict event if unresolved conflicts exist → pipeline PAUSES
        if unresolved:
            logger.warn(
                f"{len(unresolved)} unresolved conflicts detected — pausing for review",
                phase=phase_id,
            )
            logger.report_conflicts([c.to_dict() for c in unresolved])

        logger.phase_progress(phase_id, phase_name, 95)
        logger.phase_complete(phase_id, phase_name, score=score, atoms_count=len(all_unique_atoms))

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
                "input_atoms": len(raw_atoms),
                "output_atoms": len(all_unique_atoms),
                "duplicates_merged": total_duplicates,
                "conflicts_total": len(all_conflicts),
                "conflicts_unresolved": len(unresolved),
                "is_paused": len(unresolved) > 0,
            },
        )

    except Exception as e:
        logger.phase_failed(phase_id, phase_name, str(e))
        return PhaseResult(
            phase_id=phase_id, status="failed", started_at=started_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
            duration_seconds=time.time() - start_time,
            error_message=str(e),
        )


def _find_atom(atoms: list[dict], atom_id: str) -> dict:
    """Find atom dict by ID, return empty dict if not found."""
    for a in atoms:
        if a.get("id") == atom_id:
            return a
    return {"id": atom_id, "title": "Unknown", "content": ""}
