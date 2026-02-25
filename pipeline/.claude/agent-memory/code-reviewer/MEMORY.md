# Code Reviewer Agent Memory

## Project: skill-factory-web

### Architecture
- **Pipeline** (Python): P0-P6 phases in `pipeline/phases/`, orchestrated by `pipeline/orchestrator/runner.py`
- **Frontend** (Next.js + TypeScript): React components in `components/build/`, API routes in `app/api/`
- **DB**: SQLite via better-sqlite3, schema in `lib/db-schema.ts`
- **Communication**: Pipeline emits JSON lines to stdout, parsed by `lib/build-runner.ts` as SSE

### Key Patterns
- PhaseId is a string enum ("p0"-"p6"), P55 is a sub-step that logs under "p5" to avoid breaking frontend parseInt
- Logger guard: `len(phase) > 2` prevents sub-phases from emitting phase events
- PHASE_MODEL_MAP in `pipeline/core/types.py` controls light/full model selection per tier, but P3/P4 hardcode light model
- Domain lessons flow: feedback DB -> getDomainLessons() -> DOMAIN_LESSONS env var -> config.py -> p5_build.py prompt

### Known Issues (v2-upgrade branch)
- Smoke test Python output schema (`prompt`, `score`) mismatches frontend interface (`name`, `detail`)
- PHASE_MODEL_MAP premium tier sets P3/P4 to False but code ignores it (hardcoded True)
- No input length validation on feedback API endpoint
- getDomainLessons has unguarded JSON.parse that can throw
- P6 eval always places target skill first in list (position bias)

### Security Observations
- Feedback text is injected into LLM prompts without sanitization (prompt injection risk)
- Reports API uses path.basename sanitization -- good
- Compare API reads from DB-stored output_path without path traversal guard
- No auth on API routes (acceptable for local-only deployment)

### Review Report Location
- Reports go to: `pipeline/plans/reports/code-reviewer-{date}-{time}-{slug}.md`
