# System Architecture

**Project:** skill-factory-web | **Version:** 2.12.1 | **Updated:** 2026-02-25

## System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                         BROWSER (Client)                             │
│  React 19 | TypeScript | Tailwind CSS | shadcn/ui                    │
│  Pages: Dashboard, Wizard, Monitor, Library, Templates, Settings     │
└─────────────────────────────┬──────────────────────────────────────┘
                              │
                    HTTP + SSE (EventSource)
                              │
                              ↓
┌──────────────────────────────────────────────────────────────────────┐
│              NEXT.JS API LAYER (Backend — Node.js)                   │
│  App Router | Route Handlers | Middleware | better-sqlite3           │
│  Routes: /api/builds, /api/settings, /api/templates, /api/baselines  │
│  Queue Manager | SSE Publisher | Auth Guard                          │
└──────┬──────────────────────────────────────────────────┬────────────┘
       │                                                  │
       │ CRUD + Queue                         SSE Publish
       │                                                  │
       ↓                                                  ↓
┌──────────────────────────┐                ┌────────────────────────┐
│    SQLite Database       │                │   SSE Manager (Pub)    │
│  WAL Mode + FK on        │                │  Map<buildId, Clients> │
│  builds                  │                │  Streams phase, log,   │
│  build_logs              │                │  quality, cost         │
│  templates               │                └────────────────────────┘
│  settings                │
│  baselines               │
└──────────────────────────┘
       ↓
       │ Enqueue + Monitor
       ↓
┌────────────────────────────────────────────────────────────────┐
│            BUILD QUEUE (In-Memory FIFO)                        │
│  Concurrency Controller | Orphan Recovery | Progress Tracking  │
│  globalThis.pendingQueue: buildId[]                            │
└─────────────────────────────┬────────────────────────────────┘
                              │
                              │ Dequeue + Spawn
                              ↓
┌────────────────────────────────────────────────────────────────┐
│         BUILD RUNNER (Subprocess Manager)                       │
│  spawn(python cli.py build --config {yaml} --output-dir {dir}) │
│  Parse stdout JSON → Update DB → Broadcast SSE                │
│  Timeout: 3600s | Exit code handling | Cleanup                │
└─────────────────────────────┬────────────────────────────────┘
                              │
                    Python subprocess + Claude API
                              │
                              ↓
┌────────────────────────────────────────────────────────────────┐
│              PYTHON PIPELINE (6 Phases)                        │
│  cli.py → runner.py → orchestrator/runner.py                  │
│                                                                 │
│  P0: Baseline      (skill-seekers + web scraping)            │
│  P1: Audit         (Claude Sonnet — transcript analysis)      │
│  P2: Extract       (Claude Sonnet — knowledge atoms)          │
│  P3: Dedup         (Claude Haiku — merge duplicates)          │
│  P4: Verify        (Claude Haiku — evidence validation)       │
│  P5: Architect     (Claude Sonnet — SKILL.md generation)      │
│                                                                 │
│  Outputs: JSON artifacts + logs → stdout (JSON-line format)   │
└────────────────────────────────────────────────────────────────┘
                              │
                    Claude API calls + skill-seekers
                              │
                              ↓
          ┌──────────────────────────────────┐
          │     External Services            │
          │  Anthropic API (Claude models)   │
          │  HTTP clients (URL scraping)     │
          │  PyMuPDF (PDF extraction)        │
          │  skill-seekers (baseline search) │
          └──────────────────────────────────┘
```

## Frontend Layer

### Pages & Components

**Layout:**
- Root: `app/layout.tsx` → ThemeProvider → AuthGate → Sidebar + Content
- AuthGate: Conditional login form (if not authenticated)
- Sidebar: Navigation menu (Dashboard, Wizard, Library, Templates, Settings)

**Pages:**
| Page | Route | Components | Purpose |
|------|-------|-----------|---------|
| Dashboard | `/` | stats-bar, recent-builds, build-card | Overview of all builds |
| Build Wizard | `/build/new` | build-wizard, 5 step-* components | Create new build |
| Build Monitor | `/build/[id]` | phase-stepper, log-viewer, quality-report | Real-time progress |
| Library | `/library` | skill list with search/filter | Browse completed skills |
| Templates | `/templates` | template cards with preview | Browse templates |
| Baselines | `/baselines` | baseline list, CRUD form | Manage reference docs |
| Settings | `/settings` | key-value form, cleanup trigger | Configure app |

### Custom Hooks

**useAuth Hook:**
```typescript
const { isAuthenticated, login, logout } = useAuth();

// Checks /api/auth on mount
// Sets token in cookie on login
// Clears on logout
```

**useBuilds Hook:**
```typescript
const { builds, loading, createBuild, deleteBuild, retryBuild } = useBuilds();

// Fetches GET /api/builds
// Manages build CRUD operations
// Refetches on create/delete
```

**useBuildStream Hook:**
```typescript
const { logs, currentPhase, quality, cost, complete } = useBuildStream(buildId);

// Subscribes to GET /api/builds/[id]/logs (SSE)
// Parses events: phase, log, quality, cost, conflict, complete
// Cleanup on unmount
```

### Data Flow

**Build Creation:**
1. User fills wizard (4 steps)
2. Click "Start Build"
3. POST /api/builds → { id, name, domain, config_yaml }
4. Redirect to /build/[id]
5. Start SSE subscription

**Build Monitoring:**
1. Open /build/[id]
2. useEffect → subscribe to SSE
3. Receive events: phase, log, quality, cost
4. Update UI in real-time (phase-stepper, log-viewer, quality-report)
5. On complete: enable download button

**Conflict Review:**
1. SSE event `conflict` received
2. Build pauses (status = "paused")
3. Show conflict review UI
4. User resolves (Keep A/B/Merge/Discard per conflict)
5. POST /api/builds/[id]/review → { decisions: [...] }
6. Resume build (P3 → P4 → P5)

## Backend Layer

### API Routes

**Authentication:**
- POST /api/auth: `{ password: string }` → `{ token: string }`
- GET /api/auth: Check if authenticated → `{ authenticated: boolean }`
- Cookie: `sf_auth` (httpOnly, 7-day TTL)

**Builds CRUD:**
- GET /api/builds: List all builds (filter by status)
- POST /api/builds: Create new build
- GET /api/builds/[id]: Get build details
- DELETE /api/builds/[id]: Delete build + cleanup files
- POST /api/builds/[id]/stop: Send SIGTERM to subprocess
- POST /api/builds/[id]/retry: Create new build with same config

**Build Monitoring:**
- GET /api/builds/[id]/logs: SSE stream (phase, log, quality, cost, error events)

**Conflict Resolution:**
- GET /api/builds/[id]/review: Get conflict data
- POST /api/builds/[id]/review: Submit conflict resolution decisions

**Package Download:**
- GET /api/builds/[id]/download: Return package.zip

**Uploads:**
- POST /api/uploads: Upload files (transcripts, PDFs) → return temp path

**Settings:**
- GET /api/settings: Read all settings
- PUT /api/settings: Update settings (API keys, paths, flags)
- POST /api/settings/cleanup: Delete old builds
- POST /api/settings/test-telegram: Send test message

**Other:**
- GET /api/stats: Dashboard stats (total builds, completed, avg quality, cost)
- GET /api/templates: List templates
- GET/POST/PUT/DELETE /api/baselines: Baseline CRUD

### Database Schema

**Builds Table:**
```sql
CREATE TABLE builds (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  domain TEXT,
  status TEXT NOT NULL,  -- pending, queued, running, paused, completed, failed
  current_phase TEXT,    -- p0-p5 or null
  phase_progress REAL,   -- 0-100
  config_yaml TEXT NOT NULL,
  template_id TEXT,
  quality_score REAL,    -- 0-100 or null
  atoms_extracted INTEGER,
  atoms_deduplicated INTEGER,
  atoms_verified INTEGER,
  compression_ratio REAL,
  api_cost_usd REAL,
  tokens_used INTEGER,
  output_path TEXT,      -- /data/builds/{id}/
  package_path TEXT,     -- /data/builds/{id}/package.zip
  review_status TEXT,    -- none, pending, completed
  review_data TEXT,      -- JSON: conflict decisions
  error_message TEXT,
  created_by TEXT,
  created_at TEXT,
  started_at TEXT,
  completed_at TEXT
);

CREATE INDEX idx_builds_created_at ON builds(created_at DESC);
```

**Build Logs Table:**
```sql
CREATE TABLE build_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  build_id TEXT NOT NULL REFERENCES builds(id),
  timestamp TEXT NOT NULL,
  level TEXT,            -- debug, info, warn, error, phase
  phase TEXT,            -- p0-p5 or null
  message TEXT NOT NULL,
  metadata TEXT          -- JSON: extra details
);

CREATE INDEX idx_logs_build_id_ts ON build_logs(build_id, timestamp);
```

**Templates Table:**
```sql
CREATE TABLE templates (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  domain TEXT NOT NULL,
  description TEXT,
  icon TEXT,            -- emoji or icon name
  config_yaml TEXT NOT NULL,
  is_default INTEGER,   -- 1 or 0
  usage_count INTEGER,
  created_at TEXT,
  updated_at TEXT
);
```

**Settings Table (Key-Value Store):**
```sql
CREATE TABLE settings (
  key TEXT PRIMARY KEY,
  value TEXT,
  updated_at TEXT
);

-- Seed:
INSERT INTO settings VALUES ('anthropic_api_key', '', now());
INSERT INTO settings VALUES ('python_path', 'python', now());
INSERT INTO settings VALUES ('max_concurrent_builds', '2', now());
INSERT INTO settings VALUES ('auto_cleanup_days', '30', now());
INSERT INTO settings VALUES ('telegram_token', '', now());
INSERT INTO settings VALUES ('telegram_chat_id', '', now());
```

**Baselines Table:**
```sql
CREATE TABLE baselines (
  id TEXT PRIMARY KEY,
  domain TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  config_path TEXT,        -- /configs/seekers/{domain}.json
  seekers_output_dir TEXT, -- /data/cache/baselines/{domain}/
  status TEXT,             -- pending, ready, failed
  source_urls TEXT,        -- JSON array
  refs_count INTEGER,
  topics_count INTEGER,
  created_at TEXT,
  updated_at TEXT
);
```

### Build Queue

**In-Memory FIFO:**
```typescript
// globalThis.pendingQueue: string[] (buildIds)

class BuildQueue {
  static async enqueue(buildId: string): Promise<void> {
    if (!globalThis.pendingQueue) {
      globalThis.pendingQueue = [];
    }
    globalThis.pendingQueue.push(buildId);
    await this.processQueue();
  }

  static async processQueue(): Promise<void> {
    // While queue not empty AND running < max_concurrent_builds:
    //   Dequeue → spawn subprocess → await completion
  }

  static getPendingCount(): number {
    return globalThis.pendingQueue?.length ?? 0;
  }
}
```

**Orphan Recovery:**
On server startup: Query `builds WHERE status = 'running'` → resume from checkpoint.

### SSE Manager

**Pub/Sub Pattern:**
```typescript
class SSEManager {
  private static subscribers = new Map<string, Set<ServerResponse>>();

  static subscribe(buildId: string, response: ServerResponse) {
    if (!this.subscribers.has(buildId)) {
      this.subscribers.set(buildId, new Set());
    }
    this.subscribers.get(buildId)!.add(response);
  }

  static publish(buildId: string, eventType: string, data: object) {
    const clients = this.subscribers.get(buildId);
    if (!clients) return;

    const sseMessage = `data: ${JSON.stringify({ type: eventType, ...data })}\n\n`;
    for (const client of clients) {
      client.write(sseMessage);
    }
  }

  static unsubscribe(buildId: string, response: ServerResponse) {
    const clients = this.subscribers.get(buildId);
    if (clients) {
      clients.delete(response);
      if (clients.size === 0) {
        this.subscribers.delete(buildId);
      }
    }
  }
}
```

**Events Streamed:**
| Event | Structure | Frequency | Purpose |
|-------|-----------|-----------|---------|
| `phase` | {phase, status, progress} | Once per phase start/end | Update stepper |
| `log` | {timestamp, level, phase, message} | Per log line | Append to log viewer |
| `quality` | {phase, score, details} | Once per phase end | Show scores |
| `cost` | {phase, tokens, usd} | Once per phase end | Track cost |
| `conflict` | {count, samples} | Once if conflicts | Flag review needed |
| `package` | {path, size, atoms} | Once at P5 end | Show download |
| `complete` | {status, totalTime} | Once at end | Enable download |
| `error` | {level, message, fatal} | On error | Display error banner |

## Pipeline Layer (Python)

### Execution Flow

**Entry Point: cli.py**
```
python cli.py build --config {yaml} --output-dir {dir}
  ↓
PipelineRunner.run()
  ↓
For each phase (P0-P5):
  ├─ Load input artifact (or skip if dependent)
  ├─ Run phase logic (Claude calls, processing)
  ├─ Emit SSE events (phase, log, quality, cost)
  ├─ Write output JSON
  └─ Handle conflicts (pause if P3 unresolved)
  ↓
On complete:
  ├─ Assemble package.zip
  ├─ Emit package event
  └─ Exit code 0 (or 1 on error)
```

### Phase Details

**P0: Baseline (Seekers)**
- Input: Domain name + seeker config JSON
- Process: URL discovery + web scraping via skill-seekers library
- Output: `baseline_summary.json` { topics: [...], refs_count, content_depth }
- Quality: Content depth (40%) + diversity (30%) + relevance (30%)

**P1: Audit (Claude Sonnet)**
- Input: Transcripts + baseline
- Process: Analyze topic density, category coverage, balance
- Output: `inventory.json` { topics: [...], categories: [...], stats }
- Quality: Topic density (30%) + depth distribution (25%) + category (20%) + balance (25%)

**P2: Extract (Claude Sonnet — Most Expensive)**
- Input: All sources (transcripts, PDFs, URLs, repo)
- Process: Chunk sources → Claude calls → extract KnowledgeAtoms
- Output: `atoms_raw.json` { atoms: [{ id, title, content, source, tokens }] }
- Quality: Structural quality (60%) + completeness (40%) + diversity bonus (+5)
- Cost: ~$5-15 per build (Sonnet input)

**P3: Dedup (Claude Haiku)**
- Input: atoms_raw.json
- Process: Pairwise similarity check → merge duplicates OR flag conflicts
- Output: `atoms_deduplicated.json` + `conflicts.json` (if not auto-resolved)
- Status: **PAUSES** if conflicts found → user must review
- Quality: Kept ratio vs ideal (90 pts) + merge bonus (10 pts) - penalties
- Resume: POST /api/builds/[id]/review with decisions → continue P3 → P4 → P5

**P4: Verify (Claude Haiku)**
- Input: atoms_deduplicated.json
- Process: Validate evidence, check integrity, sampling verification
- Output: `atoms_verified.json` { atoms: [...with evidence flags] }
- Quality: Evidence rate (50%) + match score (30%) + coverage (20%)

**P5: Architect (Claude Sonnet)**
- Input: atoms_verified.json
- Process: Generate SKILL.md, organize knowledge files, create references
- Output: SKILL.md + knowledge/*.md + references.json + package.zip
- Quality: Weighted rollup of P0-P5 (coefficients: 0.15, 0.10, 0.25, 0.15, 0.20, 0.15)
- Hard fail: < 50 atoms, > 40% conflicts, missing SKILL.md, token limit exceeded

**Output Structure:**
```
/data/builds/{buildId}/
├── config.yaml
├── baseline_summary.json    (P0)
├── inventory.json           (P1)
├── atoms_raw.json          (P2)
├── atoms_deduplicated.json (P3)
├── conflicts.json          (P3 optional)
├── atoms_verified.json     (P4)
├── SKILL.md                (P5)
├── knowledge/
│   ├── {atom_id}.md
│   └── ...
├── references.json         (P5)
├── package.zip             (P5 final)
└── pipeline.log            (all logs)
```

### Error Handling

**Phase-Level:**
- Try: run phase logic
- Catch: log error, emit error event, set fatal flag
- Result: status = "failed", error_message populated

**Retry Strategy:**
- Network errors (URL fetch): retry 3x with exponential backoff
- Claude API errors: retry 3x with exponential backoff (rate limits)
- File I/O errors: immediate fail

**Subprocess Communication:**
- Stdout: JSON-line events (parsed by build-runner)
- Stderr: Not captured (Node.js build-runner logs)
- Exit code: 0 (success), 1 (failed)

## Data Flow Diagrams

### Build Creation → Execution

```
1. User submits Wizard
        ↓
2. POST /api/builds
        ↓
3. createBuild() → DB insert (status: pending)
        ↓
4. Response { id: "uuid" }
        ↓
5. Browser redirect /build/[id]
        ↓
6. Meanwhile: api/builds route checks status=pending
        ↓
7. buildQueue.enqueue("uuid")
        ↓
8. If running < max: spawn subprocess
        ↓
9. buildRunner.spawnBuildProcess()
        ↓
10. update DB status → "running"
        ↓
11. Browser SSE subscribe /api/builds/[id]/logs
        ↓
12. Phase loop: stdout → parseJsonLine → DB + broadcast SSE
        ↓
13. On complete/error: update DB, emit "complete" event
        ↓
14. Browser enables download button
```

### SSE Event Loop

```
Python subprocess:
  log_event("phase", phase="p2", status="running") → stdout
        ↓
build-runner:
  parseJsonLine() → { type: "phase", phase: "p2", status: "running" }
        ↓
  updateBuildStatus(buildId, { current_phase: "p2" })
        ↓
  sseManager.publish(buildId, "phase", { phase: "p2", status: "running" })
        ↓
Browser (SSE client):
  eventSource.onmessage → { type: "phase", ... }
        ↓
  useBuildStream hook updates state
        ↓
  React re-renders phase-stepper (P2 active)
```

## File Storage Layout

**Directory Structure:**
```
data/
├── skill-factory.db          # SQLite (1 file)
├── skill-factory.db-wal      # Write-ahead log (auto-managed)
├── skill-factory.db-shm      # Shared memory (auto-managed)
│
├── builds/                   # Per-build artifacts
│   ├── {build_id_1}/
│   │   ├── config.yaml
│   │   ├── baseline_summary.json
│   │   ├── atoms_raw.json
│   │   ├── atoms_deduplicated.json
│   │   ├── atoms_verified.json
│   │   ├── SKILL.md
│   │   ├── knowledge/
│   │   │   ├── atom-001.md
│   │   │   └── ...
│   │   ├── references.json
│   │   ├── package.zip
│   │   └── pipeline.log
│   │
│   ├── {build_id_2}/
│   │   └── ...
│   │
│   └── ...
│
├── uploads/                  # Temporary uploads (cleaned after build)
│   ├── transcript_001.txt
│   ├── paper_002.pdf
│   └── ...
│
├── cache/                    # Baseline scraper output
│   ├── baselines/
│   │   ├── facebook-ads/
│   │   │   ├── urls.json
│   │   │   ├── content.json
│   │   │   └── summary.json
│   │   ├── google-ads/
│   │   └── ...
│   └── ...
│
└── templates/               # Optional: Template configs
    ├── fb-ads.yaml
    ├── google-ads.yaml
    └── ...
```

**Cleanup Policy:**
- Runs: Manual (Settings → Cleanup Now) or cron (PM2 ecosystem.config.js)
- Logic: Delete builds where `completed_at < (now - auto_cleanup_days)`
- Frees: `/data/builds/{id}/` directory + DB records

## Deployment Architecture

### PM2 Deployment

**Process Manager:**
- Single Node.js process (Next.js server)
- Auto-restart on crash
- Ecosystem config: CPU, memory, node args, env vars

**File Layout:**
```
/opt/skill-factory-web/
├── node_modules/
├── .next/
├── data/
├── pipeline/
├── ecosystem.config.js
├── deploy.sh
├── .env.local
└── ...
```

**Auto-start on Reboot:**
```bash
pm2 startup systemd  # Generate systemd service
pm2 save            # Persist process list
```

### Docker Deployment

**Multi-Stage Build:**
```dockerfile
# Stage 1: Node build
FROM node:20 AS builder
WORKDIR /app
COPY . .
RUN npm install && npm run build

# Stage 2: Python + Node runtime
FROM node:20
RUN apt-get update && apt-get install -y python3.11 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /app/.next .next
COPY --from=builder /app/node_modules node_modules
COPY pipeline/ pipeline/
COPY public/ public/
RUN pip3 install -r pipeline/requirements.txt
EXPOSE 3000
CMD ["node", ".next/standalone/server.js"]
```

**Volume Mounts:**
- `/app/data` → /data (SQLite, builds, uploads)
- `.env.local` → environment

### Nginx Reverse Proxy

**Config:**
```nginx
upstream skill_factory {
    server localhost:3000;
}

server {
    listen 80;
    server_name factory.example.com;

    location / {
        proxy_pass http://skill_factory;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_cache_bypass $http_upgrade;

        # CRITICAL for SSE:
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }

    # Redirect to HTTPS (after certbot setup)
    # return 301 https://$server_name$request_uri;
}
```

**Enable HTTPS:**
```bash
sudo certbot --nginx -d factory.example.com
```

## Scalability & Future Improvements

**Current Constraints:**
- Single SQLite file → works for < 10k builds
- In-memory queue → lost on restart (recovers from DB)
- Single Node process → concurrency via worker threads (not needed yet)
- Single Python interpreter per build → can't parallelize phases

**Future (v3):**
- PostgreSQL for multi-instance deployment
- Redis for distributed queue + caching
- Background worker service (separate from API)
- Phase parallelization within a build
- Skill marketplace (S3 storage + CDN)
- Multi-user with team management

## Performance Characteristics

| Operation | Typical Duration | Notes |
|-----------|------------------|-------|
| Build startup | 5-10 sec | Queue + spawn overhead |
| P0 Baseline | 20-60 sec | Web scraping (depends on domain) |
| P1 Audit | 30-90 sec | Claude API latency + tokens |
| P2 Extract | 3-10 min | Most expensive (Claude API) |
| P3 Dedup | 1-3 min | Claude API + conflict detection |
| P4 Verify | 1-3 min | Claude API + sampling |
| P5 Architect | 2-5 min | Final generation + packaging |
| **Total (Standard)** | **~15 min** | Varies by source size |
| SSE event latency | < 1 sec | JSON parse + broadcast |
| API response | < 500 ms | Median (DB + JSON) |
| Download package | < 10 sec | Zip compression on-disk |

## Security Architecture

**Authentication:**
- Single password (env var) → djb2 hash → cookie token
- Cookie: httpOnly, SameSite=Strict, 7-day TTL
- No user accounts (team-level access)

**Authorization:**
- Middleware guards /api/* routes (except /api/auth)
- No per-resource access control (monolithic team)

**Data Protection:**
- No PII stored (only build metadata)
- API keys in .env (not git-committed)
- SQLite file permissions: 0600 (read-write owner only)
- No logs to stdout (sensitive data risk)

**API Security:**
- HTTPS (via Nginx + certbot) in production
- Input validation on all endpoints
- Rate limiting (future)
- CORS: same-origin only (no external API)

## Monitoring & Observability

**Logs:**
- PM2: `pm2 logs skill-factory` → stdout/stderr
- Python: JSON-line events to stdout (captured by build-runner)
- Database: Query logs (future — currently none)

**Metrics (future):**
- Build success rate
- Average build duration per phase
- API latency percentiles
- Queue depth
- SSE connection count

**Error Tracking:**
- Sentry integration (future)
- Error logs in DB (future)
- Alert on repeated failures (future)
