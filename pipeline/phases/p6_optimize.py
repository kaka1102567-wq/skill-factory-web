"""Phase 6 — Optimize: Test and improve SKILL.md description for triggering accuracy.

Workflow:
1. Read SKILL.md → extract current description (via PyYAML, NOT regex)
2. Generate 20 eval queries (10 should-trigger, 10 should-not)
3. Simulate triggering: for each query, ask Claude if it would invoke this skill
4. Score: accuracy = correct_decisions / total_queries
5. If score < 100%: call Claude to improve description
6. Repeat up to max_iterations
7. Pick best description (by TEST score), update SKILL.md

CRITICAL PATCHES APPLIED:
- PyYAML for YAML parsing (regex returns ">" on production folded block scalars)
- Single run per query (cache_key=SHA256(system+user) + temperature=0.0 = deterministic)
- 7 decoy skills for realistic simulation (3 decoys overestimates accuracy)
"""

import os
import re
import json
import time
import random
import yaml
from typing import Optional

from ..core.types import BuildConfig, PhaseResult
from ..core.logger import PipelineLogger
from ..core.errors import PhaseError
from ..core.utils import read_json, write_json
from ..clients.claude_client import ClaudeClient
from ..seekers.cache import SeekersCache
from ..seekers.lookup import SeekersLookup
from ..prompts.p6_optimize_prompts import (
    P6_GENERATE_EVALS_SYSTEM, P6_GENERATE_EVALS_USER,
    P6_SIMULATE_TRIGGER_SYSTEM, P6_SIMULATE_TRIGGER_USER,
    P6_IMPROVE_DESCRIPTION_SYSTEM, P6_IMPROVE_DESCRIPTION_USER,
)

ITERATIONS_BY_TIER = {"draft": 2, "standard": 3, "premium": 5}
EVAL_COUNT = 20

# 7 decoy skills for realistic competition
DECOY_SKILLS = [
    ("general-knowledge", "Use for general questions that don't require specialized skills."),
    ("code-helper", "Use for programming, coding, debugging, and software development questions."),
    ("web-search", "Use when the user needs current information, news, or real-time data from the internet."),
    ("data-analysis", "Use for data processing, statistics, CSV/Excel analysis, and visualization."),
    ("writing-assistant", "Use for drafting emails, essays, blog posts, and professional documents."),
    ("math-solver", "Use for calculations, equations, algebra, calculus, and mathematical proofs."),
    ("language-translator", "Use for translation between languages, grammar correction, and localization."),
]


def run_p6(
    config: BuildConfig, claude: Optional[ClaudeClient],
    cache: SeekersCache, lookup: SeekersLookup, logger: PipelineLogger,
) -> PhaseResult:
    """Run P6 Description Optimization."""
    phase = "p6"
    started = time.time()
    logger.phase_start(phase, "Optimize", tool="Claude")

    if config.skip_optimize:
        logger.info("P6 skipped (skip_optimize=True)", phase=phase)
        return PhaseResult(phase_id=phase, status="skipped")

    if not claude:
        logger.phase_failed(phase, "Optimize", "Claude client required")
        return PhaseResult(phase_id=phase, status="failed",
                           error_message="Claude client required for P6")

    use_light = config.phase_model_hints.get("p6", False)
    cost_before = claude.total_cost_usd
    tokens_before = claude.total_input_tokens + claude.total_output_tokens

    try:
        # Step 1: Read current SKILL.md
        skill_path = os.path.join(config.output_dir, "SKILL.md")
        if not os.path.exists(skill_path):
            raise PhaseError(phase, "SKILL.md not found — run P5 first")

        with open(skill_path, 'r', encoding='utf-8') as f:
            skill_content = f.read()

        current_description = _extract_description(skill_content)
        if not current_description:
            raise PhaseError(phase, "Could not extract description from SKILL.md")

        # Use template pre-optimized description as starting point if available
        if config.template_optimized_description:
            current_description = config.template_optimized_description
            logger.info("Using template pre-optimized description as starting point", phase=phase)

        logger.info(
            f"Current description: {len(current_description)} chars, "
            f"{len(current_description.split())} words", phase=phase,
        )
        logger.phase_progress(phase, "Optimize", 10)

        # Step 2: Load topics from P1 inventory
        topics = _load_topics(config.output_dir)

        # Step 3: Generate eval queries
        logger.info("Generating evaluation queries...", phase=phase)
        eval_set = _generate_eval_queries(
            claude, config.name, config.domain, current_description, topics, logger
        )
        pos = sum(1 for e in eval_set if e.get('should_trigger'))
        neg = len(eval_set) - pos
        logger.info(f"Generated {len(eval_set)} eval queries ({pos} positive, {neg} negative)", phase=phase)
        logger.phase_progress(phase, "Optimize", 25)

        # Step 4: Train/test split (60/40)
        train_set, test_set = _split_eval_set(eval_set, holdout=0.4)
        logger.info(f"Split: {len(train_set)} train, {len(test_set)} test", phase=phase)

        # Step 5: Optimization loop
        max_iters = ITERATIONS_BY_TIER.get(config.quality_tier, 3)
        history = []
        best_description = current_description
        best_test_score = 0.0
        best_train_score = 0.0

        for iteration in range(1, max_iters + 1):
            progress = 25 + int(70 * iteration / max_iters)
            logger.phase_progress(phase, "Optimize", min(progress, 95))
            logger.info(f"--- Iteration {iteration}/{max_iters} ---", phase=phase)

            # Evaluate on ALL queries in one pass
            all_results = _evaluate_description(
                claude, config.name, current_description,
                train_set + test_set, logger,
            )

            train_queries = {q["query"] for q in train_set}
            train_results = [r for r in all_results if r["query"] in train_queries]
            test_results = [r for r in all_results if r["query"] not in train_queries]

            train_score = _calc_score(train_results)
            test_score = _calc_score(test_results)
            logger.info(f"Scores — train: {train_score:.0%}, test: {test_score:.0%}", phase=phase)

            if test_score > best_test_score or (
                test_score == best_test_score and train_score > best_train_score
            ):
                best_description = current_description
                best_test_score = test_score
                best_train_score = train_score

            history.append({
                "iteration": iteration,
                "description": current_description,
                "train_score": train_score,
                "test_score": test_score,
                "train_results": train_results,
            })

            if train_score >= 1.0:
                logger.info("Perfect train score — stopping early", phase=phase)
                break

            if iteration == max_iters:
                break

            # Improve based on TRAIN results only (blinded)
            logger.info("Improving description...", phase=phase)
            current_description = _improve_description(
                claude, config.name, config.domain, current_description,
                train_score, train_results, history, logger,
            )
            logger.info(f"New description: {len(current_description)} chars", phase=phase)

        # Step 6: Apply best description
        logger.info(
            f"Best description (test={best_test_score:.0%}, train={best_train_score:.0%})",
            phase=phase,
        )
        updated_content = _replace_description(skill_content, best_description)
        with open(skill_path, 'w', encoding='utf-8') as f:
            f.write(updated_content)

        # Save optimization report
        report = {
            "best_description": best_description,
            "original_description": _extract_description(skill_content),
            "best_train_score": best_train_score,
            "best_test_score": best_test_score,
            "iterations": len(history),
            "eval_set": eval_set,
            "history": [
                {"iteration": h["iteration"], "description": h["description"],
                 "train_score": h["train_score"], "test_score": h["test_score"]}
                for h in history
            ],
        }
        report_path = os.path.join(config.output_dir, "p6_optimization_report.json")
        write_json(report, report_path)

        cost_delta = claude.total_cost_usd - cost_before
        tokens_delta = (claude.total_input_tokens + claude.total_output_tokens) - tokens_before

        duration = time.time() - started
        logger.phase_complete(phase, "Optimize", score=best_test_score * 100)

        return PhaseResult(
            phase_id=phase, status="done",
            started_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
            duration_seconds=round(duration, 1),
            quality_score=round(best_test_score * 100, 1),
            api_cost_usd=cost_delta,
            tokens_used=tokens_delta,
            output_files=[skill_path, report_path],
            metrics={
                "best_train_score": best_train_score,
                "best_test_score": best_test_score,
                "iterations_run": len(history),
                "eval_count": len(eval_set),
                "description_chars": len(best_description),
                "description_words": len(best_description.split()),
            },
        )

    except PhaseError:
        raise
    except Exception as e:
        logger.phase_failed(phase, "Optimize", str(e))
        return PhaseResult(phase_id=phase, status="failed", error_message=str(e),
                           duration_seconds=round(time.time() - started, 1))


# --- Helper functions ---

def _extract_description(skill_md: str) -> str:
    """Extract description from YAML frontmatter using PyYAML."""
    match = re.match(r'^---\s*\n(.*?)\n---', skill_md, re.DOTALL)
    if not match:
        return ""
    try:
        frontmatter = yaml.safe_load(match.group(1))
        if isinstance(frontmatter, dict):
            return str(frontmatter.get("description", "")).strip()
    except yaml.YAMLError:
        pass
    return ""


def _replace_description(skill_md: str, new_description: str) -> str:
    """Replace description in YAML frontmatter using PyYAML."""
    match = re.match(r'^(---\s*\n)(.*?)(\n---)', skill_md, re.DOTALL)
    if not match:
        return skill_md
    prefix, fm_text, suffix = match.group(1), match.group(2), match.group(3)
    body = skill_md[match.end():]
    try:
        frontmatter = yaml.safe_load(fm_text)
        if not isinstance(frontmatter, dict):
            return skill_md
        frontmatter["description"] = new_description
        new_fm = yaml.dump(
            frontmatter, default_flow_style=False,
            allow_unicode=True, sort_keys=False, width=120
        )
        return prefix + new_fm.rstrip('\n') + suffix + body
    except yaml.YAMLError:
        return skill_md


def _load_topics(output_dir: str) -> str:
    inv_path = os.path.join(output_dir, "inventory.json")
    if not os.path.exists(inv_path):
        return "Not available"
    try:
        data = read_json(inv_path)
        topics = data.get("topics", [])
        if isinstance(topics, list):
            return ", ".join(t.get("topic", "") for t in topics[:30] if t.get("topic"))
    except Exception:
        pass
    return "Not available"


def _generate_eval_queries(claude, name, domain, description, topics, logger):
    result = claude.call_json(
        system=P6_GENERATE_EVALS_SYSTEM.format(
            count=EVAL_COUNT, positive_count=EVAL_COUNT // 2, negative_count=EVAL_COUNT // 2,
        ),
        user=P6_GENERATE_EVALS_USER.format(
            name=name, domain=domain, description=description, topics=topics,
        ),
        max_tokens=4096, phase="p6",
    )
    if isinstance(result, list):
        return result
    if isinstance(result, dict) and "queries" in result:
        return result["queries"]
    logger.warn("Unexpected eval format — using empty set", phase="p6")
    return []


def _split_eval_set(eval_set, holdout=0.4, seed=42):
    rng = random.Random(seed)
    trigger = [e for e in eval_set if e.get("should_trigger")]
    no_trigger = [e for e in eval_set if not e.get("should_trigger")]
    rng.shuffle(trigger)
    rng.shuffle(no_trigger)
    n_t = max(1, int(len(trigger) * holdout))
    n_nt = max(1, int(len(no_trigger) * holdout))
    test = trigger[:n_t] + no_trigger[:n_nt]
    train = trigger[n_t:] + no_trigger[n_nt:]
    return train, test


def _build_skills_list(skill_name: str, description: str) -> str:
    """Build skills list with target skill + decoy skills, randomized to avoid position bias."""
    skills = [(skill_name, description)] + list(DECOY_SKILLS)
    random.shuffle(skills)
    lines = [f"{i+1}. {name}: {desc}" for i, (name, desc) in enumerate(skills)]
    return "\n".join(lines)


def _evaluate_description(claude, skill_name, description, eval_set, logger):
    """Evaluate description by simulating trigger decisions. Single run per query."""
    results = []
    skills_list = _build_skills_list(skill_name, description)

    for item in eval_set:
        query = item["query"]
        should_trigger = item.get("should_trigger", True)

        response = claude.call(
            system=P6_SIMULATE_TRIGGER_SYSTEM,
            user=P6_SIMULATE_TRIGGER_USER.format(query=query, skills_list=skills_list),
            max_tokens=50, phase="p6", use_light_model=True,
        )
        triggered = skill_name.lower() in response.lower()
        passed = triggered if should_trigger else not triggered

        results.append({
            "query": query, "should_trigger": should_trigger,
            "triggered": triggered, "pass": passed,
        })
    return results


def _calc_score(results):
    if not results:
        return 0.0
    return sum(1 for r in results if r["pass"]) / len(results)


def _improve_description(claude, name, domain, current, score, results, history, logger):
    failed = [r for r in results if not r["pass"]]
    lines = []
    for r in failed:
        direction = "MISSED" if r["should_trigger"] else "FALSE TRIGGER"
        triggered_str = "YES" if r["triggered"] else "NO"
        lines.append(f'  [{direction}] "{r["query"]}" (triggered: {triggered_str})')
    results_detail = "\n".join(lines) if lines else "All passed!"

    history_lines = []
    for h in history[-3:]:
        history_lines.append(
            f"  Iter {h['iteration']}: train={h['train_score']:.0%}, test={h['test_score']:.0%}\n"
            f'  "{h["description"][:100]}..."'
        )
    history_str = "\n".join(history_lines) if history_lines else "First attempt"

    response = claude.call(
        system=P6_IMPROVE_DESCRIPTION_SYSTEM,
        user=P6_IMPROVE_DESCRIPTION_USER.format(
            name=name, domain=domain, current_description=current,
            score=f"{score:.0%}", results_detail=results_detail, history=history_str,
        ),
        max_tokens=2048, phase="p6",
    )

    match = re.search(r'<description>(.*?)</description>', response, re.DOTALL)
    new_desc = match.group(1).strip().strip('"') if match else response.strip().strip('"')
    if len(new_desc) > 1024:
        new_desc = new_desc[:1020] + "..."
        logger.warn("Description truncated to 1024 chars", phase="p6")
    return new_desc
