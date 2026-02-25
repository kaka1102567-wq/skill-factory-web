---
title: "Skill Factory Web v2 Upgrade"
description: "13 tasks across 7 phases: pipeline prompts, core, new phases, frontend, tests, UI, advanced"
status: complete
priority: P1
effort: 17-22d
branch: v2-upgrade
tags: [v2, pipeline, p6, p55, multi-model, ui]
created: 2026-02-25
---

# V2 Upgrade Implementation Plan

Source: `UPGRADE-PLAN-FINAL.md` (10 critical patches, 13 tasks, 4 sprints)

## Dependency Graph

```
Phase 1 (Prompts) ──┐
                     ├──> Phase 2 (Core) ──> Phase 3 (New Phases) ──┬──> Phase 5 (Tests)
Phase 1 (Prompts) ──┘                                               │
                                                 Phase 4 (Frontend) ┘
                                                       │
                                                       v
                                          Phase 6 (UI Features) [parallel group]
                                                       │
                                                       v
                                          Phase 7 (Advanced Features)
```

## Execution Strategy

| Phase | Parallel? | Depends On | Est. LOC |
|-------|-----------|------------|----------|
| 1 - Pipeline Prompts | YES (internal) | none | ~400 |
| 2 - Pipeline Core | SEQUENTIAL | Phase 1 | ~100 |
| 3 - New Pipeline Phases | SEQUENTIAL | Phase 2 | ~600 |
| 4 - Frontend Sync | SEQUENTIAL | Phase 3 | ~50 |
| 5 - Tests | SEQUENTIAL | Phase 3+4 | ~120 |
| 6 - UI Features | PARALLEL (internal) | Phase 4 | ~800 |
| 7 - Advanced Features | SEQUENTIAL | Phase 6 | ~400 |

**Total estimated LOC changes: ~2,500**

## Critical Patches Mapping

| Patch | Description | Phase |
|-------|-------------|-------|
| P1 | PyYAML (not regex) for YAML | 3 |
| P2 | Remove RUNS_PER_QUERY | 3 |
| P3 | 7 decoy skills | 3 |
| P4 | Config-based multi-model | 2 |
| P5 | 4 frontend sync points | 4 |
| P6 | Assert guard logger | 3 |
| P7 | resume adds "p6" | 3 |
| P8 | Document P3/P4 hardcoded | 2 |
| P9 | P55 Option A (inline) | 3 |
| P10 | Compare API regex truncation | 6 |

## File Ownership Matrix

| File | Phase | Action |
|------|-------|--------|
| `pipeline/prompts/p5_build_prompts.py` | 1 | modify |
| `pipeline/prompts/p1_audit_prompts.py` | 1 | modify |
| `pipeline/prompts/p2_extract_prompts.py` | 1 | modify |
| `pipeline/prompts/p3_dedup_prompts.py` | 1 | modify |
| `pipeline/prompts/p4_verify_prompts.py` | 1 | modify |
| `pipeline/core/types.py` | 2 | modify |
| `pipeline/orchestrator/runner.py` | 3 | modify |
| `pipeline/core/logger.py` | 3 | modify |
| `pipeline/prompts/p6_optimize_prompts.py` | 3 | create |
| `pipeline/phases/p6_optimize.py` | 3 | create |
| `pipeline/phases/p55_smoke_test.py` | 3 | create |
| `pipeline/phases/p5_build.py` | 1+6 | modify |
| `types/build.ts` | 4 | modify |
| `hooks/use-build-stream.ts` | 4 | modify |
| `components/build/phase-stepper.tsx` | 4 | modify |
| `pipeline/tests/test_phases.py` | 5 | modify |
| `components/build/eval-trigger-panel.tsx` | 6 | create |
| `components/build/build-compare.tsx` | 6 | create |
| `components/build/quality-report.tsx` | 6 | modify |
| `components/build/feedback-widget.tsx` | 7 | create |
| `lib/feedback.ts` | 7 | create |
| `lib/db-schema.ts` | 7 | modify |

## Phase Files

- [Phase 1: Pipeline Prompts](phase-01-pipeline-prompts.md)
- [Phase 2: Pipeline Core](phase-02-pipeline-core.md)
- [Phase 3: New Pipeline Phases](phase-03-new-pipeline-phases.md)
- [Phase 4: Frontend Sync](phase-04-frontend-sync.md)
- [Phase 5: Tests](phase-05-tests.md)
- [Phase 6: UI Features](phase-06-ui-features.md)
- [Phase 7: Advanced Features](phase-07-advanced-features.md)
