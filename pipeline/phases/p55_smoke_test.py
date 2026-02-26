"""Phase 5.5 — Smoke Test: Validate built skill works correctly before optimization.

Generates 3-5 realistic test prompts from knowledge atoms,
runs them with SKILL.md in system context,
and checks if responses use the skill's knowledge accurately.

This is a NON-BLOCKING sub-step: failures produce warnings, not pipeline stops.

CRITICAL: Do NOT use logger.phase_start("p55", ...)
P55 is a sub-step of P5, only use logger.info()/logger.warn() with phase="p5".
If we emit a phase event, frontend parseInt("p55")=55 will break the stepper.
"""

import os
import time
import json
from typing import Optional

from ..core.types import BuildConfig, PhaseResult
from ..core.logger import PipelineLogger
from ..core.utils import read_json, write_json
from ..clients.claude_client import ClaudeClient
from ..seekers.cache import SeekersCache
from ..seekers.lookup import SeekersLookup

SMOKE_TEST_COUNT = 5
PASS_THRESHOLD = 0.6

GENERATE_PROMPTS_SYSTEM = """\
You are creating realistic test prompts to validate an AI knowledge skill.

Generate {count} test prompts that a real user would ask. Each prompt should:
1. Be specific enough that a good answer REQUIRES the skill's knowledge
2. Cover different knowledge pillars/categories
3. Vary in complexity (1 simple, 2 medium, 2 complex)
4. Use natural language (not "test the skill about X")

For each prompt, write 2-3 KEY FACTS that a correct answer must include.
OUTPUT: JSON array only.\
"""

GENERATE_PROMPTS_USER = """\
Generate {count} test prompts for this skill:

**Skill name:** {name}
**Domain:** {domain}

**Sample knowledge atoms:**
{sample_atoms}

Return JSON array:
[
  {{
    "prompt": "A realistic user question",
    "expected_facts": ["Fact the answer must include", "Another required fact"],
    "category": "Which knowledge pillar this tests",
    "complexity": "simple|medium|complex"
  }}
]
"""

GRADE_RESPONSE_SYSTEM = """\
You are grading an AI assistant's response to check if it correctly used knowledge from a skill.
Check if the response contains the expected facts. Be generous — facts don't need to be verbatim.
OUTPUT: JSON only.\
"""

GRADE_RESPONSE_USER = """\
**Question:** {prompt}
**Expected facts:** {expected_facts}
**AI response:** {response}

{{
  "results": [
    {{"fact": "expected fact", "present": true, "evidence": "where in response"}}
  ],
  "overall_pass": true,
  "score": 0.8,
  "notes": "Brief assessment"
}}
"""


def run_p55(
    config: BuildConfig, claude: Optional[ClaudeClient],
    cache: SeekersCache, lookup: SeekersLookup, logger: PipelineLogger,
) -> PhaseResult:
    """Run P5.5 Smoke Test (non-blocking sub-step).

    Logs under phase="p5" — NEVER use phase_start/phase_complete with "p55".
    """
    phase = "p5"  # Sub-step — log under p5, NOT p55
    started = time.time()
    logger.info("Running Smoke Test...", phase=phase)

    if not claude:
        logger.warn("Smoke test skipped — no Claude client", phase=phase)
        return PhaseResult(phase_id="p55", status="skipped")

    # Read model hint
    use_light = config.phase_model_hints.get("p55", True)

    try:
        skill_path = os.path.join(config.output_dir, "SKILL.md")
        if not os.path.exists(skill_path):
            return PhaseResult(phase_id="p55", status="skipped", error_message="SKILL.md not found")
        with open(skill_path, 'r', encoding='utf-8') as f:
            skill_content = f.read()

        # Load atoms for context
        sample_atoms = "Not available"
        for atoms_file in ["atoms_verified.json", "atoms_deduplicated.json"]:
            atoms_path = os.path.join(config.output_dir, atoms_file)
            if os.path.exists(atoms_path):
                data = read_json(atoms_path)
                atoms = data.get("atoms", [])[:10]
                sample_atoms = json.dumps(
                    [{"title": a.get("title", ""), "content": a.get("content", "")[:200]} for a in atoms],
                    ensure_ascii=False, indent=2,
                )
                break

        # Step 1: Generate test prompts
        logger.info("Generating smoke test prompts...", phase=phase)
        test_prompts = claude.call_json(
            system=GENERATE_PROMPTS_SYSTEM.format(count=SMOKE_TEST_COUNT),
            user=GENERATE_PROMPTS_USER.format(
                count=SMOKE_TEST_COUNT, name=config.name,
                domain=config.domain, sample_atoms=sample_atoms,
            ),
            max_tokens=2048, phase=phase, use_light_model=use_light,
        )
        if isinstance(test_prompts, dict):
            test_prompts = test_prompts.get("prompts", test_prompts.get("tests", []))
        if not isinstance(test_prompts, list) or not test_prompts:
            logger.warn("Could not generate test prompts — skipping", phase=phase)
            return PhaseResult(phase_id="p55", status="skipped")

        # Step 2: Run and grade each test
        results = []
        for i, test in enumerate(test_prompts[:SMOKE_TEST_COUNT]):
            prompt = test.get("prompt", "")
            expected = test.get("expected_facts", [])
            if not prompt:
                continue
            logger.info(f"  Test {i+1}/{min(len(test_prompts), SMOKE_TEST_COUNT)}: {prompt[:60]}...", phase=phase)

            response = claude.call(
                system=f"You have access to this knowledge skill:\n\n{skill_content[:3000]}",
                user=prompt, max_tokens=1024, phase=phase,
            )
            grade = claude.call_json(
                system=GRADE_RESPONSE_SYSTEM,
                user=GRADE_RESPONSE_USER.format(
                    prompt=prompt,
                    expected_facts=json.dumps(expected, ensure_ascii=False),
                    response=response[:2000],
                ),
                max_tokens=1024, phase=phase, use_light_model=True,
            )
            passed = grade.get("overall_pass", False)
            score = grade.get("score", 0)
            results.append({
                "prompt": prompt, "expected_facts": expected,
                "response": response,
                "response_preview": response[:300],
                "passed": passed, "score": score,
                "grade_notes": grade.get("notes", ""),
                "grade_results": grade.get("results", []),
                "category": test.get("category", ""),
                "complexity": test.get("complexity", ""),
            })
            logger.info(f"  {'PASS' if passed else 'FAIL'} Score: {score:.0%}", phase=phase)

        # Step 3: Overall result
        pass_count = sum(1 for r in results if r["passed"])
        total = len(results)
        overall_score = pass_count / total if total > 0 else 0

        report = {
            "pass_count": pass_count, "total": total,
            "score": overall_score, "passed": overall_score >= PASS_THRESHOLD,
            "threshold": PASS_THRESHOLD, "results": results,
        }
        report_path = os.path.join(config.output_dir, "smoke_test_report.json")
        write_json(report, report_path)

        status_emoji = "PASS" if overall_score >= PASS_THRESHOLD else "WARN"
        logger.info(f"Smoke Test {status_emoji}: {pass_count}/{total} passed ({overall_score:.0%})", phase=phase)

        if overall_score < PASS_THRESHOLD:
            logger.warn("Smoke test below threshold — skill may need manual review", phase=phase)

        return PhaseResult(
            phase_id="p55", status="done",
            duration_seconds=round(time.time() - started, 1),
            quality_score=round(overall_score * 100, 1),
            output_files=[report_path],
            metrics={"pass_count": pass_count, "total": total, "overall_pass": overall_score >= PASS_THRESHOLD},
        )

    except Exception as e:
        logger.warn(f"Smoke test error (non-fatal): {e}", phase=phase)
        return PhaseResult(phase_id="p55", status="skipped", error_message=str(e))
