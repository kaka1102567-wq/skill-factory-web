"""Phase 5 — Build: Generate SKILL.md, knowledge files, and package zip."""

import json
import os
import shutil
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


def _load_skill_seekers_baseline(output_dir: str) -> dict | None:
    """Load skill_seekers baseline from P0 output if available."""
    try:
        summary = read_json(f"{output_dir}/baseline_summary.json")
        if summary.get("source") == "skill_seekers":
            return summary
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        pass
    return None


def _copy_seekers_references(baseline: dict, output_dir: str,
                             logger: PipelineLogger) -> None:
    """Copy skill-seekers references into build output."""
    refs_dir = os.path.join(output_dir, "references")
    os.makedirs(refs_dir, exist_ok=True)

    for ref in baseline.get("references", []):
        ref_path = os.path.join(refs_dir, ref["path"])
        write_file(ref_path, ref["content"])

    logger.info(
        f"Copied {len(baseline.get('references', []))} reference files",
        phase="p5",
    )


def _classify_atoms(atoms: list) -> dict:
    """Classify atoms into expert tips vs verified knowledge."""
    expert_tips = []
    verified_knowledge = []

    for atom in atoms:
        note = atom.get("verification_note") or ""
        if "Expert insight" in note or "not found in official" in note:
            expert_tips.append(atom)
        else:
            verified_knowledge.append(atom)

    return {
        "expert_tips": expert_tips,
        "verified": verified_knowledge,
    }


def _build_routing_section(pillars: dict, references: list) -> str:
    """Build routing logic section for SKILL.md."""
    lines = ["## Routing Logic", ""]

    if references:
        lines.append("### Reference Docs")
        for ref in references:
            name = ref["path"].replace(".md", "").replace("_", " ").title()
            lines.append(
                f"- If user asks about **{name}** "
                f"-> see `references/{ref['path']}`"
            )
        lines.append("")

    if pillars:
        lines.append("### Knowledge Files")
        for pillar_name, atoms in pillars.items():
            display = pillar_name.replace("_", " ").title()
            topics = ", ".join(
                a.get("title", "") for a in atoms[:3]
            )
            lines.append(
                f"- If user asks about **{display}** "
                f"({topics}) -> see `knowledge/{pillar_name}.md`"
            )
        lines.append("")

    return "\n".join(lines)


def _build_expert_section(expert_atoms: list) -> str:
    """Build Expert Tips section from unverified-in-docs atoms."""
    if not expert_atoms:
        return ""

    lines = ["## Expert Tips", "",
             "> Insights from practitioners — not found in official docs.",
             ""]
    for atom in expert_atoms:
        lines.append(f"### {atom.get('title', 'Tip')}")
        lines.append("")
        lines.append(atom.get("content", ""))
        tags = atom.get("tags", [])
        if tags:
            lines.append("")
            lines.append(f"*Tags: {', '.join(tags)}*")
        lines.append("")
    return "\n".join(lines)


def _build_advanced_section(verified_atoms: list) -> str:
    """Build Advanced Strategies from high-confidence verified atoms."""
    advanced = [
        a for a in verified_atoms
        if float(a.get("confidence", 0)) >= 0.9
    ]
    if not advanced:
        return ""

    lines = ["## Advanced Strategies", ""]
    for atom in advanced[:10]:
        lines.append(f"### {atom.get('title', 'Strategy')}")
        lines.append("")
        lines.append(atom.get("content", ""))
        lines.append("")
    return "\n".join(lines)


def _build_skill_seekers_skill_md(config, baseline, pillars,
                                  build_atoms, avg_confidence) -> str:
    """Build production SKILL.md using skill-seekers template + atoms."""
    classified = _classify_atoms(build_atoms)
    references = baseline.get("references", [])

    # YAML frontmatter
    lines = [
        "---",
        f"name: {config.name}",
        "description: >",
        f"  Use this skill when working with {config.domain}.",
        f"  Covers {len(build_atoms)} verified knowledge atoms across",
        f"  {len(pillars)} categories with reference documentation.",
        'version: "1.0"',
        "metadata:",
        f"  author: Skill Factory",
        f"  domain: {config.domain}",
        f"  atoms: {len(build_atoms)}",
        f"  confidence: {avg_confidence:.2f}",
        "---",
        "",
        f"# {config.name}",
        "",
        f"Structured knowledge skill for **{config.domain}**, "
        f"generated from official documentation and expert analysis.",
        "",
    ]

    # Routing logic
    lines.append(_build_routing_section(pillars, references))

    # Knowledge pillars overview
    lines.append("## Knowledge Pillars")
    lines.append("")
    for name, atoms in pillars.items():
        display = name.replace("_", " ").title()
        lines.append(
            f"- **{display}** — {len(atoms)} atoms "
            f"-> `knowledge/{name}.md`"
        )
    lines.append("")

    # Expert Tips
    expert_section = _build_expert_section(classified["expert_tips"])
    if expert_section:
        lines.append(expert_section)

    # Advanced Strategies
    advanced_section = _build_advanced_section(classified["verified"])
    if advanced_section:
        lines.append(advanced_section)

    # References
    if references:
        lines.append("## References")
        lines.append("")
        for ref in references:
            lines.append(f"- `references/{ref['path']}`")
        lines.append("")

    return "\n".join(lines)


def run_p5(config: BuildConfig, claude: ClaudeClient,
           cache: SeekersCache = None, lookup: SeekersLookup = None,
           logger: PipelineLogger = None) -> PhaseResult:
    """Build final skill package: SKILL.md + knowledge files + zip.

    If skill-seekers baseline exists, builds production SKILL.md with
    routing logic, expert tips, and reference docs.
    Otherwise falls back to Claude-generated SKILL.md.
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
            raise PhaseError(
                phase_id, f"P4 output not found: {input_path}",
            )

        all_atoms = verified_data.get("atoms", [])
        if not all_atoms:
            raise PhaseError(phase_id, "No verified atoms to build from")

        # Filter out flagged atoms
        build_atoms = [
            a for a in all_atoms if a.get("status") != "flagged"
        ]
        logger.info(
            f"Building from {len(build_atoms)} atoms "
            f"({len(all_atoms) - len(build_atoms)} flagged excluded)",
            phase=phase_id,
        )

        # Group by category -> pillars
        pillars: dict[str, list] = {}
        for atom in build_atoms:
            cat = atom.get("category", "general")
            pillars.setdefault(cat, []).append(atom)

        pillar_names = list(pillars.keys())
        total_steps = len(pillar_names) + 3  # knowledge + SKILL + meta + zip
        current_step = 0
        output_files = []

        knowledge_dir = os.path.join(config.output_dir, "knowledge")
        os.makedirs(knowledge_dir, exist_ok=True)

        # Check for skill-seekers baseline
        baseline = _load_skill_seekers_baseline(config.output_dir)
        use_seekers = baseline is not None

        if use_seekers:
            logger.info(
                "Using Skill Seekers baseline for production build",
                phase=phase_id,
            )
            _copy_seekers_references(baseline, config.output_dir, logger)

        # ── Step 1: Generate knowledge files per pillar ──
        for pillar_name, atoms in pillars.items():
            current_step += 1
            progress = int((current_step / max(total_steps, 1)) * 80)
            logger.phase_progress(phase_id, phase_name, progress)

            logger.info(
                f"Generating knowledge/{pillar_name}.md "
                f"({len(atoms)} atoms)",
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
                    fp = os.path.join(knowledge_dir, f"{pillar_name}.md")
                    write_file(fp, content)
                    output_files.append(fp)
                else:
                    logger.warn(
                        f"Empty content for pillar '{pillar_name}'",
                        phase=phase_id,
                    )
            except Exception as e:
                logger.warn(
                    f"Failed to generate {pillar_name}.md: {e}",
                    phase=phase_id,
                )
                fallback = _generate_fallback_knowledge(
                    pillar_name, atoms,
                )
                fp = os.path.join(knowledge_dir, f"{pillar_name}.md")
                write_file(fp, fallback)
                output_files.append(fp)

        # ── Step 2: Generate SKILL.md ──
        current_step += 1
        progress = int((current_step / max(total_steps, 1)) * 80)
        logger.phase_progress(phase_id, phase_name, progress)
        logger.info("Generating SKILL.md", phase=phase_id)

        avg_confidence = (
            sum(float(a.get("confidence", 0.5)) for a in build_atoms)
            / len(build_atoms)
            if build_atoms else 0.0
        )

        if use_seekers:
            skill_content = _build_skill_seekers_skill_md(
                config, baseline, pillars, build_atoms, avg_confidence,
            )
        else:
            skill_content = _build_skill_md_via_claude(
                config, pillars, build_atoms, claude, logger,
            )

        skill_path = os.path.join(config.output_dir, "SKILL.md")
        write_file(skill_path, skill_content)
        output_files.append(skill_path)

        # ── Step 3: Write metadata.json ──
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
            "pillars": {
                name: len(atoms) for name, atoms in pillars.items()
            },
            "avg_confidence": round(avg_confidence, 3),
            "platforms": config.platforms,
            "baseline_source": "skill_seekers" if use_seekers else "legacy",
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

        atoms_extracted = verified_data.get("total_atoms", len(all_atoms))
        atoms_deduplicated = len(build_atoms)
        atoms_verified = sum(
            1 for a in build_atoms
            if a.get("status") in ("verified", "updated")
        )
        total_words = sum(
            len(a.get("content", "").split()) for a in build_atoms
        )
        transcript_words = total_words * 10
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
        logger.phase_complete(
            phase_id, phase_name, score=score,
            atoms_count=len(build_atoms),
        )

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


def _build_skill_md_via_claude(config, pillars, build_atoms,
                               claude, logger) -> str:
    """Generate SKILL.md via Claude API (legacy path)."""
    pillars_desc = ", ".join(
        f"{name} ({len(atoms)} atoms)"
        for name, atoms in pillars.items()
    )
    user_prompt = P5_SKILL_USER.format(
        name=config.name, domain=config.domain,
        language=config.language, pillars=pillars_desc,
        atom_count=len(build_atoms),
        quality_tier=config.quality_tier,
    )

    try:
        result = claude.call_json(
            system=P5_SKILL_SYSTEM, user=user_prompt,
            max_tokens=4096, phase="p5",
        )
        content = result.get("content", "")
        if content:
            return content
        raise PhaseError("p5", "Claude returned empty SKILL.md")
    except PhaseError:
        raise
    except Exception as e:
        logger.warn(
            f"Claude SKILL.md failed: {e} — using fallback",
            phase="p5",
        )
        return _generate_fallback_skill(config, pillars, build_atoms)


def _generate_fallback_skill(config: BuildConfig, pillars: dict,
                             atoms: list) -> str:
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
        lines.append(
            f"- **{name}** — {len(pillar_atoms)} atoms "
            f"-> `knowledge/{name}.md`"
        )
    lines.append("")
    lines.append("## Usage")
    lines.append("")
    lines.append(
        "Load this skill to access structured knowledge "
        "from analyzed video transcripts."
    )
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
