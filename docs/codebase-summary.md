# Skill Factory Web — Codebase Summary

**Project:** skill-factory-web | **Version:** 2.12.1 | **Language:** TypeScript (frontend), Python (pipeline)

## Directory Structure

```
skill-factory-web/
├── app/                    # Next.js App Router (12 routes + 17 API endpoints)
├── components/             # React components (~40 files, 18 shadcn/ui)
├── hooks/                  # Custom React hooks (3 files)
├── lib/                    # Backend modules (15 files, 2,500+ LOC)
├── types/                  # TypeScript type definitions (1 file)
├── pipeline/               # Python pipeline engine (~4,500 LOC)
├── public/                 # Static assets
├── .claude/                # Claude Code agent configs
├── data/                   # Runtime data (SQLite, builds, uploads)
├── node_modules/           # Dependencies (auto-generated)
├── .env.example            # Environment template
├── middleware.ts           # Auth guard middleware
├── next.config.ts          # Next.js configuration
├── tsconfig.json           # TypeScript config
├── tailwind.config.ts      # Tailwind CSS config
├── Dockerfile              # Multi-stage Docker build
├── ecosystem.config.js     # PM2 process manager config
├── deploy.sh               # Deployment script
└── package.json            # Node dependencies
```

## Frontend Layer (App Router)

### Pages & Routes
| Route | File | Purpose | Components |
|-------|------|---------|-----------|
| `/` | `app/page.tsx` | Dashboard | stats-bar, recent-builds, build-card |
| `/build/new` | `app/build/new/page.tsx` | Build Wizard | build-wizard, 5-step components |
| `/build/[id]` | `app/build/[id]/page.tsx` | Build Monitor | phase-stepper, log-viewer, quality-report |
| `/library` | `app/library/page.tsx` | Skills Library | skill list, search, download |
| `/templates` | `app/templates/page.tsx` | Template Catalog | template cards, preview |
| `/baselines` | `app/baselines/page.tsx` | Baselines Manager | baseline list, CRUD |
| `/settings` | `app/settings/page.tsx` | App Settings | key-value form, cleanup trigger |

### API Routes (17 endpoints)
| Method | Path | Handler | Purpose |
|--------|------|---------|---------|
| GET | `/api/auth` | route.ts | Check auth status |
| POST | `/api/auth` | route.ts | Login (password → token) |
| GET | `/api/builds` | route.ts | List all builds |
| POST | `/api/builds` | route.ts | Create new build |
| GET | `/api/builds/[id]` | route.ts | Get build details |
| DELETE | `/api/builds/[id]` | route.ts | Delete build |
| GET | `/api/builds/[id]/logs` | route.ts | SSE stream |
| POST | `/api/builds/[id]/stop` | route.ts | Stop running build |
| POST | `/api/builds/[id]/retry` | route.ts | Retry failed build |
| GET/POST | `/api/builds/[id]/review` | route.ts | Conflict resolution |
| GET | `/api/builds/[id]/download` | route.ts | Download package.zip |
| POST | `/api/uploads` | route.ts | Upload files |
| GET | `/api/stats` | route.ts | Dashboard stats |
| GET/PUT | `/api/settings` | route.ts | Read/update settings |
| POST | `/api/settings/cleanup` | route.ts | Trigger old build cleanup |
| POST | `/api/settings/test-telegram` | route.ts | Test Telegram bot |
| GET/POST/PUT/DELETE | `/api/templates` | route.ts | Template CRUD |
| GET/POST/PUT/DELETE | `/api/baselines` | route.ts | Baseline CRUD |
| GET | `/api/baselines/[domain]` | route.ts | Get baseline by domain |

### Components Directory (40+ files)

**Build Components** (`components/build/`)
- `build-wizard.tsx` — 4-step form orchestration
- `phase-stepper.tsx` — Visual phase progress (P0-P5)
- `log-viewer.tsx` — Real-time log streaming + filtering
- `quality-report.tsx` — Per-phase scores + final metric
- `conflict-review.tsx` — Dedup conflict resolution UI
- `skill-preview.tsx` — SKILL.md preview
- `step-template.tsx` — Template picker
- `step-upload.tsx` — File upload interface
- `step-data-sources.tsx` — URL entry
- `step-config.tsx` — YAML editor
- `step-review.tsx` — Final confirmation

**Dashboard Components** (`components/dashboard/`)
- `build-card.tsx` — Build summary card (status, progress, cost)
- `recent-builds.tsx` — List of recent builds
- `stats-bar.tsx` — KPI display (total, completed, avg quality, cost)

**Layout Components** (`components/layout/`)
- `sidebar.tsx` — Navigation menu + user info
- `auth-gate.tsx` — Login form for unauthenticated users

**UI Components** (`components/ui/`)
- 18 shadcn/ui primitives: button, card, input, dialog, tabs, progress, badge, etc.

### Custom Hooks (3 files)

| Hook | File | Purpose |
|------|------|---------|
| `useAuth()` | `hooks/use-auth.ts` | Get auth status, login/logout |
| `useBuilds()` | `hooks/use-builds.ts` | Fetch build list + CRUD operations |
| `useBuildStream()` | `hooks/use-build-stream.ts` | SSE subscription + event parsing |

### Types (`types/build.ts`)
- `Build` — build metadata + status
- `BuildLog` — log entry with phase + message
- `Template` — template catalog item
- `PhaseInfo` — phase metadata (name, icon, tool)
- `DashboardStats` — KPI snapshot
- `BuildStatus` type: "pending" | "queued" | "running" | "paused" | "completed" | "failed"
- `PhaseId` type: "p0" | "p1" | "p2" | "p3" | "p4" | "p5"
- `QualityTier` type: "draft" | "standard" | "premium"

## Backend Layer (Node.js + SQLite)

### Database Module (`lib/db.ts`, 243 LOC)
**Functions:**
- `getDb()` — Singleton SQLite instance with WAL mode
- `getBuild(id)`, `getBuilds(status?)` — Read builds
- `createBuild(data)` — Create new build
- `updateBuild(id, updates)` — Update build status/scores
- `deleteBuild(id)` — Delete build + cleanup files
- `createBuildLog(buildId, data)` — Append log entry
- `getBuildLogs(buildId)` — Fetch logs for build
- `getTemplates()`, `createTemplate()`, `updateTemplate()` — Template CRUD
- `getSetting(key)`, `setSetting(key, value)` — Settings store
- `getBaselines()`, `getBaseline(domain)` — Baseline queries
- `getDashboardStats()` — KPI snapshot

**Key Detail:** SQLite singleton pattern ensures single DB connection. WAL mode enables concurrent reads + sequential writes.

### Database Schema (`lib/db-schema.ts`, 203 LOC)
**Tables:**
- `builds` (13 columns) — id, name, domain, status, current_phase, phase_progress, config_yaml, quality_score, atoms_*, api_cost_usd, output_path, package_path, review_status
- `build_logs` (7 columns) — id, build_id, timestamp, level, phase, message, metadata
- `templates` (9 columns) — id, name, domain, description, icon, config_yaml, is_default, usage_count, created_at, updated_at
- `settings` (3 columns) — key, value, updated_at
- `baselines` (9 columns) — id, domain, name, config_path, seekers_output_dir, status, source_urls, refs_count, topics_count

**Indexes:** Compound index on (build_id, created_at), (domain), (key)

**Seed Data:** 4 templates (FB Ads, Google Ads, Blockchain, Custom), 4 baselines (bl-fb-ads, bl-google-ads, bl-seo, bl-blockchain)

### Build Runner (`lib/build-runner.ts`, 951 LOC — LARGEST FILE)
**Core Functions:**
- `spawnBuildProcess(buildId, config)` — Fork Python subprocess with env variables
- `parseJsonLine(line)` — Parse stdout events (phase, log, quality, cost, conflict, error)
- `updateBuildStatus(buildId, status, data)` — Persist changes to DB
- `broadcastSSE(buildId, event)` — Emit event to connected clients
- `stopBuild(buildId)` — Send SIGTERM to subprocess
- `recoverOrphanBuilds()` — Resume crashed builds on startup

**Subprocess Communication:**
- Spawns: `python pipeline/cli.py build --config {yaml} --output-dir {dir}`
- Parses stdout (newline-delimited JSON) for events
- Exits: code 0 (success), code 1+ (failure)
- Timeout: 3600s (1 hour) per build

**Error Handling:**
- ENOENT → python_path setting not found
- TIMEOUT → build manually stopped
- Non-zero exit → captured as build failure

### Build Queue (`lib/build-queue.ts`, 140 LOC)
**Implementation:** In-memory FIFO with concurrency control

**Functions:**
- `enqueue(buildId)` — Add to queue
- `dequeue()` — Pop from queue (if running < max)
- `isRunning(buildId)` — Check if in progress
- `pause(buildId)` — Mark as paused
- `getPendingCount()` — Queue size

**Storage:** `globalThis.pendingQueue` (in-memory) — survives request cycles, lost on restart

**Recovery:** On startup, query DB for `status='running'` → resume from last checkpoint

### SSE Manager (`lib/sse-manager.ts`, 56 LOC)
**Pub/Sub for real-time streaming:**
- `subscribe(buildId, response)` — Register client for events
- `publish(buildId, event, data)` — Broadcast to all subscribers
- `unsubscribe(buildId, response)` — Cleanup on disconnect

**Storage:** Map<buildId, Set<ServerResponse>>

### Config Generator (`lib/config-generator.ts`, 111 LOC)
**Function:** Convert UI form input → YAML config

**Inputs:**
- `name`, `domain`, `quality_tier`
- `sources`: { transcripts: File[], urls: string[], repos: string[] }
- `template_id`, `advanced_config` (optional)

**Outputs:** YAML ready for Python CLI

### Auth Module (`lib/auth.ts`, 34 LOC)
**Functions:**
- `hashPassword(pwd)` — djb2 hash → base36
- `validatePassword(pwd, hash)` — Verify password
- `setAuthCookie(response, hash)` — Create httpOnly cookie (7 days)
- `getAuthToken(request)` — Extract token from cookie
- `isAuthenticated(request)` — Check valid token

**Cookie:** Name: `sf_auth`, HttpOnly, SameSite=Strict, 7-day TTL

### Notifications (`lib/notifications.ts`, 53 LOC)
**Function:** Send Telegram messages on build events

**Trigger Events:**
- Build complete (success)
- Build failed
- Phase milestone

**Message Format:** Build name + status + quality score + cost

### Cleanup (`lib/cleanup.ts`, 73 LOC)
**Function:** Delete builds older than retention period

**Logic:**
- Query builds where `completed_at < (now - auto_cleanup_days)`
- Delete files from `/data/builds/{id}/`
- Delete DB records

**Trigger:** Manual (Settings → Cleanup Now) or cron (via PM2 ecosystem.config.js)

### Baseline Registry (`lib/baseline-registry.ts`, 110 LOC)
**Function:** Map domain → baseline config path

**Data:**
```typescript
{
  "facebook-ads": "/configs/seekers/facebook-ads.json",
  "google-ads": "/configs/seekers/google-ads.json",
  ...
}
```

### Baseline Scraper (`lib/baseline-scraper.ts`, 70 LOC)
**Function:** Pre-pipeline content discovery for P0

**Inputs:** Domain + seeker config → URLs to scrape

**Output:** `baseline_summary.json` (topics, refs count, content depth)

### Utils (`lib/utils.ts`, 99 LOC)
**UI Utilities:**
- `cn()` — Tailwind class merging (clsx + tailwind-merge)
- `formatDate()` — Timestamp formatting
- `formatCost()` — USD formatting
- `formatDuration()` — Time elapsed display

## Pipeline Layer (Python)

### Entry Point (`pipeline/cli.py`, 315 LOC)
**Commands:**
- `build` — Full pipeline execution (P0-P5)
- `resolve` — Re-run conflict resolution
- `status` — Check running build status

**Arguments:**
- `--config {yaml}` — Build config
- `--output-dir {path}` — Output directory
- `--quality-tier {draft|standard|premium}` — Model selection

### Core Modules (`pipeline/core/`)
- `types.py` — BuildConfig, KnowledgeAtom, PhaseResult dataclasses
- `errors.py` — PhaseError, PipelineError exceptions
- `config.py` — YAML loader + validation
- `logger.py` — Structured logging to JSON (consumed by build-runner)
- `utils.py` — Helper functions (paths, timestamps, etc.)

### Phase Implementations (`pipeline/phases/`, ~3,601 LOC total)
- `p0_baseline.py` — Seekers-based content discovery
- `p1_audit.py` — Transcript analysis → inventory
- `p2_extract.py` — Atom extraction (Claude Sonnet)
- `p3_dedup.py` — Deduplication + conflict detection (Claude Haiku)
- `p4_verify.py` — Evidence validation (Claude Haiku)
- `p5_architect.py` — SKILL.md + package generation (Claude Sonnet)

**Each phase:**
- Reads input artifacts (previous phase output)
- Runs Claude API calls (with retries via tenacity)
- Emits SSE events to build-runner (phase, log, quality, cost)
- Writes JSON output to `/data/builds/{id}/`
- Catches errors → fatal flag + error log

### Seekers Integration (`pipeline/seekers/`, ~1,581 LOC)
- `url_discoverer.py` — Recursive web crawling
- `pdf_extractor.py` — PyMuPDF text extraction
- `repo_analyzer.py` — Git repo structure analysis
- `content_scraper.py` — HTTP requests with retry logic

### Claude Client (`pipeline/clients/claude_client.py`)
**Wrapper around anthropic SDK:**
- `call_claude(model, messages, max_tokens)` — Sync API call
- `stream_claude(model, messages)` — Streaming for large outputs
- Error handling: retries with exponential backoff (tenacity)
- Cost tracking: count tokens + calculate USD

### Web Client (`pipeline/clients/web_client.py`)
**For communicating back to Node.js:**
- `post_event(build_id, event_type, data)` — SSE event submission

### Orchestrator (`pipeline/orchestrator/`)
- `runner.py` — Phase sequencing + state machine
- `state.py` — BuildState dataclass (current phase, atoms count, quality scores)

### Tests (`pipeline/tests/`, ~4,522 LOC)
- Unit tests for each phase
- Mock Claude API responses
- Test fixtures (sample configs, transcripts)
- Pytest parameterization for quality tiers

### Dependencies (`pipeline/requirements.txt`)
```
anthropic>=0.40.0
openai>=1.50.0
pyyaml
httpx
beautifulsoup4
lxml
tenacity
python-dotenv
PyMuPDF
pytest
skill-seekers>=2.7.0
```

## Key Patterns & Conventions

### Frontend (TypeScript/React)
- **Component Structure:** Functional components + custom hooks
- **State Management:** React hooks (useState, useContext for auth)
- **Styling:** Tailwind CSS 4 + shadcn/ui components (new-york style)
- **Icons:** lucide-react (18px default)
- **Async:** fetch API + useEffect for data fetching
- **Path Alias:** `@/*` maps to `./` (Next.js default)

### Backend (Node.js/TypeScript)
- **Database:** SQLite singleton pattern (better-sqlite3)
- **Subprocess:** child_process.spawn with JSON-line protocol
- **Streaming:** Server-Sent Events (SSE) for real-time updates
- **Error Handling:** try-catch + typed error classes
- **Config:** Environment variables via .env.local (next.js auto-loads)

### Python Pipeline
- **Type Hints:** Full dataclass annotations (Python 3.11+)
- **Error Handling:** Custom exception hierarchy
- **Logging:** JSON output to stdout (consumed by build-runner)
- **External APIs:** anthropic SDK + httpx (async capable)
- **Retries:** tenacity decorator for resilience
- **Testing:** pytest with fixtures + mocks

## Code Statistics

| Directory | Files | Lines | Language |
|-----------|-------|-------|----------|
| `app/` | 7 | ~800 | TypeScript/TSX |
| `components/` | 40 | ~2,000 | TypeScript/TSX |
| `hooks/` | 3 | ~300 | TypeScript |
| `lib/` | 15 | ~2,500 | TypeScript |
| `middleware.ts` | 1 | ~50 | TypeScript |
| `pipeline/` | 60+ | ~8,500 | Python |
| **Total** | **~125** | **~14,000+** | Mixed |

**Note:** Excludes node_modules, .git, test files, and generated files.

## Key Files to Know

| File | Purpose | LOC | Status |
|------|---------|-----|--------|
| `lib/build-runner.ts` | Subprocess orchestration (CRITICAL) | 951 | Stable |
| `lib/db.ts` | Database queries (CRITICAL) | 243 | Stable |
| `pipeline/cli.py` | Pipeline entry (CRITICAL) | 315 | Stable |
| `pipeline/phases/p5_architect.py` | Final packaging (HIGH) | TBD | v2-rewrite pending |
| `components/build/build-wizard.tsx` | UI entry point (HIGH) | TBD | Stable |
| `middleware.ts` | Auth guard (HIGH) | 50 | Stable |
| `lib/config-generator.ts` | YAML generation (MEDIUM) | 111 | Stable |

## Next Steps for Developers

1. **Read:** [System Architecture](./system-architecture.md) for data flow
2. **Read:** [Code Standards](./code-standards.md) for conventions
3. **Setup:** Clone repo, `npm install`, `pip install -r pipeline/requirements.txt`
4. **Local Dev:** `npm run dev` (frontend), in another terminal: mock Python CLI
5. **Test:** `npm test` + `pytest pipeline/`
6. **Deploy:** See [README.md](../README.md) for deployment options
