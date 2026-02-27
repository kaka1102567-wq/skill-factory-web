## Phase Implementation Report

### Executed Phase
- Phase: P4 Multilingual Verify + P5 Confidence Map + TypeScript Settings
- Plan: inline task (no plan dir)
- Status: completed

### Files Modified

| File | Changes |
|------|---------|
| `pipeline/phases/p4_verify.py` | +90 lines: `_verify_with_embeddings()`, updated `run_p4` to use embedding_client |
| `pipeline/phases/p5_build.py` | Replaced `_generate_confidence_map()` (2-level→4-level), added `_extract_verification_score()`, `_enrich_atoms_multi_source()`, call site in `run_p5` |
| `lib/db-schema.ts` | +6 lines: 3 embedding settings in seed block + INSERT OR IGNORE migrations |
| `lib/build-runner.ts` | +3 lines: EMBEDDING_API_KEY, EMBEDDING_MODEL, EMBEDDING_BASE_URL env vars in spawnEnv |
| `app/settings/page.tsx` | +1 import (Layers icon), +new Embedding Model section with 3 inputs |
| `openspec/changes/hybrid-embedding/tasks.md` | Marked tasks 4.1-4.4, 5.1-5.3, 6.1-6.3 as [x] |

### Tasks Completed

- [x] 4.1 Read P4 verify flow
- [x] 4.2 `_verify_with_embeddings()` — similarity_matrix against baseline refs, 3-class (verified/partially_verified/expert_insight)
- [x] 4.3 Score written as `"Verified (score 0.85) against ref.md"` — matches `score\s+([\d.]+)` regex
- [x] 4.4 Fallback: if no embedding_client → `_verify_with_skill_seekers` (keyword) unchanged
- [x] 5.1 `_generate_confidence_map()` rewritten: HIGH/MEDIUM/LOW from parsed scores
- [x] 5.2 `_extract_verification_score()` helper added above `_generate_confidence_map`
- [x] 5.3 `_enrich_atoms_multi_source()` added; called in `run_p5` before confidence_map generation
- [x] 6.1 3 embedding settings in `db-schema.ts` seed + migration INSERT OR IGNORE
- [x] 6.2 3 embedding env vars in `_spawnPipeline` env object
- [x] 6.3 Embedding Model section in settings UI (Model + Base URL + API Key)

### Tests Status
- Python syntax: pass (`ast.parse` clean on both files)
- TypeScript: pass (`npx tsc --noEmit` zero errors)
- Unit tests: not run (out of scope for this task — covered by task 7.x)

### Issues Encountered
None. All changes are backward-compatible:
- P4: embedding path only activates when `config.embedding_client` is set
- P5: confidence map degrades gracefully when no score in verification_note (uses baseline_reference presence)
- P5 enrichment: skips silently if <3 sources or no embedding_client

### Next Steps
- Task 7.x: write/update tests for P4 embedding verify, P5 4-level map, P5 enrichment
