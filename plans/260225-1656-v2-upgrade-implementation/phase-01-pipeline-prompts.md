# Phase 1: Pipeline Prompts

## Context Links
- Source: `UPGRADE-PLAN-FINAL.md` Tasks 1, 2, 3
- Sprint: 1 (Quick Wins)

## Overview
- **Priority**: P0-P1
- **Status**: complete
- **Description**: Rewrite P5 build prompts for "pushy" descriptions, add progressive disclosure enforcer to p5_build.py, rewrite WHY-driven prompts for P1-P4
- **Estimated effort**: 2.5 days
- **Can run in parallel**: Task 1 + Task 3 touch different files. Task 2 touches p5_build.py (shared with Task 10 in Phase 6 -- Phase 6 runs later so no conflict)

## Dependencies
- **Depends on**: none
- **Blocks**: Phase 2

## File Ownership

| File | Action | Task |
|------|--------|------|
| `pipeline/prompts/p5_build_prompts.py` | **REPLACE entire content** | Task 1 |
| `pipeline/phases/p5_build.py` | **ADD function** `_enforce_progressive_disclosure` | Task 2 |
| `pipeline/prompts/p1_audit_prompts.py` | **REPLACE** `P1_SYSTEM` | Task 3A |
| `pipeline/prompts/p2_extract_prompts.py` | **REPLACE** `P2_SYSTEM`, `P2_GAP_SYSTEM`, `P2_CODE_SYSTEM` | Task 3B |
| `pipeline/prompts/p3_dedup_prompts.py` | **REPLACE** `P3_SYSTEM` | Task 3C |
| `pipeline/prompts/p4_verify_prompts.py` | **REPLACE** `P4_SYSTEM`, `P4_BATCH_VERIFY_SYSTEM` | Task 3D |

## Key Insights
- Prompts use WHY-before-WHAT pattern to improve Claude reasoning
- P5 prompts add "pushy" description generation optimized for skill triggering
- Progressive disclosure enforcer validates L1/L2/L3 constraints (description chars, body lines, knowledge file TOC)
- Keep ALL existing variable placeholders (`{domain}`, `{language}`, etc.) unchanged
- Keep ALL existing JSON output formats unchanged -- only rewrite SYSTEM prompts

## Implementation Steps

### Task 1: Rewrite P5 Build Prompts (UPGRADE-PLAN lines 75-206)

1. Open `pipeline/prompts/p5_build_prompts.py`
2. Replace ENTIRE file content with code from UPGRADE-PLAN lines 85-205
3. Key changes:
   - `P5_SKILL_SYSTEM`: Now explains triggering context, pushy description rules, 80-200 words / <1024 chars
   - `P5_SKILL_USER`: Added DESCRIPTION WRITING GUIDE with example, returns JSON `{description, content, metadata}`
   - `P5_KNOWLEDGE_SYSTEM`: Added WHY THIS STRUCTURE MATTERS section
   - `P5_KNOWLEDGE_USER`: Unchanged format

```python
# P5_SKILL_SYSTEM key additions:
# - "CRITICAL CONTEXT -- Why description matters" section
# - "Claude has a tendency to NOT invoke skills" framing
# - Description rules: imperative form, USER INTENT focus, 80-200 words, <1024 chars
# - "Do NOT use for..." exclusion pattern
```

### Task 2: Progressive Disclosure Enforcer (UPGRADE-PLAN lines 220-318)

1. Open `pipeline/phases/p5_build.py`
2. Add function `_enforce_progressive_disclosure` BEFORE `_generate_fallback_skill` (around line 997)
3. Function signature:

```python
def _enforce_progressive_disclosure(
    skill_content: str,
    description: str,
    knowledge_files: dict[str, str],
    logger: PipelineLogger,
) -> tuple[str, list[str]]:
```

4. Three checks:
   - L1: Description 80-200 words, <1024 chars
   - L2: SKILL.md body <500 lines (excluding frontmatter)
   - L3: Knowledge files >300 lines should have TOC
5. Integration: Call in `run_p5()` AFTER generating SKILL.md + knowledge files, BEFORE writing to disk:

```python
description = result.get("description", "") if isinstance(result, dict) else ""
skill_content, pd_warnings = _enforce_progressive_disclosure(
    skill_content, description, knowledge_files, logger
)
```

### Task 3: WHY-Driven Prompt Rewrite (UPGRADE-PLAN lines 321-529)

**3A. P1 Audit** (`p1_audit_prompts.py`):
- Replace `P1_SYSTEM` with WHY-driven version (lines 334-359)
- Adds: WHY THIS MATTERS, YOUR APPROACH (4 steps), DEPTH SCORING GUIDE

**3B. P2 Extract** (`p2_extract_prompts.py`):
- Replace `P2_SYSTEM` with WHY KNOWLEDGE ATOMS explanation (lines 365-391)
- Replace `P2_GAP_SYSTEM` with WHY GAP-FILLING section (lines 396-411)
- Replace `P2_CODE_SYSTEM` with WHY CODE PATTERNS section (lines 416-439)

**3C. P3 Dedup** (`p3_dedup_prompts.py`):
- Replace `P3_SYSTEM` with DECISION FRAMEWORK + CONSERVATIVE APPROACH (lines 445-470)

**3D. P4 Verify** (`p4_verify_prompts.py`):
- Replace `P4_SYSTEM` with WHY VERIFICATION MATTERS + outcomes (lines 476-501)
- Replace `P4_BATCH_VERIFY_SYSTEM` with WHY BATCH VERIFICATION (lines 506-523)

## Validation

```bash
# All existing tests must still pass
cd pipeline && python -m pytest tests/ -x

# Specific P5 tests
cd pipeline && python -m pytest tests/test_phases.py -k "p5" -x

# Verify imports work
python -c "
from pipeline.prompts.p5_build_prompts import P5_SKILL_SYSTEM, P5_KNOWLEDGE_SYSTEM
from pipeline.prompts.p1_audit_prompts import P1_SYSTEM
from pipeline.prompts.p2_extract_prompts import P2_SYSTEM
from pipeline.prompts.p3_dedup_prompts import P3_SYSTEM
from pipeline.prompts.p4_verify_prompts import P4_SYSTEM
print('All prompt imports OK')
"
```

## TODO
- [ ] Task 1: Replace p5_build_prompts.py content
- [ ] Task 2: Add _enforce_progressive_disclosure to p5_build.py
- [ ] Task 2: Integrate enforcer call in run_p5()
- [ ] Task 3A: Rewrite P1_SYSTEM
- [ ] Task 3B: Rewrite P2_SYSTEM, P2_GAP_SYSTEM, P2_CODE_SYSTEM
- [ ] Task 3C: Rewrite P3_SYSTEM
- [ ] Task 3D: Rewrite P4_SYSTEM, P4_BATCH_VERIFY_SYSTEM
- [ ] Run pytest -- all tests pass
- [ ] Verify all prompt imports

## Success Criteria
- All existing tests pass unchanged
- Prompt strings contain WHY sections
- Progressive disclosure function produces warnings for edge cases
- No variable placeholder changes (backward compatible)

## Risk Assessment
- **Low**: Prompt-only changes are safe -- no logic changes
- **Medium**: Progressive disclosure integration point in run_p5() needs careful placement -- must be AFTER content generation, BEFORE disk write
