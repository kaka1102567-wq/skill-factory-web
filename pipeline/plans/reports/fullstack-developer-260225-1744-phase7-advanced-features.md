# Phase Implementation Report

## Executed Phase
- Phase: Phase 7 — Advanced Features (Tasks 12 + 13)
- Plan: plans/260225-1656-v2-upgrade-implementation/phase-07-advanced-features.md
- Status: completed

## Files Modified

| File | Change |
|------|--------|
| `lib/db-schema.ts` | Added `build_feedback` table + idx_feedback_domain; migration-safe template column additions |
| `pipeline/core/types.py` | Added `template_optimized_description: str = ""` and `domain_lessons: str = ""` to BuildConfig |
| `pipeline/phases/p6_optimize.py` | Wire template_optimized_description as starting point after description extraction |
| `pipeline/phases/p5_build.py` | Append domain_lessons to P5_SKILL_USER prompt in `_build_skill_md_via_claude` |
| `pipeline/core/config.py` | Read `DOMAIN_LESSONS` env var into `domain_lessons` field |
| `lib/build-runner.ts` | Import getDomainLessons; query lessons before spawn; pass as `DOMAIN_LESSONS` env var |
| `pipeline/tests/conftest.py` | Add P6 eval-query mock; fix mock SKILL.md to include YAML frontmatter with description |
| `pipeline/tests/test_e2e_dry.py` | Update expected `current_phase` from "p5" to "p6" (P6 now in PHASES) |

## Files Created

| File | Description |
|------|-------------|
| `lib/feedback.ts` | submitFeedback + getDomainLessons functions |
| `app/api/builds/[id]/feedback/route.ts` | POST endpoint: validate rating 1-5, persist feedback |
| `components/build/feedback-widget.tsx` | Star rating + issue chips + text area + submit |

## Tasks Completed

- [x] 12A: `build_feedback` + template migration-safe columns in db-schema.ts
- [x] 12B: `template_optimized_description` field in BuildConfig
- [x] 12C: Wire template description as P6 starting point
- [x] 13A: `build_feedback` table + index in db-schema.ts
- [x] 13B: `lib/feedback.ts` (submitFeedback, getDomainLessons)
- [x] 13C: POST `/api/builds/[id]/feedback/route.ts`
- [x] 13D: `components/build/feedback-widget.tsx`
- [x] 13E: `domain_lessons` field in BuildConfig
- [x] 13F: Inject domain_lessons into P5 prompt
- [x] 13G: Wire getDomainLessons in build-runner.ts via DOMAIN_LESSONS env var

## Tests Status
- Type check: pass (Compiled successfully)
- Python unit tests: 325 passed, 0 failed
- Integration tests: pass (test_e2e_dry full pipeline P0→P6)

## Issues Encountered

1. **MockClaudeClient SKILL.md had no YAML frontmatter** — P6 `_extract_description` returned "" and raised PhaseError. Fixed by updating mock to return valid frontmatter with description.
2. **test_e2e_dry assertions expected `current_phase == "p5"`** — P6 was added to PHASES so the last phase is now "p6". Updated two test assertions.
3. **domain_lessons transport**: Env var approach chosen (DOMAIN_LESSONS) to avoid modifying config.yaml at runtime. For very long lesson strings (many builds), consider temp file approach.

## Architecture Notes

- domain_lessons flow: DB → getDomainLessons() → DOMAIN_LESSONS env → config.py → BuildConfig.domain_lessons → p5_build.py prompt
- template_optimized_description flow: DB template column → config → p6 starting point (bypasses initial extraction)
- build_feedback table: migration-safe (CREATE TABLE IF NOT EXISTS), cascades on build delete
