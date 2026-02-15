"""Phase 5 — Build: Generate SKILL.md, knowledge files, and package zip.

Supports multi-platform packaging: claude, openclaw, antigravity.
"""

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

MAX_ANTIGRAVITY_CHARS = 50000


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


# ── Multi-platform Packagers ─────────────────────────────


def _copy_dir_tree(src: str, dst: str) -> None:
    """Copy directory tree if source exists."""
    if os.path.isdir(src):
        shutil.copytree(src, dst, dirs_exist_ok=True)


def _package_claude(platform_dir, skill_path, knowledge_dir, refs_dir):
    """Claude: SKILL.md (full frontmatter + routing) + knowledge/ + references/."""
    if os.path.exists(skill_path):
        shutil.copy2(skill_path, os.path.join(platform_dir, "SKILL.md"))
    _copy_dir_tree(knowledge_dir, os.path.join(platform_dir, "knowledge"))
    _copy_dir_tree(refs_dir, os.path.join(platform_dir, "references"))


def _package_openclaw(platform_dir, config, build_atoms, avg_confidence,
                      knowledge_dir, refs_dir):
    """OpenClaw: simplified SKILL.md (name, description, version) + knowledge/ + references/."""
    lines = [
        "---",
        f"name: {config.name}",
        f"description: Use this skill for {config.domain} knowledge.",
        'version: "1.0"',
        "---",
        "",
        f"# {config.name}",
        "",
        f"Knowledge skill for **{config.domain}** with "
        f"{len(build_atoms)} atoms, confidence {avg_confidence:.2f}.",
        "",
    ]
    write_file(os.path.join(platform_dir, "SKILL.md"), "\n".join(lines))
    _copy_dir_tree(knowledge_dir, os.path.join(platform_dir, "knowledge"))
    _copy_dir_tree(refs_dir, os.path.join(platform_dir, "references"))


def _package_antigravity(platform_dir, config, knowledge_dir, refs_dir):
    """Antigravity: single system_instructions.md with all content inlined."""
    lines = [
        f"# {config.name} — System Instructions",
        "",
        f"You are an expert in **{config.domain}**. "
        f"Use the knowledge below to answer questions accurately "
        f"in {config.language}.",
        "",
        "---",
        "",
        "## Core Knowledge",
        "",
    ]

    # Inline all knowledge files
    if os.path.isdir(knowledge_dir):
        for fname in sorted(os.listdir(knowledge_dir)):
            if fname.endswith(".md"):
                fpath = os.path.join(knowledge_dir, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if content:
                    lines.append(content)
                    lines.append("")

    lines.extend(["---", "", "## Reference Material", ""])

    # Inline references, truncate if over limit
    ref_parts = []
    if os.path.isdir(refs_dir):
        for fname in sorted(os.listdir(refs_dir)):
            if fname.endswith(".md"):
                fpath = os.path.join(refs_dir, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if content:
                    ref_parts.append(content)

    ref_text = "\n\n".join(ref_parts)
    current_text = "\n".join(lines)

    if len(current_text) + len(ref_text) > MAX_ANTIGRAVITY_CHARS:
        budget = MAX_ANTIGRAVITY_CHARS - len(current_text) - 200
        ref_text = ref_text[: max(budget, 0)]
        ref_text += "\n\n*[References truncated to fit size limit]*"

    lines.append(ref_text)
    lines.extend([
        "",
        "---",
        "",
        "## Response Guidelines",
        "",
        f"- Answer in **{config.language}**",
        "- Cite specific knowledge when answering",
        "- If unsure, acknowledge limitations",
        f"- Stay within the domain of **{config.domain}**",
        "",
    ])

    write_file(
        os.path.join(platform_dir, "system_instructions.md"),
        "\n".join(lines),
    )


def _package_for_platforms(config, output_dir, build_atoms,
                           avg_confidence, logger):
    """Distribute build output to platform-specific directories.

    Single platform → keeps flat structure (backward compatible).
    Multiple platforms → creates subdirectories per platform.
    """
    platforms = [p.lower() for p in (config.platforms or ["claude"])]

    if len(platforms) <= 1:
        return platforms  # flat structure, nothing to do

    skill_path = os.path.join(output_dir, "SKILL.md")
    knowledge_dir = os.path.join(output_dir, "knowledge")
    refs_dir = os.path.join(output_dir, "references")

    packagers = {
        "claude": lambda d: _package_claude(
            d, skill_path, knowledge_dir, refs_dir,
        ),
        "openclaw": lambda d: _package_openclaw(
            d, config, build_atoms, avg_confidence,
            knowledge_dir, refs_dir,
        ),
        "antigravity": lambda d: _package_antigravity(
            d, config, knowledge_dir, refs_dir,
        ),
    }

    for platform in platforms:
        platform_dir = os.path.join(output_dir, platform)
        os.makedirs(platform_dir, exist_ok=True)

        packager = packagers.get(platform)
        if packager:
            packager(platform_dir)
        else:
            logger.warn(
                f"Unknown platform '{platform}', skipping",
                phase="p5",
            )

    # Clean up staging files (now in platform subdirs)
    if os.path.exists(skill_path):
        os.remove(skill_path)
    if os.path.isdir(knowledge_dir):
        shutil.rmtree(knowledge_dir)
    if os.path.isdir(refs_dir):
        shutil.rmtree(refs_dir)

    platform_names = ", ".join(platforms)
    logger.info(
        f"Packaged for {len(platforms)} platforms: {platform_names}",
        phase="p5",
    )
    return platforms


def _generate_readme(config: BuildConfig, metadata: dict,
                     atoms: list, output_dir: str) -> str:
    """Generate README.md for the skill package."""
    from pathlib import Path

    total_atoms = len(atoms)
    verified = len([a for a in atoms if a.get("status") in ("verified", "updated")])
    verified_pct = round(verified / total_atoms * 100, 1) if total_atoms else 0

    knowledge_dir = Path(output_dir) / "knowledge"
    knowledge_files = sorted(knowledge_dir.glob("*.md")) if knowledge_dir.exists() else []

    refs_dir = Path(output_dir) / "references"
    ref_files = sorted(refs_dir.glob("*.md")) if refs_dir.exists() else []

    # Sources breakdown
    sources = []
    transcript_atoms = len([a for a in atoms if a.get("source") == "transcript"])
    baseline_atoms = len([a for a in atoms if a.get("source") == "baseline"])
    if transcript_atoms > 0:
        sources.append(f"{transcript_atoms} from expert transcript")
    if baseline_atoms > 0:
        sources.append(f"{baseline_atoms} from baseline documentation")

    categories = sorted(set(a.get("category", "general") for a in atoms))
    quality_score = metadata.get("avg_confidence", 0) * 100
    slug = config.name.lower().replace(" ", "-")

    lines = [
        f"# {config.name}",
        "",
        "> AI Skill Package — Generated by Skill Factory",
        "",
        "## Overview",
        "",
        f"This skill package contains **{total_atoms} knowledge atoms** extracted and verified",
        f"from expert knowledge, organized into {len(knowledge_files)} knowledge pillars",
        f"with {len(ref_files)} reference documents.",
        "",
        f"**Domain:** {config.domain}  ",
        f"**Language:** {config.language}  ",
        f"**Quality:** {quality_score:.1f}% ({config.quality_tier} tier)",
        "",
        "## Quick Start",
        "",
        "### For Claude (Anthropic)",
        "1. Copy the `claude/` folder into your Claude project",
        "2. Claude will read `SKILL.md` first for routing logic",
        "3. Knowledge files in `knowledge/` are loaded on-demand",
        "",
        "### For OpenClaw",
        "1. Copy the `openclaw/` folder into your OpenClaw skill directory",
        "",
        "### For Antigravity",
        "1. Copy `antigravity/system_instructions.md` to your Antigravity config",
        "",
        "## Package Structure",
        "",
        "```",
        f"{slug}/",
        f"├── SKILL.md              # Entry point",
        f"├── knowledge/            # {len(knowledge_files)} knowledge pillars",
    ]

    for kf in knowledge_files:
        lines.append(f"│   ├── {kf.name}")

    lines.extend([
        f"├── references/           # {len(ref_files)} source documents",
        "├── metadata.json         # Build metadata",
        "└── README.md             # This file",
        "```",
        "",
        "## Knowledge Categories",
        "",
    ])

    for cat in categories:
        cat_atoms = [a for a in atoms if a.get("category") == cat]
        lines.append(f"- **{cat.replace('_', ' ').title()}** — {len(cat_atoms)} atoms")

    lines.extend([
        "",
        "## Statistics",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total Atoms | {total_atoms} |",
        f"| Verified | {verified}/{total_atoms} ({verified_pct}%) |",
        f"| Quality Score | {quality_score:.1f}% |",
        f"| Sources | {', '.join(sources) if sources else 'N/A'} |",
        f"| Platforms | {', '.join(config.platforms)} |",
        f"| Built | {metadata.get('created_at', 'N/A')} |",
        "",
        "## How It Works",
        "",
        "This skill was built using Skill Factory's 6-phase pipeline:",
        "",
        f"1. **Baseline** — Loaded {len(ref_files)} reference documents",
        f"2. **Audit** — Mapped expert topics against baseline coverage",
        f"3. **Extract** — Extracted {total_atoms} knowledge atoms",
        "4. **Dedup** — Removed duplicates and detected conflicts",
        "5. **Verify** — Cross-referenced atoms against baseline evidence",
        f"6. **Build** — Organized into pillars and packaged for {len(config.platforms)} platform(s)",
        "",
        "## License",
        "",
        "Generated from expert knowledge. Built with Skill Factory.",
        "",
    ])

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

        # ── Step 2.5: Multi-platform packaging ──
        platforms_built = _package_for_platforms(
            config, config.output_dir, build_atoms,
            avg_confidence, logger,
        )

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
            "platforms_built": platforms_built,
            "baseline_source": "skill_seekers" if use_seekers else "legacy",
        }
        metadata_path = os.path.join(config.output_dir, "metadata.json")
        write_json(metadata, metadata_path)
        output_files.append(metadata_path)

        # ── Step 3.5: Generate README.md ──
        readme_content = _generate_readme(config, metadata, build_atoms, config.output_dir)
        if len(config.platforms) <= 1:
            write_file(os.path.join(config.output_dir, "README.md"), readme_content)
        else:
            write_file(os.path.join(config.output_dir, "README.md"), readme_content)
            for platform in config.platforms:
                pdir = os.path.join(config.output_dir, platform.lower())
                if os.path.isdir(pdir):
                    write_file(os.path.join(pdir, "README.md"), readme_content)
        logger.info("Generated README.md", phase=phase_id)

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
                "platforms_built": platforms_built,
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
