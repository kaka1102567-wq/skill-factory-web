# Phase 6: UI Features

## Context Links
- Source: `UPGRADE-PLAN-FINAL.md` Tasks 8, 9, 10, 11
- Sprint: 3 (Quality & UI)
- Patches: P10 (compare API regex truncation)

## Overview
- **Priority**: P2
- **Status**: complete
- **Description**: Build eval trigger panel, build compare page, script auto-bundler, quality report 2.0
- **Estimated effort**: 5-6 days
- **Internal parallelism**: Tasks 8, 9, 10, 11 touch DIFFERENT files and can run concurrently

## Dependencies
- **Depends on**: Phase 4 (frontend must have P6 types)
- **Blocks**: Phase 7

## File Ownership

### Task 8: Eval Trigger Panel
| File | Action |
|------|--------|
| `app/api/builds/[id]/eval-trigger/route.ts` | **CREATE** |
| `components/build/eval-trigger-panel.tsx` | **CREATE** |
| `app/build/[id]/page.tsx` | **MODIFY** (add tab) |

### Task 9: Build Compare
| File | Action |
|------|--------|
| `app/api/builds/compare/route.ts` | **CREATE** |
| `components/build/build-compare.tsx` | **CREATE** |
| `app/compare/page.tsx` | **CREATE** |
| `components/layout/sidebar.tsx` | **MODIFY** (add nav link) |

### Task 10: Script Auto-Bundler
| File | Action |
|------|--------|
| `pipeline/prompts/p5_script_prompts.py` | **CREATE** |
| `pipeline/phases/p5_build.py` | **MODIFY** (add `_maybe_bundle_scripts`) |

### Task 11: Quality Report 2.0
| File | Action |
|------|--------|
| `components/build/quality-report.tsx` | **MODIFY** (add smoke test + P6 sections) |
| `app/api/builds/[id]/reports/route.ts` | **CREATE** |

**Conflict check**: `p5_build.py` is modified by both Task 2 (Phase 1) and Task 10 (this phase). Phase 1 adds `_enforce_progressive_disclosure`; Task 10 adds `_maybe_bundle_scripts`. Different functions, no overlap. `app/build/[id]/page.tsx` only modified by Task 8.

## Key Insights
- **PATCH P10**: Compare API must read description from P6 report first (not regex on SKILL.md) because `yaml.dump` produces multi-line output that regex truncates
- Tasks 8-11 are independent and can be implemented in parallel by different agents
- All new API endpoints follow existing patterns (getBuild, path.join, fs.existsSync)

## Implementation Steps

### Task 8: Eval Trigger Panel (UPGRADE-PLAN lines 1664-1856)

**8A. Create API** `app/api/builds/[id]/eval-trigger/route.ts`:
- GET endpoint reads `p6_optimization_report.json` from build output dir
- Returns `{ eval_set, report }` or `{ eval_set: [], report: null }` if no P6 run
- Report includes: best_train_score, best_test_score, iterations, original_description, best_description, history

**8B. Create component** `components/build/eval-trigger-panel.tsx`:
- Score summary (3 cards: train, test, iterations)
- Description before/after diff
- Eval queries split: should-trigger vs should-not-trigger
- Each query shows pass/fail icon
- Loading state, empty state

**8C. Integration** in `app/build/[id]/page.tsx`:
```tsx
import { EvalTriggerPanel } from "@/components/build/eval-trigger-panel";
// Add tab: "Triggering"
{tab === "eval" && <EvalTriggerPanel buildId={build.id} />}
```

### Task 9: Build Compare (UPGRADE-PLAN lines 1860-2057)

**9A. Create API** `app/api/builds/compare/route.ts`:
- GET `?a={id}&b={id}` -- loads both builds + reports
- **PATCH P10**: Read description from P6 report first, fallback to regex on SKILL.md
- Returns `{ a: { ...build, reports }, b: { ...build, reports } }`

```typescript
// PATCH P10: Read from P6 report first (regex truncates yaml.dump multi-line)
const p6ReportPath = path.join(build.output_path, "p6_optimization_report.json");
if (fs.existsSync(p6ReportPath)) {
  const p6Report = JSON.parse(fs.readFileSync(p6ReportPath, "utf-8"));
  files["description"] = p6Report.best_description || "";
}
```

**9B. Create component** `components/build/build-compare.tsx`:
- Side-by-side header (build name + domain)
- Comparison table: quality_score, atoms_verified, api_cost_usd, tokens_used
- Color coding: green = better, red = worse (inverted for cost)
- Description comparison

**9C. Create page** `app/compare/page.tsx`:
- Two build selectors (dropdown from completed builds)
- Renders BuildCompare component when both selected
- Supports URL params `?a=...&b=...`

**9D. Update sidebar** `components/layout/sidebar.tsx`:
```tsx
{ href: "/compare", icon: GitCompareArrows, label: "Compare" }
```

### Task 10: Script Auto-Bundler (UPGRADE-PLAN lines 2061-2163)

**10A. Create prompts** `pipeline/prompts/p5_script_prompts.py`:
- `P5_SCRIPT_SYSTEM` -- identifies domain patterns (marketing -> calculators, tech -> generators)
- `P5_SCRIPT_USER` -- analyzes skill and returns `{scripts: [{name, description, language, code}]}`

**10B. Add function** to `pipeline/phases/p5_build.py`:

```python
def _maybe_bundle_scripts(config, claude, atoms, topics, logger) -> list[dict]:
    """Auto-generate helper scripts. Only for standard/premium tiers."""
    if config.quality_tier == "draft":
        return []
    # Call Claude to analyze domain and generate scripts
    # Return list of {name, description, code}
```

**10B Integration**: In `run_p5()`, after packaging knowledge files, before creating zip:
```python
scripts = _maybe_bundle_scripts(config, claude, build_atoms, topics_str, logger)
for script in scripts:
    script_path = os.path.join(config.output_dir, "scripts", script["name"])
    os.makedirs(os.path.dirname(script_path), exist_ok=True)
    write_file(script_path, script["code"])
```

### Task 11: Quality Report 2.0 (UPGRADE-PLAN lines 2167-2278)

**11A. Create API** `app/api/builds/[id]/reports/route.ts`:
- GET `?file={name}` -- reads JSON report from build output
- Sanitizes filename (basename only, must end .json)
- Returns parsed JSON or 404

**11B. Modify** `components/build/quality-report.tsx`:
- Add state for smoke test + P6 reports
- Fetch from `/api/builds/{id}/reports?file=smoke_test_report.json`
- Fetch from `/api/builds/{id}/reports?file=p6_optimization_report.json`
- Add smoke test section: pass count, per-test results with check/X icons
- Add P6 optimization section: train/test/iterations, improvement arrow

## Validation

```bash
# TypeScript compile
npm run build

# Python tests (for Task 10)
cd pipeline && python -m pytest tests/ -x

# Manual UI verification
npm run dev
# Test: build page shows Triggering tab
# Test: /compare page loads and selectors work
# Test: quality report shows smoke test + P6 sections
```

## TODO

### Task 8
- [ ] Create eval-trigger API endpoint
- [ ] Create eval-trigger-panel.tsx component
- [ ] Add Triggering tab to build page

### Task 9
- [ ] Create compare API endpoint (with P10 patch)
- [ ] Create build-compare.tsx component
- [ ] Create compare page
- [ ] Add Compare link to sidebar

### Task 10
- [ ] Create p5_script_prompts.py
- [ ] Add _maybe_bundle_scripts to p5_build.py
- [ ] Integrate in run_p5() before zip creation

### Task 11
- [ ] Create reports API endpoint
- [ ] Add smoke test section to quality-report.tsx
- [ ] Add P6 optimization section to quality-report.tsx

### Final
- [ ] npm run build -- compiles
- [ ] pytest -- all pass

## Success Criteria
- Eval trigger panel shows P6 optimization results
- Compare page displays side-by-side build metrics
- Script bundler generates scripts for marketing domains
- Quality report shows smoke test + P6 sections
- All existing features continue to work

## Risk Assessment
- **Medium**: Multiple new API endpoints -- ensure auth middleware covers new routes
- **Medium**: p5_build.py has accumulated 2 additions (disclosure + bundler) -- watch for file size
- **Low**: New components are isolated, no impact on existing UI
