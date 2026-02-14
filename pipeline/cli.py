#!/usr/bin/env python3
"""
Mock Skill Factory CLI for testing the web UI.
Simulates a 6-phase build pipeline with JSON log output.
Usage: python mock_cli.py build --config config.yaml --output ./output --json-logs
"""

import json
import sys
import time
import random
import os
import argparse


def log(event, **kwargs):
    """Print JSON log line to stdout."""
    data = {"event": event, **kwargs}
    print(json.dumps(data), flush=True)


def simulate_phase(phase_id, phase_name, tool, duration_range=(3, 8)):
    """Simulate a pipeline phase with progress updates."""
    duration = random.uniform(*duration_range)
    steps = random.randint(5, 15)
    atoms_found = 0

    log("phase", phase=phase_id, name=phase_name, status="running", progress=0)
    log("log", level="info", phase=phase_id,
        message=f"Starting {phase_name} phase using {tool}...")

    for i in range(steps):
        time.sleep(duration / steps)
        progress = int(((i + 1) / steps) * 100)

        messages = [
            f"Processing document chunk {i+1}/{steps}...",
            f"Analyzing content with {tool}...",
            f"Found {random.randint(5, 30)} knowledge atoms",
            f"Validating extracted data...",
            f"Cross-referencing with baseline...",
            f"Deduplicating similar entries...",
            f"Scoring quality metrics...",
        ]

        log("log", level="info", phase=phase_id,
            message=random.choice(messages))

        if progress % 25 == 0:
            log("phase", phase=phase_id, name=phase_name,
                status="running", progress=progress)

        atoms_found += random.randint(10, 50)

    score = random.uniform(78, 98)
    log("quality", phase=phase_id, score=round(score, 1),
        **{"pass": score >= 70}, atoms_count=atoms_found)

    log("phase", phase=phase_id, name=phase_name,
        status="done", progress=100)
    log("log", level="info", phase=phase_id,
        message=f"{phase_name} complete: {atoms_found} atoms, quality {score:.1f}%")

    return atoms_found, score


def main():
    parser = argparse.ArgumentParser(description="Skill Factory CLI (Mock)")
    parser.add_argument("command", choices=["build"], help="Command to run")
    parser.add_argument("--config", required=True, help="Config YAML path")
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument("--json-logs", action="store_true", help="JSON log output")
    args = parser.parse_args()

    log("log", level="info", message="Skill Factory CLI v1.0 (Mock)")
    log("log", level="info", message=f"Config: {args.config}")
    log("log", level="info", message=f"Output: {args.output}")

    if os.path.exists(args.config):
        with open(args.config) as f:
            log("log", level="info", message=f"Config loaded: {len(f.read())} bytes")

    os.makedirs(args.output, exist_ok=True)

    total_atoms = 0
    total_cost = 0
    all_scores = []

    phases = [
        ("p0", "Baseline", "Seekers", (2, 4)),
        ("p1", "Audit", "Claude", (3, 6)),
        ("p2", "Extract", "Claude", (5, 10)),
        ("p3", "Deduplicate", "Claude+Seekers", (4, 8)),
        ("p4", "Verify", "Seekers+Claude", (4, 8)),
        ("p5", "Architect", "Claude+Seekers", (3, 6)),
    ]

    for idx, (phase_id, name, tool, duration) in enumerate(phases):
        atoms, score = simulate_phase(phase_id, name, tool, duration)
        total_atoms += atoms
        all_scores.append(score)

        phase_cost = round(random.uniform(0.5, 2.5), 2)
        total_cost += phase_cost
        phase_tokens = random.randint(10000, 50000)
        log("cost", api_cost_usd=round(total_cost, 2),
            tokens_used=phase_tokens * (idx + 1))

    final_score = round(sum(all_scores) / len(all_scores), 1)
    log("quality", quality_score=final_score,
        atoms_extracted=total_atoms,
        atoms_deduplicated=int(total_atoms * 0.6),
        atoms_verified=int(total_atoms * 0.55),
        compression_ratio=round(random.uniform(0.08, 0.15), 3))

    # Generate mock output files
    skill_md_path = os.path.join(args.output, "SKILL.md")
    with open(skill_md_path, "w") as f:
        f.write(f"# Mock Skill\n\nGenerated at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"\n## Stats\n- Atoms: {total_atoms}\n- Quality: {final_score}%\n")
        f.write(f"- Cost: ${total_cost:.2f}\n")

    knowledge_dir = os.path.join(args.output, "knowledge")
    os.makedirs(knowledge_dir, exist_ok=True)
    with open(os.path.join(knowledge_dir, "atoms.json"), "w") as f:
        json.dump({"atoms_count": total_atoms, "quality": final_score}, f)

    # Create mock zip package
    import zipfile
    zip_path = os.path.join(args.output, "package.zip")
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(skill_md_path, "SKILL.md")
        zf.write(os.path.join(knowledge_dir, "atoms.json"), "knowledge/atoms.json")

    log("package", path=zip_path, output_dir=args.output)
    log("log", level="info", message=f"Package created: {zip_path}")
    log("log", level="info",
        message=f"Build complete! Quality: {final_score}%, Atoms: {total_atoms}, Cost: ${total_cost:.2f}")


if __name__ == "__main__":
    main()
