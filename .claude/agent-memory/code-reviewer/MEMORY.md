# Code Reviewer Agent Memory

## Project: skill-factory-web

### Architecture
- Next.js frontend + Python pipeline backend
- Build data stored in `data/builds/{id}/output/`
- `build.output_path` in SQLite DB points to output dir (set by pipeline `package` event)
- API routes under `app/api/builds/` read files from output_path
- Python pipeline phases: P0-P6 + P55 (smoke test sub-step of P5)

### Security Patterns
- Path traversal: All routes reading `build.output_path` must validate against `data/builds/` base
- Routes using output_path: `[id]/route.ts`, `[id]/reports/route.ts`, `[id]/eval-trigger/route.ts`, `compare/route.ts`
- `startsWith` prefix check needs `+ path.sep` to prevent sibling directory bypass (e.g., `builds-malicious/`)
- File sanitization: `path.basename()` + extension whitelist is defense-in-depth

### Schema Alignment (P55 <-> Frontend)
- P55 smoke_test_report.json: `results`, `pass_count`, `total`, `score`, `passed`
- SmokeTest items: `prompt`, `passed`, `score`, `grade_notes`
- Frontend component: `components/build/quality-report.tsx`

### Model Routing
- PHASE_MODEL_MAP in `pipeline/core/types.py` maps tier -> phase -> use_light_model
- P3/P4 HARDCODE `use_light_model=True` in their source files regardless of map
- Map should align with hardcoded values for consistency
- P55, P6 actually read `config.phase_model_hints` from the map

### Key Files
- `lib/build-runner.ts` - spawns Python pipeline, passes env vars
- `lib/feedback.ts` - getDomainLessons() for self-improving pipeline
- `pipeline/orchestrator/runner.py` - sequences P0-P6 phases
- `pipeline/core/types.py` - shared types + PHASE_MODEL_MAP
