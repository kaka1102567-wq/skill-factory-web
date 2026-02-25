# Phase 5: Tests

## Context Links
- Source: `UPGRADE-PLAN-FINAL.md` Task 6
- Sprint: 2/3

## Overview
- **Priority**: P1
- **Status**: complete
- **Description**: Add test classes for P6 optimizer, P55 smoke test, progressive disclosure, and multi-model strategy
- **Estimated effort**: 0.5 days

## Dependencies
- **Depends on**: Phase 3 (P6 + P55 code must exist), Phase 4 (frontend must compile)
- **Blocks**: Phase 6 (UI work should start only after core is tested)

## File Ownership

| File | Action | Task |
|------|--------|------|
| `pipeline/tests/test_phases.py` | **ADD** 4 test classes | Task 6 |

## Key Insights
- Tests validate helper functions (not full pipeline runs -- those need Claude API)
- P55 test verifies graceful skip when no Claude client
- Progressive disclosure test checks warning generation
- Multi-model test validates PHASE_MODEL_MAP structure

## Implementation Steps

### Task 6: Add test classes (UPGRADE-PLAN lines 1573-1660)

Add 4 test classes to `pipeline/tests/test_phases.py`:

```python
class TestP6Optimize:
    def test_extract_description_double_quoted(self):
        from pipeline.phases.p6_optimize import _extract_description
        md = '---\nname: test\ndescription: "Use this for testing"\n---\n# Test'
        assert _extract_description(md) == "Use this for testing"

    def test_extract_description_unquoted(self):
        from pipeline.phases.p6_optimize import _extract_description
        md = '---\nname: test\ndescription: Use this for testing\n---\n# Test'
        assert _extract_description(md) == "Use this for testing"

    def test_replace_description(self):
        from pipeline.phases.p6_optimize import _replace_description
        md = '---\nname: test\ndescription: "old desc"\n---\n# Test'
        result = _replace_description(md, "new desc here")
        assert "new desc here" in result
        assert "old desc" not in result

    def test_split_eval_set_stratified(self):
        from pipeline.phases.p6_optimize import _split_eval_set
        evals = [{"query": f"q{i}", "should_trigger": i < 10} for i in range(20)]
        train, test = _split_eval_set(evals, holdout=0.4)
        assert any(e["should_trigger"] for e in train)
        assert any(not e["should_trigger"] for e in train)
        assert any(e["should_trigger"] for e in test)

    def test_calc_score(self):
        from pipeline.phases.p6_optimize import _calc_score
        assert _calc_score([{"pass": True}, {"pass": True}, {"pass": False}]) == pytest.approx(2/3)
        assert _calc_score([]) == 0.0


class TestP55SmokeTest:
    def test_import(self):
        from pipeline.phases.p55_smoke_test import run_p55
        assert callable(run_p55)

    def test_skips_without_claude(self, tmp_path):
        from pipeline.phases.p55_smoke_test import run_p55
        from pipeline.core.types import BuildConfig
        from pipeline.core.logger import PipelineLogger
        config = BuildConfig(name="test", domain="test", output_dir=str(tmp_path))
        result = run_p55(config, None, None, None, PipelineLogger())
        assert result.status == "skipped"


class TestProgressiveDisclosure:
    def test_description_too_short(self):
        from pipeline.phases.p5_build import _enforce_progressive_disclosure
        from pipeline.core.logger import PipelineLogger
        _, warnings = _enforce_progressive_disclosure("# Test", "Short", {}, PipelineLogger())
        assert any("undertrigger" in w.lower() or "too short" in w.lower() for w in warnings)

    def test_description_ok(self):
        from pipeline.phases.p5_build import _enforce_progressive_disclosure
        from pipeline.core.logger import PipelineLogger
        desc = " ".join(["word"] * 120)
        _, warnings = _enforce_progressive_disclosure("# Test", desc, {}, PipelineLogger())
        desc_warnings = [w for w in warnings if "escription" in w]
        assert len(desc_warnings) == 0


class TestMultiModelStrategy:
    def test_phase_model_map_structure(self):
        from pipeline.core.types import PHASE_MODEL_MAP
        for tier in ["draft", "standard", "premium"]:
            assert tier in PHASE_MODEL_MAP
            assert "p1" in PHASE_MODEL_MAP[tier]
            assert "p5" in PHASE_MODEL_MAP[tier]

    def test_draft_uses_light_for_p1(self):
        from pipeline.core.types import PHASE_MODEL_MAP
        assert PHASE_MODEL_MAP["draft"]["p1"] is True

    def test_premium_uses_full_for_all(self):
        from pipeline.core.types import PHASE_MODEL_MAP
        for phase_id, use_light in PHASE_MODEL_MAP["premium"].items():
            assert use_light is False, f"Premium should use full model for {phase_id}"
```

**Note**: `PipelineLogger()` constructor may need adjustment based on actual signature. Check current logger.py init params.

## Validation

```bash
cd pipeline && python -m pytest tests/test_phases.py -x -v

# Run specific test classes
python -m pytest tests/test_phases.py::TestP6Optimize -v
python -m pytest tests/test_phases.py::TestP55SmokeTest -v
python -m pytest tests/test_phases.py::TestProgressiveDisclosure -v
python -m pytest tests/test_phases.py::TestMultiModelStrategy -v

# Full suite
python -m pytest tests/ -x
```

## TODO
- [ ] Add TestP6Optimize class (5 tests)
- [ ] Add TestP55SmokeTest class (2 tests)
- [ ] Add TestProgressiveDisclosure class (2 tests)
- [ ] Add TestMultiModelStrategy class (3 tests)
- [ ] Run full test suite -- all pass

## Success Criteria
- 12 new tests, all passing
- All existing tests still pass
- No mocks of actual Claude API (test helpers only)

## Risk Assessment
- **Low**: Test-only changes
- **Note**: `PipelineLogger()` constructor signature needs verification -- may need `build_id` or other args
- **Note**: `BuildConfig` constructor may need additional required fields beyond `name` and `domain`
