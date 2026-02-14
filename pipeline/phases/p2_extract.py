"""Phase 2 — Extract: Break transcripts into Knowledge Atoms via Claude."""

import time
from datetime import datetime, timezone

from ..core.types import BuildConfig, PhaseResult, KnowledgeAtom
from ..core.logger import PipelineLogger
from ..core.utils import read_all_transcripts, chunk_text, write_json
from ..core.errors import PhaseError
from ..clients.claude_client import ClaudeClient
from ..seekers.cache import SeekersCache
from ..seekers.lookup import SeekersLookup
from ..seekers.taxonomy import get_all_categories
from ..prompts.p2_extract_prompts import P2_SYSTEM, P2_USER_TEMPLATE


def run_p2(config: BuildConfig, claude: ClaudeClient,
           cache: SeekersCache = None, lookup: SeekersLookup = None,
           logger: PipelineLogger = None) -> PhaseResult:
    """Extract Knowledge Atoms from transcripts.

    Calls Claude API for each transcript chunk, parses atoms,
    assigns unique IDs, and saves to atoms_raw.json.
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

        logger.info(f"Extracting atoms from {len(valid_transcripts)} transcripts", phase=phase_id)

        categories = get_all_categories(config.domain)
        all_atoms: list[KnowledgeAtom] = []
        atom_counter = 0

        # Count total chunks for progress
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
            progress = int((i / max(total_chunks, 1)) * 85)
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
                    max_tokens=4096, phase=phase_id,
                )

                raw_atoms = result.get("atoms", [])
                for raw in raw_atoms:
                    atom_counter += 1
                    atom_id = f"atom_{atom_counter:04d}"

                    atom = KnowledgeAtom(
                        id=atom_id,
                        title=raw.get("title", "Untitled"),
                        content=raw.get("content", ""),
                        category=raw.get("category", ""),
                        tags=raw.get("tags", []),
                        source_video=chunk_info["filename"],
                        source_timestamp=raw.get("source_timestamp"),
                        confidence=float(raw.get("confidence", 0.5)),
                        status="raw",
                        created_at=datetime.now(timezone.utc).isoformat(),
                    )
                    all_atoms.append(atom)

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

        if not all_atoms:
            raise PhaseError(phase_id, "No atoms extracted from any chunk")

        # Calculate score based on atom quality
        avg_confidence = sum(a.confidence for a in all_atoms) / len(all_atoms)
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
        logger.phase_complete(phase_id, phase_name, score=score, atoms_count=len(all_atoms))

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
