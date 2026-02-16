"""Phase 4 — Verify: Cross-reference atoms against baseline via Seekers + Claude."""

import json
import re
import random
import time
from datetime import datetime, timezone

from ..core.types import BuildConfig, PhaseResult, KnowledgeAtom
from ..core.logger import PipelineLogger
from ..core.config import get_tier_params
from ..core.utils import read_json, write_json
from ..core.errors import PhaseError
from ..clients.claude_client import ClaudeClient, CreditExhaustedError
from ..seekers.cache import SeekersCache
from ..seekers.lookup import SeekersLookup
from ..prompts.p4_verify_prompts import (
    P4_SYSTEM, P4_USER_TEMPLATE,
    P4_BATCH_VERIFY_SYSTEM, P4_BATCH_VERIFY_USER_TEMPLATE,
)

STOP_WORDS = frozenset({
    'là', 'và', 'của', 'các', 'có', 'được', 'cho', 'trong', 'với',
    'này', 'một', 'để', 'không', 'khi', 'từ', 'như', 'về', 'theo',
    'the', 'and', 'for', 'that', 'this', 'with', 'from', 'are', 'was',
    'have', 'has', 'been', 'will', 'can', 'not', 'but', 'use', 'you',
})


def _extract_keywords(text: str, max_kw: int = 10) -> list[str]:
    """Extract top keywords by frequency, excluding stop words."""
    words = re.findall(r'\b\w{3,}\b', text.lower())
    freq: dict[str, int] = {}
    for w in words:
        if w not in STOP_WORDS and not w.isdigit():
            freq[w] = freq.get(w, 0) + 1
    return sorted(freq, key=freq.get, reverse=True)[:max_kw]


STRONG_THRESHOLD = 70.0
WEAK_THRESHOLD = 40.0
SNIPPET_CONTEXT = 200  # chars before + after match point


def _extract_snippet_deep(content: str, keywords: list[str]) -> dict:
    """Extract a snippet around the best keyword cluster with position info."""
    content_lower = content.lower()
    # Find position of first matching keyword for snippet anchor
    best_pos = -1
    for kw in keywords:
        pos = content_lower.find(kw)
        if pos >= 0:
            best_pos = pos
            break

    if best_pos < 0:
        return {"snippet": content[:SNIPPET_CONTEXT], "start": 0,
                "end": min(len(content), SNIPPET_CONTEXT)}

    start = max(0, best_pos - SNIPPET_CONTEXT)
    end = min(len(content), best_pos + SNIPPET_CONTEXT)
    snippet = content[start:end].strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(content):
        snippet = snippet + "..."
    return {"snippet": snippet, "start": start, "end": end}


def _search_baseline(atom_title: str, atom_content: str,
                     references: list[dict]) -> dict:
    """Deep evidence search with match scores and snippet extraction."""
    keywords = _extract_keywords(atom_title + " " + atom_content)
    if not keywords:
        return {"found": False, "match_score": 0.0, "keywords_matched": [],
                "keywords_total": 0}

    total_kw = len(keywords)
    best_ref = None
    best_matched = []
    best_score = 0.0

    for ref in references:
        ref_lower = ref["content"].lower()
        matched = [kw for kw in keywords if kw in ref_lower]
        score = (len(matched) / total_kw) * 100 if total_kw > 0 else 0.0
        if score > best_score:
            best_score = score
            best_matched = matched
            best_ref = ref

    if best_score >= WEAK_THRESHOLD and best_ref:
        snippet_info = _extract_snippet_deep(best_ref["content"], best_matched)
        return {
            "found": True,
            "file": best_ref["path"],
            "snippet": snippet_info["snippet"],
            "snippet_start": snippet_info["start"],
            "snippet_end": snippet_info["end"],
            "match_score": round(best_score, 1),
            "keywords_matched": best_matched,
            "keywords_total": total_kw,
        }

    return {
        "found": False,
        "closest_file": best_ref["path"] if best_ref else None,
        "closest_score": round(best_score, 1),
        "keywords_matched": best_matched,
        "keywords_total": total_kw,
        "note": (f"Expert insight — closest match in "
                 f"{best_ref['path'] if best_ref else 'none'} "
                 f"but below threshold")
    }


def _load_skill_seekers_baseline(output_dir: str) -> list[dict] | None:
    """Try to load skill_seekers references from P0 baseline_summary."""
    try:
        summary = read_json(f"{output_dir}/baseline_summary.json")
        if (summary.get("source") == "skill_seekers"
                and summary.get("references")):
            return summary["references"]
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        pass
    return None


def _verify_with_skill_seekers(atoms_to_verify, ss_references, logger):
    """Verify atoms against skill-seekers baseline references."""
    phase_id = "p4"
    strong_count = 0
    weak_count = 0
    none_count = 0
    verified_ids = set()

    for i, atom in enumerate(atoms_to_verify):
        atom_id = atom.get("id", "")
        atom_title = atom.get("title", "")
        atom_content = atom.get("content", "")

        result = _search_baseline(atom_title, atom_content, ss_references)

        if result["found"]:
            score = result["match_score"]
            atom["status"] = "verified"
            atom["confidence"] = min(
                1.0, float(atom.get("confidence", 0.5)) + 0.05,
            )
            atom["verification_note"] = (
                f"Verified against {result['file']} "
                f"({len(result['keywords_matched'])}/{result['keywords_total']} "
                f"keywords, {score}% match)"
            )
            atom["baseline_reference"] = result["file"]
            atom["evidence"] = {
                "found": True,
                "file": result["file"],
                "snippet": result["snippet"],
                "snippet_start": result["snippet_start"],
                "snippet_end": result["snippet_end"],
                "match_score": score,
                "keywords_matched": result["keywords_matched"],
                "keywords_total": result["keywords_total"],
            }
            if score >= STRONG_THRESHOLD:
                strong_count += 1
            else:
                weak_count += 1
        else:
            atom["status"] = "verified"
            atom["confidence"] = float(atom.get("confidence", 0.5))
            atom["verification_note"] = (
                "Expert insight — not found in official docs"
            )
            atom["evidence"] = {
                "found": False,
                "closest_file": result.get("closest_file"),
                "closest_score": result.get("closest_score", 0.0),
                "note": result.get("note",
                    "Expert insight — not found in official docs"),
            }
            none_count += 1

        verified_ids.add(atom_id)

    total = strong_count + weak_count + none_count
    if total > 0:
        verified = strong_count + weak_count
        pct = round(verified / total * 100, 1)
        logger.info(
            f"Verified {verified}/{total} atoms ({pct}%)",
            phase=phase_id,
        )
        logger.info(
            f"  {strong_count} strong evidence (>={int(STRONG_THRESHOLD)}% match)",
            phase=phase_id,
        )
        logger.info(
            f"  {weak_count} weak evidence "
            f"({int(WEAK_THRESHOLD)}-{int(STRONG_THRESHOLD)}% match)",
            phase=phase_id,
        )
        logger.info(
            f"  {none_count} no evidence (expert insights)",
            phase=phase_id,
        )

    return strong_count + weak_count, none_count, verified_ids


BATCH_SIZE = 10


def _verify_with_claude_batch(atoms_to_verify, config, claude, lookup, logger):
    """Verify atoms via Claude API in batches of BATCH_SIZE (light model)."""
    phase_id = "p4"
    verified_count = 0
    updated_count = 0
    flagged_count = 0
    verified_ids = set()

    total_batches = (len(atoms_to_verify) + BATCH_SIZE - 1) // BATCH_SIZE
    logger.info(
        f"Batch verifying {len(atoms_to_verify)} atoms in "
        f"{total_batches} batches (light model)",
        phase=phase_id,
    )

    for i in range(0, len(atoms_to_verify), BATCH_SIZE):
        batch = atoms_to_verify[i:i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        progress = int((batch_num / max(total_batches, 1)) * 85)
        logger.phase_progress(phase_id, "Verify", progress)
        logger.info(
            f"Batch {batch_num}/{total_batches} ({len(batch)} atoms)",
            phase=phase_id,
        )

        # Collect baseline excerpts for entire batch
        baseline_excerpts = ""
        if lookup:
            all_keywords = []
            for a in batch:
                all_keywords.extend(a.get("tags", []))
            unique_kw = list(set(all_keywords))[:20]
            for kw in unique_kw:
                hits = lookup.lookup_by_topic(kw, max_results=2)
                for h in hits:
                    content = h.content if hasattr(h, 'content') else h.get("content", "")
                    title = h.title if hasattr(h, 'title') else h.get("title", kw)
                    if content:
                        baseline_excerpts += (
                            f"\n### {title}\n"
                            f"{content[:500]}\n"
                        )

        # Build atoms JSON for prompt
        atoms_json = json.dumps([{
            "atom_id": a.get("id", ""),
            "title": a.get("title", ""),
            "content": a.get("content", ""),
            "category": a.get("category", ""),
            "tags": a.get("tags", []),
        } for a in batch], ensure_ascii=False, indent=2)

        user_prompt = P4_BATCH_VERIFY_USER_TEMPLATE.format(
            baseline_excerpts=baseline_excerpts or "(No baseline references available)",
            atoms_json=atoms_json,
            batch_size=len(batch),
        )

        try:
            result = claude.call_json(
                system=P4_BATCH_VERIFY_SYSTEM,
                user=user_prompt,
                max_tokens=4096,
                phase=phase_id,
                use_light_model=True,
            )

            results_list = result.get("results", [])
            results_map = {r.get("atom_id", ""): r for r in results_list}

            for atom in batch:
                atom_id = atom.get("id", "")
                r = results_map.get(atom_id)
                if r:
                    status = r.get("status", "verified")
                    adj = float(r.get("confidence_adjustment", 0))
                    atom["status"] = status
                    atom["confidence"] = min(
                        1.0, float(atom.get("confidence", 0.5)) + adj,
                    )
                    atom["verification_note"] = r.get(
                        "verification_note", "",
                    )
                    atom["baseline_reference"] = r.get(
                        "baseline_reference",
                    )
                    if status == "flagged":
                        flagged_count += 1
                    else:
                        verified_count += 1
                else:
                    atom["status"] = "verified"
                    atom["verification_note"] = (
                        "Expert insight — batch verify fallback"
                    )
                    verified_count += 1
                verified_ids.add(atom_id)

        except CreditExhaustedError:
            raise
        except Exception as e:
            logger.warn(
                f"Batch verify failed for batch {batch_num}: {e}",
                phase=phase_id,
            )
            for atom in batch:
                atom["status"] = "verified"
                atom["verification_note"] = f"Verification skipped: {e}"
                verified_ids.add(atom.get("id", ""))
                verified_count += 1

    return verified_count, updated_count, flagged_count, verified_ids


def run_p4(config: BuildConfig, claude: ClaudeClient,
           cache: SeekersCache = None, lookup: SeekersLookup = None,
           logger: PipelineLogger = None) -> PhaseResult:
    """Verify deduplicated atoms against baseline knowledge.

    If skill-seekers baseline is available, verifies via keyword search.
    Otherwise falls back to Seekers lookup + Claude verification.
    """
    logger = logger or PipelineLogger()
    phase_id = "p4"
    phase_name = "Verify"
    logger.phase_start(phase_id, phase_name, tool="Claude + Seekers")
    started_at = datetime.now(timezone.utc).isoformat()
    start_time = time.time()

    try:
        # Read P3 output
        input_path = f"{config.output_dir}/atoms_deduplicated.json"
        try:
            dedup_data = read_json(input_path)
        except FileNotFoundError:
            raise PhaseError(
                phase_id, f"P3 output not found: {input_path}",
            )

        all_atoms = dedup_data.get("atoms", [])
        if not all_atoms:
            logger.warn("No atoms to verify — skipping", phase=phase_id)
            logger.phase_complete(
                phase_id, phase_name, score=0.0, atoms_count=0,
            )
            return PhaseResult(
                phase_id=phase_id, status="done", started_at=started_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
                duration_seconds=time.time() - start_time,
                quality_score=0.0, atoms_count=0,
            )

        # Quality tier controls sampling
        tier_params = get_tier_params(config.quality_tier)
        sample_pct = tier_params["verify_sample_pct"]

        if sample_pct >= 100:
            atoms_to_verify = list(all_atoms)
        else:
            sample_size = max(
                1, int(len(all_atoms) * sample_pct / 100),
            )
            atoms_to_verify = random.sample(
                all_atoms, min(sample_size, len(all_atoms)),
            )

        total_to_verify = len(atoms_to_verify)
        logger.info(
            f"Verifying {total_to_verify}/{len(all_atoms)} atoms "
            f"(tier={config.quality_tier}, sample={sample_pct}%)",
            phase=phase_id,
        )

        # Try skill-seekers baseline first
        ss_references = _load_skill_seekers_baseline(config.output_dir)

        if ss_references:
            logger.info(
                f"Using Skill Seekers baseline ({len(ss_references)} refs)",
                phase=phase_id,
            )
            verified_count, unverified_count, verified_ids = (
                _verify_with_skill_seekers(
                    atoms_to_verify, ss_references, logger,
                )
            )
            updated_count = 0
            flagged_count = unverified_count
        else:
            verified_count, updated_count, flagged_count, verified_ids = (
                _verify_with_claude_batch(
                    atoms_to_verify, config, claude, lookup, logger,
                )
            )

        # Mark non-sampled atoms as passthrough
        for atom in all_atoms:
            if atom.get("id") not in verified_ids:
                atom["status"] = "verified"
                atom.setdefault(
                    "verification_note", "Not sampled — passed through",
                )

        # Calculate score
        if all_atoms:
            avg_confidence = (
                sum(float(a.get("confidence", 0.5)) for a in all_atoms)
                / len(all_atoms)
            )
            flagged_penalty = (
                flagged_count / max(total_to_verify, 1)
            ) * 20
            score = min(
                100.0, max(0.0, avg_confidence * 100 - flagged_penalty),
            )
        else:
            score = 0.0

        # Save output
        output_path = f"{config.output_dir}/atoms_verified.json"
        write_json({
            "atoms": all_atoms,
            "total_atoms": len(all_atoms),
            "verified": verified_count,
            "updated": updated_count,
            "flagged": flagged_count,
            "score": round(score, 1),
        }, output_path)

        logger.phase_progress(phase_id, phase_name, 95)
        logger.phase_complete(
            phase_id, phase_name, score=score, atoms_count=len(all_atoms),
        )

        cost = claude.get_cost_summary()
        return PhaseResult(
            phase_id=phase_id, status="done", started_at=started_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
            duration_seconds=time.time() - start_time,
            quality_score=score, atoms_count=len(all_atoms),
            api_cost_usd=cost["cost_usd"],
            tokens_used=cost["input_tokens"] + cost["output_tokens"],
            output_files=[output_path],
            metrics={
                "total_atoms": len(all_atoms),
                "sampled": total_to_verify,
                "verified": verified_count,
                "updated": updated_count,
                "flagged": flagged_count,
                "sample_pct": sample_pct,
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
