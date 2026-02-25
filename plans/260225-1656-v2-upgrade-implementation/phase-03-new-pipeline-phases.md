# Phase 3: New Pipeline Phases

## Context Links
- Source: `UPGRADE-PLAN-FINAL.md` Tasks 4A-4D, 4H, 5
- Sprint: 2 (Core Features)
- Patches: P1, P2, P3, P6, P7, P9

## Overview
- **Priority**: P0
- **Status**: complete
- **Description**: Create P6 optimizer phase, P55 smoke test, update runner.py with PHASES list + P55 inline + resume, add logger guard
- **Estimated effort**: 3-4 days
- **This is the largest and most critical phase of the upgrade**

## Dependencies
- **Depends on**: Phase 2 (needs PHASE_MODEL_MAP, phase_model_hints, skip_optimize in types.py)
- **Blocks**: Phase 4, Phase 5

## File Ownership

| File | Action | Task |
|------|--------|------|
| `pipeline/prompts/p6_optimize_prompts.py` | **CREATE** | Task 4A |
| `pipeline/phases/p6_optimize.py` | **CREATE** | Task 4B |
| `pipeline/core/types.py` | **MODIFY** PhaseId enum (add P6) | Task 4C |
| `pipeline/orchestrator/runner.py` | **MODIFY** PHASES list, P55 inline, resume | Task 4D |
| `pipeline/core/logger.py` | **MODIFY** phase_start guard | Task 4H |
| `pipeline/phases/p55_smoke_test.py` | **CREATE** | Task 5 |

**Conflict note**: `types.py` was modified in Phase 2. Phase 3 adds PhaseId enum entry -- non-overlapping change.

## Key Insights

### Critical Patches Applied
- **P1**: Use `import yaml` (PyYAML) for `_extract_description` and `_replace_description` -- regex returns `">"` on production SKILL.md with folded block scalars
- **P2**: Remove `RUNS_PER_QUERY` -- cache + temp=0 = deterministic, running twice = same result. Saves 50% API cost
- **P3**: Use 7 decoy skills (not 3) for realistic trigger simulation
- **P6**: Logger guard prevents `phase_start("p55")` which would break frontend parseInt
- **P7**: `resume_after_resolve` must include "p6" in resume phases
- **P9**: P55 is Option A -- inline sub-step of P5, NOT in PHASES array, NOT in INITIAL_PHASES

### P55 Architecture (CRITICAL)
```
P55 is a SUB-STEP of P5, NOT a separate phase.
- P55 NOT in Python PHASES list
- P55 NOT in TypeScript PHASES/INITIAL_PHASES
- P55 does NOT call logger.phase_start() or phase_complete()
- P55 is called INLINE in runner.py after P5 completes
- Stepper UI shows: P0 > P1 > P2 > P3 > P4 > P5 > P6 (7 phases)
- P55 logs under phase="p5"
```

## Implementation Steps

### Task 4A: Create p6_optimize_prompts.py (UPGRADE-PLAN lines 640-755)

Create `pipeline/prompts/p6_optimize_prompts.py` with 4 prompt pairs:

```python
"""Phase 6 -- Optimize: Test and improve SKILL.md description for triggering accuracy."""

P6_GENERATE_EVALS_SYSTEM = """..."""   # Lines 646-668
P6_GENERATE_EVALS_USER = """..."""     # Lines 670-686
P6_SIMULATE_TRIGGER_SYSTEM = """...""" # Lines 688-702
P6_SIMULATE_TRIGGER_USER = """..."""   # Lines 704-712
P6_IMPROVE_DESCRIPTION_SYSTEM = """...""" # Lines 714-734
P6_IMPROVE_DESCRIPTION_USER = """..."""   # Lines 736-755
```

Key template variables: `{count}`, `{positive_count}`, `{negative_count}`, `{name}`, `{domain}`, `{description}`, `{topics}`, `{query}`, `{skills_list}`, `{current_description}`, `{score}`, `{results_detail}`, `{history}`

### Task 4B: Create p6_optimize.py (UPGRADE-PLAN lines 758-1156)

Create `pipeline/phases/p6_optimize.py` -- full implementation from UPGRADE-PLAN.

**Constants**:
```python
ITERATIONS_BY_TIER = {"draft": 2, "standard": 3, "premium": 5}
EVAL_COUNT = 20

# PATCH P3: 7 decoy skills
DECOY_SKILLS = [
    ("general-knowledge", "Use for general questions..."),
    ("code-helper", "Use for programming..."),
    ("web-search", "Use when user needs current info..."),
    ("data-analysis", "Use for data processing..."),
    ("writing-assistant", "Use for drafting..."),
    ("math-solver", "Use for calculations..."),
    ("language-translator", "Use for translation..."),
]
```

**Main function**: `run_p6(config, claude, cache, lookup, logger) -> PhaseResult`

**Helper functions** (all from UPGRADE-PLAN):
- `_extract_description(skill_md)` -- **PATCH P1**: Uses `yaml.safe_load()`, NOT regex
- `_replace_description(skill_md, new_description)` -- **PATCH P1**: Uses `yaml.dump()`
- `_load_topics(output_dir)` -- reads inventory.json
- `_generate_eval_queries(claude, name, domain, description, topics, logger)` -- generates 20 queries
- `_split_eval_set(eval_set, holdout=0.4, seed=42)` -- stratified 60/40 split
- `_build_skills_list(skill_name, description)` -- target + 7 decoys
- `_evaluate_description(claude, skill_name, description, eval_set, logger)` -- **PATCH P2**: single run per query
- `_calc_score(results)` -- correct/total
- `_improve_description(claude, name, domain, current, score, results, history, logger)` -- Claude generates new description

**P6 Workflow**:
1. Read SKILL.md, extract description via PyYAML
2. Generate 20 eval queries (10 positive, 10 negative)
3. Split 60/40 train/test
4. Loop: evaluate all queries, track best by TEST score, improve from TRAIN failures
5. Apply best description back to SKILL.md via PyYAML
6. Save optimization report JSON

### Task 4C: Add P6 to PhaseId enum (UPGRADE-PLAN lines 1158-1169)

In `pipeline/core/types.py`, update PhaseId enum:

```python
class PhaseId(str, Enum):
    P0_BASELINE = "p0"
    P1_AUDIT = "p1"
    P2_EXTRACT = "p2"
    P3_DEDUP = "p3"
    P4_VERIFY = "p4"
    P5_BUILD = "p5"
    P6_OPTIMIZE = "p6"
```

### Task 4D: Update runner.py (UPGRADE-PLAN lines 1171-1239)

1. Add imports:
```python
from ..phases.p6_optimize import run_p6
from ..phases.p55_smoke_test import run_p55
```

2. Update PHASES list (P55 NOT here):
```python
PHASES = [
    ("p0", "Baseline", run_p0),
    ("p1", "Audit", run_p1),
    ("p2", "Extract", run_p2),
    ("p3", "Deduplicate", run_p3),
    ("p4", "Verify", run_p4),
    ("p5", "Build", run_p5),
    ("p6", "Optimize", run_p6),
]
```

3. **PATCH P7**: Update resume_after_resolve:
```python
resume_phases = [p for p in PHASES if p[0] in ("p4", "p5", "p6")]
```

4. Add P55 inline call in run() loop -- AFTER early returns for failed/paused:
```python
# After: if result.status == "failed": ... return
# After: if state.is_paused: ... return
# HERE:
if phase_id == "p5" and result.status == "done":
    try:
        p55_result = run_p55(self.config, self.claude, self.cache, self.lookup, self.logger)
        update_state_with_result(state, p55_result)
        save_checkpoint(state, self.config.output_dir)
    except Exception as e:
        self.logger.warn(f"Smoke test error (non-fatal): {e}")
```

5. Same P55 inline in `resume_after_resolve()` after P5.

### Task 4H: Logger guard (UPGRADE-PLAN lines 1300-1317)

In `pipeline/core/logger.py`, modify `phase_start`:

```python
def phase_start(self, phase: str, name: str, tool: str = "Claude") -> None:
    # Sub-phase IDs (e.g. "p55") must NOT use phase_start
    if len(phase) > 2:
        self.warn(f"Skipping phase_start for sub-phase '{phase}' -- use info() instead")
        return
    self._emit({"event": "phase", "phase": phase, "name": name,
                 "status": "running", "progress": 0})
    self.info(f"Starting {name} phase ({tool})...", phase=phase)
```

### Task 5: Create p55_smoke_test.py (UPGRADE-PLAN lines 1344-1560)

Create `pipeline/phases/p55_smoke_test.py` -- full implementation.

**Critical rules**:
- `phase = "p5"` (logs under P5, NOT p55)
- NEVER call `logger.phase_start("p55", ...)` or `logger.phase_complete("p55", ...)`
- Returns `PhaseResult(phase_id="p55", ...)` but this is internal only

**Constants**:
```python
SMOKE_TEST_COUNT = 5
PASS_THRESHOLD = 0.6
```

**Inline prompts** (not in separate file):
- `GENERATE_PROMPTS_SYSTEM/USER` -- generate 5 test prompts
- `GRADE_RESPONSE_SYSTEM/USER` -- grade AI response vs expected facts

**Workflow**:
1. Read SKILL.md + sample atoms
2. Generate 5 test prompts via Claude
3. For each: run with skill context, grade response
4. Save smoke_test_report.json
5. Non-blocking: always continue to P6

## Validation

```bash
# Python unit tests
cd pipeline && python -m pytest tests/ -x -v

# Import check
python -c "
from pipeline.phases.p6_optimize import run_p6, _extract_description, _replace_description
from pipeline.phases.p55_smoke_test import run_p55
from pipeline.core.types import PhaseId, PHASE_MODEL_MAP
print('All imports OK')
"

# PyYAML extract test (if production data available)
python -c "
from pipeline.phases.p6_optimize import _extract_description
md = '---\nname: test\ndescription: >\n  Multi-line\n  folded scalar\n---\n# Body'
desc = _extract_description(md)
assert desc == 'Multi-line folded scalar', f'Got: {desc}'
print('PyYAML folded scalar OK')
"

# Logger guard test
python -c "
from pipeline.core.logger import PipelineLogger
import io, sys
logger = PipelineLogger('test')
old = sys.stdout; sys.stdout = io.StringIO()
logger.phase_start('p55', 'Test')
output = sys.stdout.getvalue(); sys.stdout = old
assert '\"event\": \"phase\"' not in output, 'Guard failed!'
print('Guard works')
"
```

## TODO
- [ ] Task 4A: Create p6_optimize_prompts.py (4 prompt pairs)
- [ ] Task 4B: Create p6_optimize.py (main function + 9 helpers)
- [ ] Task 4C: Add P6_OPTIMIZE to PhaseId enum in types.py
- [ ] Task 4D: Update runner.py PHASES list (add P6)
- [ ] Task 4D: Add P55 inline call after P5 in run()
- [ ] Task 4D: Add P55 inline call after P5 in resume_after_resolve()
- [ ] Task 4D: Update resume_phases to include "p6"
- [ ] Task 4H: Add sub-phase guard to logger.phase_start()
- [ ] Task 5: Create p55_smoke_test.py
- [ ] Run pytest -- all tests pass
- [ ] Verify PyYAML extract on folded scalar
- [ ] Verify logger guard blocks p55

## Success Criteria
- P6 and P55 can be imported without errors
- Logger guard prevents phase events for sub-phases
- runner.py PHASES list has 7 entries (p0-p6)
- P55 NOT in PHASES list
- All existing tests pass
- PyYAML correctly extracts folded block scalar descriptions

## Risk Assessment
- **High**: runner.py is the most complex modification -- test thoroughly after every change
- **High**: PyYAML parsing must handle all YAML scalar styles (quoted, unquoted, folded `>`, literal `|`)
- **Medium**: P6 imports from seekers.cache and seekers.lookup -- verify these exist

## Security Considerations
- `_extract_description` uses `yaml.safe_load()` (not `yaml.load()`) -- safe against YAML deserialization attacks
- File path construction uses `os.path.join` -- no path traversal risk
