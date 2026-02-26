# Planner Agent Memory

## Project: skill-factory-web

### Architecture
- **Frontend**: Next.js App Router, React 19, TypeScript, Tailwind CSS 4, shadcn/ui
- **Backend**: Node.js API routes, SQLite (better-sqlite3), SSE for real-time
- **Pipeline**: Python 3.11+, 6 phases (P0-P5), Claude API via anthropic SDK
- **Key files**: `lib/build-runner.ts` (951 LOC, largest), `pipeline/orchestrator/runner.py`, `pipeline/core/types.py`

### v2 Upgrade Plan
- Plan dir: `plans/260225-1656-v2-upgrade-implementation/`
- 7 phases, 13 tasks, 10 critical patches
- Branch: `v2-upgrade`
- P55 is inline sub-step of P5 (Option A) -- NOT in PHASES array
- PyYAML for YAML parsing (not regex) -- regex returns ">" on folded block scalars
- Frontend has 4 sync points for phases: PhaseId type, PHASES array, INITIAL_PHASES, PHASE_COLORS

### Conventions
- Python: snake_case, dataclasses, pytest
- TypeScript: kebab-case files, PascalCase components
- Pipeline phases follow p5_build.py pattern
- ClaudeClient API: `.call(system, user, max_tokens, phase, use_light_model)`
- Validation: `cd pipeline && python -m pytest tests/ -x` and `npm run build`

### Gotchas
- `components/build/` glob blocked by `.claude/.ckignore` scout-block -- use specific file reads
- `set-active-plan.cjs` needs CK_SESSION_ID env var for persistence
- plan.md must stay under 80 lines per documentation rules
