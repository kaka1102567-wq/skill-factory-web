# Skill Factory Web — Product Overview & PDR

**Version:** 2.12.1 | **Status:** Active (v2-upgrade branch) | **Updated:** 2026-02-25

## Vision & Goals

**Mission:** Enable rapid conversion of raw knowledge sources (transcripts, PDFs, URLs, repositories) into production-ready AI Skill packages that can be used by Claude, OpenAI, or other LLM platforms.

**Goals:**
1. Reduce skill creation time from weeks → hours via automated pipeline
2. Ensure quality through multi-phase validation (P0-P5)
3. Lower AI costs via efficient processing and Claude model optimization
4. Provide intuitive web UI for non-technical users
5. Support multiple knowledge domains via template system

**Target Users:**
- Product teams creating custom AI assistant skills
- Knowledge management teams building skill libraries
- AI engineers automizing skill packaging
- External customers (SaaS model — future)

## Feature List (Current Release)

### Build Management
- **Build Wizard:** 4-step guided creation (Template → Upload → Config → Review)
- **Quality Tiers:** Draft (fast), Standard (balanced), Premium (exhaustive)
- **Build Monitoring:** Real-time SSE streaming of logs, phases, scores, costs
- **Build History:** List, filter, retry, delete, download packages
- **Conflict Review:** UI for resolving deduplication conflicts during P3

### Pipeline Processing
- **P0 Baseline:** Web scraping + document discovery via skill-seekers
- **P1 Audit:** Transcript analysis → topic inventory (Claude Sonnet)
- **P2 Extract:** Knowledge atom extraction from all sources (Claude Sonnet)
- **P3 Dedup:** Duplicate detection + merge suggestions (Claude Haiku)
- **P4 Verify:** Evidence validation + integrity checks (Claude Haiku)
- **P5 Architect:** SKILL.md + knowledge files + package generation (Claude Sonnet)
- **Quality Scoring:** Per-phase metrics (0-100) with weighted rollup

### Data Management
- **Templates:** Pre-configured skill templates (FB Ads, Google Ads, Blockchain, Custom)
- **Baselines:** Domain-specific reference documents + seekers configs
- **Settings:** API keys, paths, cleanup, notifications, concurrency
- **Cleanup:** Auto-delete old builds based on retention policy

### Infrastructure
- **SSE Streaming:** Real-time event push to browser (phase, log, quality, cost, error)
- **Build Queue:** FIFO with configurable concurrency (default: 2 concurrent)
- **Auth:** Single password (cookie-based, 7-day TTL)
- **Notifications:** Optional Telegram bot for build completion
- **Download:** Generate .zip with SKILL.md + knowledge/*.md + references/

## Six-Phase Pipeline

| Phase | Name | Model | Input | Output | Purpose |
|-------|------|-------|-------|--------|---------|
| P0 | Baseline | skill-seekers + web | Domain seeds | baseline_summary.json | Pre-pipeline content discovery |
| P1 | Audit | Claude Sonnet | Transcripts | inventory.json | Topic density + category audit |
| P2 | Extract | Claude Sonnet | All sources | atoms_raw.json | Knowledge atom extraction (60% effort) |
| P3 | Dedup | Claude Haiku | atoms_raw | atoms_deduplicated.json | Duplicate merging + conflict resolution |
| P4 | Verify | Claude Haiku | atoms_dedup | atoms_verified.json | Evidence validation + integrity |
| P5 | Architect | Claude Sonnet+Haiku | atoms_verified | SKILL.md + knowledge/*.md | Package assembly + output formatting |

**Pipeline Outputs:**
- Per-phase JSON artifacts (committed to `/data/builds/{id}/`)
- Quality scores (0-100 per phase)
- API cost tracking (USD per phase)
- Token counts (for cost reporting)
- Conflict list (if P3 detects issues)
- Final package: `package.zip` (SKILL.md + knowledge files + references.json)

## Quality Scoring System

**Per-Phase Metrics:**
- **P0:** Content depth (40%) + diversity (30%) + relevance (30%) → range 0-100
- **P1:** Topic density (30%) + depth distribution (25%) + category coverage (20%) + balance (25%)
- **P2:** Structural quality (60%) + completeness (40%) + diversity bonus (+5 max)
- **P3:** Kept ratio vs ideal (90 pts) + merge bonus (10 pts) - integrity penalties
- **P4:** Evidence rate (50%) + match score (30%) + sampling coverage (20%)
- **P5:** Weighted rollup of P0-P5 with coefficients {0.15, 0.10, 0.25, 0.15, 0.20, 0.15} + hard fail penalties

**Quality Rollup:** `final_score = Σ(phase_score × weight) - penalties`

**Hard Failures (score → 0):**
- < 50 atoms in P5
- > 40% conflicts unresolved
- Missing SKILL.md structure
- Token limit exceeded

## Build Wizard (4 Steps)

**Step 1: Template Selection**
- Display template catalog (name, domain, icon, description)
- User picks template → loads domain-specific config + seekers config
- Option for "Custom" → blank config

**Step 2: Data Upload**
- Accept: transcripts (txt, pdf), URLs (comma-separated), repo links
- File upload with progress bar
- URL discovery via baseline seekers
- Validate MIME types + file sizes (max 100MB per file)

**Step 3: Configuration**
- Build name (required)
- Domain (auto-set from template, editable)
- Quality tier (Draft/Standard/Premium) → affects phase concurrency
- Advanced: edit YAML config directly (for power users)

**Step 4: Review**
- Display processed config YAML
- Show estimated cost (based on source volume)
- Display file/URL count
- Confirm → create build (status: pending)

## Real-Time SSE Monitoring

**Events Streamed to UI:**
| Event | Data | Use Case |
|-------|------|----------|
| `phase` | {phase, status, progress} | Update phase stepper |
| `log` | {timestamp, level, phase, message} | Append to live log viewer |
| `quality` | {phase, score, details} | Update quality card |
| `cost` | {phase, tokens, usd} | Track cost progression |
| `pre-step` | {phase} | Notify before phase start |
| `conflict` | {count, samples} | Flag P3 conflict review |
| `package` | {path, size, atoms} | Show final artifact |
| `complete` | {status, time} | End stream + enable download |
| `error` | {level, message, fatal} | Display error banner |

## Conflict Resolution Workflow

**Trigger:** P3 deduplication identifies duplicates with confidence > 70%.

**UI Flow:**
1. Build pauses at P3 end
2. User navigates to "Review Conflicts" section
3. View conflict pairs (A vs B) with evidence
4. User action per conflict: Keep A | Keep B | Merge | Discard
5. Save decisions → Python CLI resumes with custom conflict_resolution.json
6. Pipeline continues P3 → P4 → P5

**Conflict Data Structure:**
```yaml
conflicts:
  - id: "c001"
    type: "semantic_duplicate"
    confidence: 0.87
    atom_a: {id: "a123", content: "..."}
    atom_b: {id: "a456", content: "..."}
    suggested_merge: "..."  # optional pre-merge
```

## Authentication & Security

**Auth Mechanism:**
- Single password (env var `FACTORY_PASSWORD`, default: `skillfactory2025`)
- Hash with djb2 → convert to base36 → store in cookie `sf_auth`
- Cookie: httpOnly, 7-day TTL, SameSite=Strict
- Middleware guards all `/api/*` routes except `/api/auth`

**No User Accounts:** Session cookie only — single password for entire team.

**Future (v3):** OAuth2 / multi-user with role-based access.

## Notification System (Optional)

**Telegram Bot Integration:**
- User configures bot token + chat ID in settings
- Events: build complete, build failed, phase milestone
- Message format: build name + status + quality score + cost
- Test button in settings UI

## Database Schema (5 Tables)

| Table | Columns | Purpose |
|-------|---------|---------|
| `builds` | id, name, domain, status, current_phase, phase_progress, config_yaml, quality_score, atoms_*, api_cost_usd, output_path, package_path, review_status | Build metadata |
| `build_logs` | id, build_id (FK), timestamp, level, phase, message, metadata | Real-time pipeline logs |
| `templates` | id, name, domain, description, icon, config_yaml, is_default, usage_count | Template catalog |
| `settings` | key, value, updated_at | Key-value store (API keys, paths, flags) |
| `baselines` | id, domain, name, config_path, seekers_output_dir, status, source_urls, refs_count, topics_count | Baseline registry |

## File Storage

**Directory Layout:**
```
data/
├── skill-factory.db           # SQLite (WAL mode)
├── builds/                    # Per-build output
│   ├── {build_id}/
│   │   ├── config.yaml
│   │   ├── baseline_summary.json
│   │   ├── atoms_raw.json
│   │   ├── atoms_deduplicated.json
│   │   ├── atoms_verified.json
│   │   ├── conflicts.json
│   │   ├── package.zip
│   │   ├── SKILL.md
│   │   ├── knowledge/
│   │   ├── references.json
│   │   └── pipeline.log
│   └── ...
├── uploads/                   # Temporary upload cache
├── cache/                     # Baseline seekers output
└── templates/                 # Template configs (optional)
```

## Deployment Options

### Option 1: PM2 (Linux/Mac)
```bash
./deploy.sh  # Installs PM2, starts process
pm2 startup  # Auto-restart on reboot
```

### Option 2: Docker
```bash
docker build -t skill-factory .
docker run -d -p 3000:3000 \
  -v $(pwd)/data:/app/data \
  -e FACTORY_PASSWORD=... \
  -e ANTHROPIC_API_KEY=... \
  skill-factory
```

### Option 3: Manual (Node + Python)
```bash
npm install && npm run build && npm start &
# In another terminal: python pipeline/cli.py (for testing)
```

## v2-Upgrade Plan (10 Patches, 4 Sprints)

**Branch:** `v2-upgrade` | **Target:** Merge to main by end of Sprint 4

### Sprint 1 (In Progress)
- **P5 Prompt Rewrite:** Enhanced SKILL.md generation with better structuring
- **Progressive Disclosure:** Hide advanced config by default, power-user panel
- **WHY-Driven Prompts:** Add contextual reasoning to P2-P5 Claude prompts
- **Multi-Model Strategy:** Sonnet for heavy lifting, Haiku for verification (cost optimization)

### Sprint 2
- **P6 Description Optimizer:** New phase for polishing skill descriptions
- **Smoke Test (P5.5):** Quick validation before P6 (catch issues early)

### Sprint 3-4
- **Eval Query UI:** Test skills against sample queries in UI
- **Build History Dashboard:** Filter by domain, status, date range
- **Script Bundler:** Package Python helper scripts with skills
- **Quality Report 2.0:** Detailed per-atom analysis + recommendations
- **Self-Improving Pipeline:** Learn from manual conflict resolutions
- **Template Manager UI:** Create/edit templates in UI (vs YAML only)

## Non-Functional Requirements

**Performance:**
- Build startup: < 5 sec (UI → queue → subprocess)
- SSE latency: < 1 sec (event → browser)
- API response: < 500ms (median)
- DB query: < 100ms (median)
- Concurrent builds: configurable 1-4 (default 2)

**Reliability:**
- Build recovery: resume from last checkpoint on crash
- Queue persistence: in-memory FIFO with orphan recovery on startup
- Database: WAL mode + foreign key constraints
- Cleanup: auto-delete builds > N days (default 30)

**Scalability:**
- Single-file SQLite suitable for < 10k builds
- Future: PostgreSQL migration for multi-instance setup
- S3/cloud storage for package archival

**Security:**
- No plaintext passwords in code/git
- HTTP-only cookies
- CORS disabled (single-origin)
- Input validation on all API endpoints
- Rate limiting (future)

**Cost Control:**
- Phase cost tracking (Claude API + tokens)
- Quality tier affects prompt complexity (Draft < Standard < Premium)
- Token estimation in UI before build
- API key rotation in settings

## Success Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Build success rate | > 95% | TBD |
| Avg build time (Standard) | < 15 min | TBD |
| Quality score (avg) | > 80 | TBD |
| Cost per build (Standard) | < $10 | TBD |
| UI load time | < 2 sec | TBD |
| SSE reliability | 99.9% | TBD |

## Roadmap

**Phase 1 (Complete):** Core pipeline (P0-P5) + Web UI + Quality scoring

**Phase 2 (v2-upgrade):** P5 rewrite + P6 + UI enhancements + cost optimization

**Phase 3 (Future):** Multi-user + team management + skill marketplace + CI/CD integration

**Phase 4 (Future):** Mobile app + API for third-party integration + advanced analytics
