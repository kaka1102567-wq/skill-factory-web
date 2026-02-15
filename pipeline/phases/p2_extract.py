"""Phase 2 — Extract: Break transcripts into Knowledge Atoms via Claude."""

import json
import re
import time
from collections import Counter
from datetime import datetime, timezone

from ..core.types import BuildConfig, PhaseResult, KnowledgeAtom
from ..core.logger import PipelineLogger
from ..core.utils import read_all_transcripts, chunk_text, write_json, read_json
from ..core.errors import PhaseError
from ..clients.claude_client import ClaudeClient
from ..seekers.cache import SeekersCache
from ..seekers.lookup import SeekersLookup
from ..seekers.taxonomy import get_all_categories
from ..prompts.p2_extract_prompts import (
    P2_SYSTEM, P2_USER_TEMPLATE,
    P2_GAP_SYSTEM, P2_GAP_USER_TEMPLATE,
)


MAX_GAP_FILL_ATOMS = 10
MAX_CONTENT_CHARS = 12000  # ~3000 tokens excerpt per gap topic


def run_p2(config: BuildConfig, claude: ClaudeClient,
           cache: SeekersCache = None, lookup: SeekersLookup = None,
           logger: PipelineLogger = None) -> PhaseResult:
    """Extract Knowledge Atoms from transcripts + baseline gap filling.

    Stream A: Extract atoms from transcript chunks (existing logic).
    Stream B: Fill gaps from baseline references (if coverage matrix exists).
    """
    logger = logger or PipelineLogger()
    phase_id = "p2"
    phase_name = "Extract"
    logger.phase_start(phase_id, phase_name, tool="Claude")
    started_at = datetime.now(timezone.utc).isoformat()
    start_time = time.time()

    try:
        # Read transcripts
        transcripts = read_all_transcripts(config.transcript_paths)
        valid_transcripts = [t for t in transcripts if t.get("content")]
        if not valid_transcripts:
            raise PhaseError(phase_id, "No valid transcripts to extract from")

        logger.info(
            f"Extracting atoms from {len(valid_transcripts)} transcripts",
            phase=phase_id,
        )

        categories = get_all_categories(config.domain)
        transcript_atoms: list[KnowledgeAtom] = []
        atom_counter = 0

        # ── Stream A: Transcript extraction ──
        all_chunks = []
        for t in valid_transcripts:
            chunks = chunk_text(t["content"], max_tokens=6000)
            for ci, chunk in enumerate(chunks):
                all_chunks.append({
                    "filename": t["filename"],
                    "chunk_index": ci + 1,
                    "total_chunks": len(chunks),
                    "chunk": chunk,
                })

        total_chunks = len(all_chunks)
        logger.info(f"Total chunks to process: {total_chunks}", phase=phase_id)

        for i, chunk_info in enumerate(all_chunks):
            progress = int((i / max(total_chunks, 1)) * 70)
            logger.phase_progress(phase_id, phase_name, progress)

            user_prompt = P2_USER_TEMPLATE.format(
                chunk_index=chunk_info["chunk_index"],
                total_chunks=chunk_info["total_chunks"],
                language=config.language,
                domain=config.domain,
                categories=", ".join(categories),
                filename=chunk_info["filename"],
                chunk=chunk_info["chunk"],
            )

            try:
                result = claude.call_json(
                    system=P2_SYSTEM, user=user_prompt,
                    max_tokens=8192, phase=phase_id,
                )

                raw_atoms = result.get("atoms", [])
                for raw in raw_atoms:
                    atom_counter += 1
                    atom = KnowledgeAtom(
                        id=f"atom_{atom_counter:04d}",
                        title=raw.get("title", "Untitled"),
                        content=raw.get("content", ""),
                        category=raw.get("category", ""),
                        tags=raw.get("tags", []),
                        source_video=chunk_info["filename"],
                        source_timestamp=raw.get("source_timestamp"),
                        confidence=float(raw.get("confidence", 0.5)),
                        status="raw",
                        created_at=datetime.now(timezone.utc).isoformat(),
                        source="transcript",
                    )
                    transcript_atoms.append(atom)

                logger.debug(
                    f"Chunk {chunk_info['chunk_index']}/{chunk_info['total_chunks']} "
                    f"of {chunk_info['filename']}: {len(raw_atoms)} atoms",
                    phase=phase_id,
                )

            except Exception as e:
                logger.warn(
                    f"Claude call failed for chunk {chunk_info['chunk_index']} "
                    f"of {chunk_info['filename']}: {e}",
                    phase=phase_id,
                )

        # ── Stream B: Baseline gap filling ──
        gap_atoms: list[KnowledgeAtom] = []
        coverage_matrix = _load_coverage_matrix(config.output_dir)
        baseline = _load_baseline(config.output_dir)

        if coverage_matrix and baseline:
            gaps = coverage_matrix.get("gap_to_fill", [])
            references = baseline.get("references", [])

            if gaps and references:
                logger.info(
                    f"Filling {len(gaps)} gaps from baseline references",
                    phase=phase_id,
                )
                gap_atoms, atom_counter = _extract_gap_atoms(
                    gaps, references, config, categories,
                    claude, atom_counter, logger,
                )

        # ── Merge streams ──
        all_atoms = transcript_atoms + gap_atoms

        if not all_atoms:
            raise PhaseError(phase_id, "No atoms extracted from any source")

        transcript_count = len(transcript_atoms)
        gap_count = len(gap_atoms)
        logger.info(
            f"Extracted: {transcript_count} from transcript"
            f" + {gap_count} from baseline"
            f" = {len(all_atoms)} total",
            phase=phase_id,
        )

        # Calculate score
        avg_confidence = (
            sum(a.confidence for a in all_atoms) / len(all_atoms)
        )
        score = min(100.0, avg_confidence * 100)

        # Save output
        output_path = f"{config.output_dir}/atoms_raw.json"
        atoms_data = [a.to_dict() for a in all_atoms]
        write_json({
            "atoms": atoms_data,
            "total_atoms": len(all_atoms),
            "score": round(score, 1),
        }, output_path)

        logger.phase_progress(phase_id, phase_name, 95)
        logger.phase_complete(
            phase_id, phase_name,
            score=score, atoms_count=len(all_atoms),
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
                "transcript_atoms": transcript_count,
                "gap_fill_atoms": gap_count,
                "chunks_processed": total_chunks,
                "avg_confidence": round(avg_confidence, 3),
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


# ── Helpers ──

STOP_WORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "and",
    "or", "not", "in", "on", "at", "to", "for", "of", "with", "by",
    "this", "that", "it", "as", "if", "but", "so", "than", "from",
    "là", "và", "của", "cho", "với", "trong", "khi", "để", "từ",
    "các", "một", "có", "được", "không", "này", "đó", "về", "theo",
})


def _load_coverage_matrix(output_dir: str) -> dict | None:
    """Load coverage matrix from P1 inventory.json."""
    try:
        inventory = read_json(f"{output_dir}/inventory.json")
        return inventory.get("coverage_matrix")
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _load_baseline(output_dir: str) -> dict | None:
    """Load skill_seekers baseline from P0 output."""
    try:
        summary = read_json(f"{output_dir}/baseline_summary.json")
        if summary.get("source") == "skill_seekers":
            return summary
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _find_reference_excerpt(
    topic: str, references: list, max_chars: int = MAX_CONTENT_CHARS,
) -> tuple[str, str]:
    """Find the best reference excerpt for a gap topic.

    Returns (ref_file, excerpt) or ("", "") if not found.
    """
    keywords = _extract_keywords(topic, max_kw=8)
    if not keywords:
        return "", ""

    best_ref = ""
    best_pos = -1
    best_content = ""

    for ref in references:
        content = ref.get("content", "")
        content_lower = content.lower()
        matches = sum(1 for kw in keywords if kw in content_lower)
        if matches < 1:
            continue

        # Find position of first keyword match for excerpt centering
        first_pos = len(content)
        for kw in keywords:
            idx = content_lower.find(kw)
            if idx >= 0 and idx < first_pos:
                first_pos = idx

        if matches > best_pos or (matches == best_pos and len(content) < len(best_content)):
            best_ref = ref.get("path", "")
            best_pos = matches
            best_content = content
            best_first = first_pos

    if not best_content:
        return "", ""

    # Extract excerpt centered around first keyword match
    half = max_chars // 2
    start = max(0, best_first - half)
    end = min(len(best_content), start + max_chars)
    excerpt = best_content[start:end]

    return best_ref, excerpt


def _extract_keywords(text: str, max_kw: int = 8) -> list[str]:
    """Extract top keywords from text using frequency."""
    words = re.findall(r'\b\w{3,}\b', text.lower())
    filtered = [w for w in words if w not in STOP_WORDS and not w.isdigit()]
    counts = Counter(filtered)
    return [w for w, _ in counts.most_common(max_kw)]


def _extract_gap_atoms(
    gaps: list[dict], references: list, config: BuildConfig,
    categories: list[str], claude: ClaudeClient,
    atom_counter: int, logger: PipelineLogger,
) -> tuple[list[KnowledgeAtom], int]:
    """Extract atoms from baseline references for gap topics."""
    phase_id = "p2"
    gap_atoms: list[KnowledgeAtom] = []
    total_gap_atoms = 0

    for gap in gaps:
        if total_gap_atoms >= MAX_GAP_FILL_ATOMS:
            logger.info(
                f"Gap-fill limit reached ({MAX_GAP_FILL_ATOMS} atoms)",
                phase=phase_id,
            )
            break

        topic = gap.get("topic", "")
        if not topic:
            continue

        ref_file, excerpt = _find_reference_excerpt(topic, references)
        if not excerpt:
            logger.debug(
                f"No reference content for gap topic: {topic}",
                phase=phase_id,
            )
            continue

        remaining = MAX_GAP_FILL_ATOMS - total_gap_atoms
        user_prompt = P2_GAP_USER_TEMPLATE.format(
            topic=topic,
            language=config.language,
            domain=config.domain,
            categories=", ".join(categories),
            ref_file=ref_file,
            content=excerpt,
        )

        try:
            result = claude.call_json(
                system=P2_GAP_SYSTEM, user=user_prompt,
                max_tokens=2048, phase=phase_id,
            )

            raw_atoms = result.get("atoms", [])[:remaining]
            for raw in raw_atoms:
                atom_counter += 1
                atom = KnowledgeAtom(
                    id=f"atom_{atom_counter:04d}",
                    title=raw.get("title", "Untitled"),
                    content=raw.get("content", ""),
                    category=raw.get("category", ""),
                    tags=raw.get("tags", []),
                    source_video=ref_file,
                    confidence=float(raw.get("confidence", 0.85)),
                    status="raw",
                    created_at=datetime.now(timezone.utc).isoformat(),
                    source="baseline",
                    gap_filled=True,
                    baseline_reference=ref_file,
                )
                gap_atoms.append(atom)
                total_gap_atoms += 1

            logger.debug(
                f"Gap '{topic}': {len(raw_atoms)} atoms from {ref_file}",
                phase=phase_id,
            )

        except Exception as e:
            logger.warn(
                f"Gap-fill failed for '{topic}': {e}",
                phase=phase_id,
            )

    return gap_atoms, atom_counter
