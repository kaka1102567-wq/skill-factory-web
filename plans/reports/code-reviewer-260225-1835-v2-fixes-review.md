# Code Review: V2 Security & Data Alignment Fixes

**Reviewer:** code-reviewer | **Date:** 2025-02-26
**Branch:** v2-upgrade | **Commit:** unstaged diff against f55978e
**LOC Changed:** ~80 lines across 6 files

---

## Overall Assessment

The changes are well-targeted: two security fixes (path traversal), one data-size guard, one schema alignment, one model-map correction, and one position-bias fix. Most are correct and complete. Two issues found: one **Critical** (incomplete path traversal coverage) and one **Medium** (non-reproducible randomization).

---

## Critical Issues

### C1: Path Traversal Guard Missing on Two Additional Routes

**Files without guards that read `build.output_path`:**

- `C:\Users\Kaka\skill-factory-web\app\api\builds\[id]\route.ts` (lines 22, 37) -- serves SKILL.md and knowledge files
- `C:\Users\Kaka\skill-factory-web\app\api\builds\[id]\eval-trigger\route.ts` (line 17) -- serves p6_optimization_report.json

Both routes derive `outputDir` from `build.output_path` (user-influenced DB field) and then read arbitrary files from it. The same path traversal vector exists here.

**Impact:** An attacker who controls `output_path` in the DB can read files outside `data/builds/`. Since `/api/builds/[id]/route.ts` also serves directory listings (`readdirSync`), this is particularly dangerous.

**Fix:** Apply the same guard pattern to both routes:
```typescript
const expectedBase = path.resolve(process.cwd(), "data", "builds");
if (!path.resolve(outputDir).startsWith(expectedBase)) {
  return NextResponse.json({ error: "Invalid build path" }, { status: 403 });
}
```

**Recommendation:** Extract a shared helper to avoid repeating this 3-line pattern in 4 routes:
```typescript
// lib/path-guard.ts
export function isInsideBuildDir(dir: string): boolean {
  const expectedBase = path.resolve(process.cwd(), "data", "builds");
  return path.resolve(dir).startsWith(expectedBase + path.sep)
    || path.resolve(dir) === expectedBase;
}
```

Note the `+ path.sep` fix -- see H1 below.

---

## High Priority

### H1: Path Traversal Guard Has Prefix-Match Bypass

**Files:** `route.ts` in both `[id]/reports/` and `compare/`

The guard uses `startsWith(expectedBase)`. On Windows, `expectedBase` resolves to e.g. `C:\Users\Kaka\skill-factory-web\data\builds`. A path like `C:\Users\Kaka\skill-factory-web\data\builds-malicious\` would also pass the `startsWith` check because the string `builds-malicious` starts with `builds`.

**Impact:** Medium-low in practice (attacker must control `output_path` in DB, and the sibling directory must exist), but the fix is trivial.

**Fix:** Append `path.sep` to the base:
```typescript
const expectedBase = path.resolve(process.cwd(), "data", "builds");
const resolved = path.resolve(outputDir);
if (resolved !== expectedBase && !resolved.startsWith(expectedBase + path.sep)) {
  return NextResponse.json({ error: "Invalid build path" }, { status: 403 });
}
```

### H2: DOMAIN_LESSONS Truncation Could Cut Mid-UTF8 / Mid-Word

**File:** `C:\Users\Kaka\skill-factory-web\lib\build-runner.ts` line 593

`.slice(0, 8000)` truncates at character index 8000. This is safe for JS strings (UTF-16 code units), but could cut a multi-byte character pair (surrogate pair) or, more likely, cut mid-sentence. The value is passed as an env var (`DOMAIN_LESSONS`) which could produce garbled final text fed to the LLM.

**Impact:** Minor data quality issue in rare cases (lessons > 8000 chars).

**Recommendation:** Find last newline before 8000:
```typescript
let lessons = getDomainLessons(domain);
if (lessons.length > 8000) {
  const cut = lessons.lastIndexOf('\n', 8000);
  lessons = cut > 0 ? lessons.slice(0, cut) : lessons.slice(0, 8000);
}
const domainLessons = lessons;
```

---

## Medium Priority

### M1: P6 `_build_skills_list` Randomization Is Non-Reproducible

**File:** `C:\Users\Kaka\skill-factory-web\pipeline\phases\p6_optimize.py` lines 313-319

The new `random.shuffle(skills)` uses the global random state (no seed). This means:
1. **Different runs of the same build produce different skill orderings**, making results non-reproducible
2. **Within a single `_evaluate_description` call**, the order is fixed (good), but the `skills_list` value fed to each iteration differs (because `_build_skills_list` is called once per `_evaluate_description`)

This is actually desirable to average out position bias across iterations, but the lack of a seed makes debugging harder.

**Recommendation:** Accept non-determinism as intended (position-bias reduction is the goal), but document the intent:
```python
def _build_skills_list(skill_name: str, description: str) -> str:
    """Build skills list with target skill + decoy skills, randomized to avoid position bias.

    NOTE: Intentionally non-seeded -- each evaluation gets a fresh random order
    to average out positional bias across iterations.
    """
```

Also, the `import random` at the top of the function is redundant since `random` is already imported at module level (line 22). Remove the local import.

### M2: PHASE_MODEL_MAP Comments Are Potentially Confusing

**File:** `C:\Users\Kaka\skill-factory-web\pipeline\core\types.py` lines 240-241

The old comments said `"Sonnet (code hardcodes True, map ignored)"`, and the new comments say `"Haiku (hardcoded in phase code)"`. The new value is `True` (Haiku), which now matches the actual runtime behavior -- **this is correct**.

However, the comment could be clearer. Currently it says `"Haiku (hardcoded in phase code)"` which could be misread as "the map value doesn't matter." The map value does matter for any future consumer of `phase_model_hints`.

**Recommendation:** Update comment to be explicit:
```python
"p3": True,   # Haiku — also hardcoded in p3_dedup.py (map value aligns with code)
"p4": True,   # Haiku — also hardcoded in p4_verify.py (map value aligns with code)
```

---

## Low Priority

### L1: SmokeReport Interface Has Unused `score` and `passed` Fields

**File:** `C:\Users\Kaka\skill-factory-web\components\build\quality-report.tsx` lines 16-22

The interface declares `score?: number` and `passed?: boolean` but neither is used in the JSX. They exist in the P55 output (confirmed in `p55_smoke_test.py` line 179) but are never rendered.

**Impact:** None -- unused fields in a TS interface are harmless. They could be useful for future features.

---

## Edge Cases Found by Scouting

1. **`app/api/builds/[id]/route.ts`** and **`eval-trigger/route.ts`** are missing path traversal guards (elevated to C1)
2. **`_build_skills_list`** is called from `_evaluate_description` which iterates all eval queries with the same `skills_list` -- confirmed correct (position is fixed per evaluation pass)
3. **P3/P4 hardcoded `use_light_model=True`** confirmed in source (p3_dedup.py:325, p4_verify.py:281) -- the types.py map change is correct alignment
4. **`getDomainLessons` return value** can be empty string (feedback.ts:25), so `.slice(0, 8000)` on empty is safe
5. **SmokeReport schema alignment** verified against P55 output format (p55_smoke_test.py:177-181) -- field names match exactly (`results`, `pass_count`, `total`, `score`, `passed`)

---

## Positive Observations

- Path traversal guards in `[id]/reports/route.ts` and `compare/route.ts` are correctly placed **before** any file read
- The `path.basename(file)` sanitization in reports route (line 24) is a good defense-in-depth layer
- SmokeReport schema alignment is exact match with Python P55 output -- no field mismatches
- DOMAIN_LESSONS truncation prevents oversized env vars that could cause process spawn failures
- P6 skill randomization properly addresses the documented position-bias issue

---

## Recommended Actions (Priority Order)

1. **[Critical]** Add path traversal guard to `[id]/route.ts` and `[id]/eval-trigger/route.ts`
2. **[Critical]** Fix `startsWith` prefix bypass by appending `path.sep` to expectedBase
3. **[High]** Consider extracting shared `isInsideBuildDir()` helper to DRY the guard across 4 routes
4. **[High]** Improve DOMAIN_LESSONS truncation to cut at newline boundary
5. **[Medium]** Remove redundant `import random` inside `_build_skills_list` (already imported at module level)
6. **[Medium]** Clarify PHASE_MODEL_MAP comments for P3/P4

---

## Schema Alignment Verification

| P55 Python Output Field | Frontend Interface Field | Match |
|-------------------------|------------------------|-------|
| `results` (list)        | `results?: SmokeTest[]` | YES |
| `pass_count` (int)      | `pass_count?: number`  | YES |
| `total` (int)           | `total?: number`       | YES |
| `score` (float)         | `score?: number`       | YES |
| `passed` (bool)         | `passed?: boolean`     | YES |

| P55 Result Item Field | SmokeTest Interface Field | Match |
|----------------------|--------------------------|-------|
| `prompt` (str)       | `prompt: string`         | YES |
| `passed` (bool)      | `passed: boolean`        | YES |
| `score` (float)      | `score?: number`         | YES |
| `grade_notes` (str)  | `grade_notes?: string`   | YES |

All fields align correctly.

---

## Unresolved Questions

1. How does `build.output_path` get set? Is it only from the pipeline's `package` event (build-runner.ts:780), or can users set it via API? If user-settable, the path traversal issue is higher severity.
2. Should the 8000-char DOMAIN_LESSONS limit be configurable via settings, or is a hardcoded constant acceptable?
