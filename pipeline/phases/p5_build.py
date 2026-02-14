"""Phase 5 — Build: Generate SKILL.md, knowledge files, and package zip."""

import json
import os
import time
from datetime import datetime, timezone

from ..core.types import BuildConfig, PhaseResult
from ..core.logger import PipelineLogger
from ..core.utils import read_json, write_json, write_file, create_zip
from ..core.errors import PhaseError
from ..clients.claude_client import ClaudeClient
from ..seekers.cache import SeekersCache
from ..seekers.lookup import SeekersLookup
from ..prompts.p5_build_prompts import (
    P5_SKILL_SYSTEM, P5_SKILL_USER,
    P5_KNOWLEDGE_SYSTEM, P5_KNOWLEDGE_USER,
)


def run_p5(config: BuildConfig, claude: ClaudeClient,
           cache: SeekersCache = None, lookup: SeekersLookup = None,
           logger: PipelineLogger = None) -> PhaseResult:
    """Build final skill package: SKILL.md + knowledge files + zip.

    Reads atoms_verified.json from P4, groups by category into pillars,
    calls Claude to generate markdown files, and packages everything.
    """
    logger = logger or PipelineLogger()
    phase_id = "p5"
    phase_name = "Build"
    logger.phase_start(phase_id, phase_name, tool="Claude")
    started_at = datetime.now(timezone.utc).isoformat()
    start_time = time.time()

    try:
        # Read P4 output
        input_path = f"{config.output_dir}/atoms_verified.json"
        try:
            verified_data = read_json(input_path)
        except FileNotFoundError:
            raise PhaseError(phase_id, f"P4 output not found: {input_path}")

        all_atoms = verified_data.get("atoms", [])
        if not all_atoms:
            raise PhaseError(phase_id, "No verified atoms to build from")

        # Filter out flagged atoms
        build_atoms = [a for a in all_atoms if a.get("status") != "flagged"]
        logger.info(
            f"Building package from {len(build_atoms)} atoms "
            f"({len(all_atoms) - len(build_atoms)} flagged excluded)",
            phase=phase_id,
        )

        # Group by category → pillars
        pillars = {}
        for atom in build_atoms:
            cat = atom.get("category", "general")
            pillars.setdefault(cat, []).append(atom)

        pillar_names = list(pillars.keys())
        total_steps = len(pillar_names) + 2  # +1 for SKILL.md, +1 for zip
        current_step = 0

        output_files = []
        knowledge_dir = os.path.join(config.output_dir, "knowledge")
        os.makedirs(knowledge_dir, exist_ok=True)

        # ── Step 1: Generate knowledge files per pillar ──
        for pillar_name, atoms in pillars.items():
            current_step += 1
            progress = int((current_step / max(total_steps, 1)) * 80)
            logger.phase_progress(phase_id, phase_name, progress)

            logger.info(
                f"Generating knowledge/{pillar_name}.md ({len(atoms)} atoms)",
                phase=phase_id,
            )

            atoms_json = json.dumps(atoms, ensure_ascii=False, indent=1)
            user_prompt = P5_KNOWLEDGE_USER.format(
                pillar_name=pillar_name,
                language=config.language,
                atom_count=len(atoms),
                atoms_json=atoms_json,
            )

            try:
                result = claude.call_json(
                    system=P5_KNOWLEDGE_SYSTEM, user=user_prompt,
                    max_tokens=4096, phase=phase_id,
                )
                content = result.get("content", "")
                if content:
                    file_path = os.path.join(knowledge_dir, f"{pillar_name}.md")
                    write_file(file_path, content)
                    output_files.append(file_path)
                else:
                    logger.warn(f"Empty content for pillar '{pillar_name}'", phase=phase_id)
            except Exception as e:
                logger.warn(f"Failed to generate {pillar_name}.md: {e}", phase=phase_id)
                # Fallback: write raw atoms as markdown
                fallback = _generate_fallback_knowledge(pillar_name, atoms)
                file_path = os.path.join(knowledge_dir, f"{pillar_name}.md")
                write_file(file_path, fallback)
                output_files.append(file_path)

        # ── Step 2: Generate SKILL.md ──
        current_step += 1
        progress = int((current_step / max(total_steps, 1)) * 80)
        logger.phase_progress(phase_id, phase_name, progress)
        logger.info("Generating SKILL.md", phase=phase_id)

        pillars_desc = ", ".join(f"{name} ({len(atoms)} atoms)" for name, atoms in pillars.items())
        user_prompt = P5_SKILL_USER.format(
            name=config.name,
            domain=config.domain,
            language=config.language,
            pillars=pillars_desc,
            atom_count=len(build_atoms),
            quality_tier=config.quality_tier,
        )

        try:
            result = claude.call_json(
                system=P5_SKILL_SYSTEM, user=user_prompt,
                max_tokens=4096, phase=phase_id,
            )
            skill_content = result.get("content", "")
            if skill_content:
                skill_path = os.path.join(config.output_dir, "SKILL.md")
                write_file(skill_path, skill_content)
                output_files.append(skill_path)
            else:
                raise PhaseError(phase_id, "Claude returned empty SKILL.md")
        except PhaseError:
            raise
        except Exception as e:
            logger.warn(f"Claude SKILL.md generation failed: {e} — using fallback", phase=phase_id)
            skill_content = _generate_fallback_skill(config, pillars, build_atoms)
            skill_path = os.path.join(config.output_dir, "SKILL.md")
            write_file(skill_path, skill_content)
            output_files.append(skill_path)

        # ── Step 3: Write metadata.json ──
        avg_confidence = (
            sum(float(a.get("confidence", 0.5)) for a in build_atoms) / len(build_atoms)
            if build_atoms else 0.0
        )
        metadata = {
            "name": config.name,
            "domain": config.domain,
            "language": config.language,
            "quality_tier": config.quality_tier,
            "version": "1.0.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "atoms_total": len(all_atoms),
            "atoms_included": len(build_atoms),
            "atoms_flagged": len(all_atoms) - len(build_atoms),
            "pillars": {name: len(atoms) for name, atoms in pillars.items()},
            "avg_confidence": round(avg_confidence, 3),
            "platforms": config.platforms,
        }
        metadata_path = os.path.join(config.output_dir, "metadata.json")
        write_json(metadata, metadata_path)
        output_files.append(metadata_path)

        # ── Step 4: Create package.zip ──
        logger.info("Creating package.zip", phase=phase_id)
        zip_path = os.path.join(config.output_dir, "package.zip")
        create_zip(config.output_dir, zip_path)
        output_files.append(zip_path)

        # ── Report final quality ──
        score = min(100.0, avg_confidence * 100)

        # Aggregate quality event for build summary UI
        atoms_extracted = verified_data.get("total_atoms", len(all_atoms))
        atoms_deduplicated = len(build_atoms)
        atoms_verified = sum(
            1 for a in build_atoms if a.get("status") in ("verified", "updated")
        )
        total_words = sum(len(a.get("content", "").split()) for a in build_atoms)
        transcript_words = total_words * 10  # rough estimate
        compression = total_words / max(transcript_words, 1)

        logger.report_quality(
            quality_score=score,
            atoms_extracted=atoms_extracted,
            atoms_deduplicated=atoms_deduplicated,
            atoms_verified=atoms_verified,
            compression_ratio=compression,
        )
        logger.report_package(zip_path, config.output_dir)

        logger.phase_progress(phase_id, phase_name, 95)
        logger.phase_complete(phase_id, phase_name, score=score, atoms_count=len(build_atoms))

        cost = claude.get_cost_summary()
        return PhaseResult(
            phase_id=phase_id, status="done", started_at=started_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
            duration_seconds=time.time() - start_time,
            quality_score=score, atoms_count=len(build_atoms),
            api_cost_usd=cost["cost_usd"],
            tokens_used=cost["input_tokens"] + cost["output_tokens"],
            output_files=output_files,
            metrics={
                "pillars": len(pillar_names),
                "knowledge_files": len(pillar_names),
                "atoms_included": len(build_atoms),
                "atoms_flagged": len(all_atoms) - len(build_atoms),
                "zip_path": zip_path,
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


def _generate_fallback_skill(config: BuildConfig, pillars: dict, atoms: list) -> str:
    """Generate a basic SKILL.md without Claude."""
    lines = [
        f"# {config.name}",
        "",
        f"**Domain:** {config.domain}",
        f"**Language:** {config.language}",
        f"**Atoms:** {len(atoms)}",
        f"**Quality:** {config.quality_tier}",
        "",
        "## Knowledge Pillars",
        "",
    ]
    for name, pillar_atoms in pillars.items():
        lines.append(f"- **{name}** — {len(pillar_atoms)} atoms → `knowledge/{name}.md`")
    lines.append("")
    lines.append("## Usage")
    lines.append("")
    lines.append("Load this skill to access structured knowledge from analyzed video transcripts.")
    return "\n".join(lines)


def _generate_fallback_knowledge(pillar_name: str, atoms: list) -> str:
    """Generate a basic knowledge file without Claude."""
    lines = [f"# {pillar_name}", ""]
    for atom in atoms:
        lines.append(f"## {atom.get('title', 'Untitled')}")
        lines.append("")
        lines.append(atom.get("content", ""))
        tags = atom.get("tags", [])
        if tags:
            lines.append("")
            lines.append(f"*Tags: {', '.join(tags)}*")
        lines.append("")
    return "\n".join(lines)
