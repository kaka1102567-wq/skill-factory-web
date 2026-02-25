# Phase 2: Pipeline Core

## Context Links
- Source: `UPGRADE-PLAN-FINAL.md` Task 7
- Sprint: 1 (Quick Wins)
- Patches: P4 (config-based multi-model), P8 (document P3/P4 hardcoded)

## Overview
- **Priority**: P1
- **Status**: complete
- **Description**: Add multi-model strategy config to BuildConfig and PHASE_MODEL_MAP constant, wire model hints in runner.py
- **Estimated effort**: 0.5 days

## Dependencies
- **Depends on**: Phase 1 (prompts must be updated first -- runner imports from prompts)
- **Blocks**: Phase 3

## File Ownership

| File | Action | Task |
|------|--------|------|
| `pipeline/core/types.py` | **ADD** field `phase_model_hints` + `skip_optimize` to BuildConfig, **ADD** constant `PHASE_MODEL_MAP` | Task 7A |
| `pipeline/orchestrator/runner.py` | **ADD** model hint initialization in `run()` | Task 7B |

## Key Insights
- **PATCH P4**: Use `config.phase_model_hints` dict, NOT hidden state on claude client (race condition risk)
- **PATCH P8**: P3 and P4 currently HARDCODE `use_light_model=True` -- the PHASE_MODEL_MAP values for P3/P4 are ignored by existing code. Document this clearly. Do NOT change P3/P4 behavior to avoid breaking changes in Sprint 1.
- Backward compat: `phase_model_hints` defaults to empty dict `{}`, `skip_optimize` defaults to `False`

## Implementation Steps

### Task 7A: Add config to types.py (UPGRADE-PLAN lines 534-589)

1. Open `pipeline/core/types.py`
2. Add two fields to `BuildConfig` dataclass (after existing `auto_discover_baseline` field):

```python
phase_model_hints: dict = field(default_factory=dict)
skip_optimize: bool = False
```

3. Add constant AFTER class definitions:

```python
# Model routing per phase -- maps phase_id to use_light_model flag
# Light model (Haiku) for pattern matching, classification
# Full model (Sonnet) for complex reasoning, generation
#
# WARNING: Map only affects NEW phases (P55, P6) that read config.phase_model_hints.
# Existing P3 and P4 HARDCODE use_light_model=True in their source files.
# To change P3/P4 model selection, edit those files directly.
PHASE_MODEL_MAP = {
    "draft": {
        "p1": True,   # Haiku
        "p2": True,   # Haiku
        "p3": True,   # Haiku (hardcoded True anyway)
        "p4": True,   # Haiku (hardcoded True anyway)
        "p5": False,  # Sonnet
        "p55": True,  # Haiku
        "p6": True,   # Haiku
    },
    "standard": {
        "p1": True,   # Haiku
        "p2": False,  # Sonnet
        "p3": True,   # Haiku (hardcoded True anyway)
        "p4": True,   # Haiku (hardcoded True anyway)
        "p5": False,  # Sonnet
        "p55": True,  # Haiku
        "p6": False,  # Sonnet
    },
    "premium": {
        "p1": False,  # Sonnet
        "p2": False,  # Sonnet
        "p3": False,  # Sonnet (code hardcodes True, map ignored)
        "p4": False,  # Sonnet (code hardcodes True, map ignored)
        "p5": False,  # Sonnet
        "p55": False, # Sonnet
        "p6": False,  # Sonnet
    },
}
```

### Task 7B: Wire model hints in runner.py (UPGRADE-PLAN lines 592-608)

1. Open `pipeline/orchestrator/runner.py`
2. Add import at top: `from ..core.types import PHASE_MODEL_MAP`
3. In `run()` method, BEFORE the phase loop (`for phase_id, phase_name, phase_func in PHASES:`), add:

```python
model_map = PHASE_MODEL_MAP.get(self.config.quality_tier, PHASE_MODEL_MAP["standard"])
self.config.phase_model_hints = model_map
```

**NOTE**: This is a minimal change to runner.py. Phase 3 will make larger runner.py changes (PHASES list, P55 inline, resume).

## Validation

```bash
cd pipeline && python -m pytest tests/ -x

# Verify backward compat:
python -c "
from pipeline.core.types import BuildConfig, PHASE_MODEL_MAP
c = BuildConfig(name='test', domain='test')
print('OK:', c.phase_model_hints)
assert c.phase_model_hints == {}, 'Default should be empty dict'
assert c.skip_optimize == False
assert 'draft' in PHASE_MODEL_MAP
assert 'p6' in PHASE_MODEL_MAP['standard']
print('All checks passed')
"
```

## TODO
- [ ] Add `phase_model_hints` and `skip_optimize` fields to BuildConfig
- [ ] Add `PHASE_MODEL_MAP` constant
- [ ] Add model hint initialization in runner.py `run()`
- [ ] Run pytest -- all tests pass
- [ ] Verify backward compatibility

## Success Criteria
- `BuildConfig()` creates with empty `phase_model_hints` dict (backward compat)
- `PHASE_MODEL_MAP` has 3 tiers with 7 phase keys each
- All existing tests pass unchanged
- No changes to P3/P4 behavior

## Risk Assessment
- **Low**: Additive changes only -- new fields with defaults, new constant
- **Note**: runner.py will be modified again in Phase 3 -- keep changes minimal here
