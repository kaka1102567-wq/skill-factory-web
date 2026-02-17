# Skill Factory Web — Project Context

> Tài liệu cung cấp toàn bộ ngữ cảnh dự án cho agent/developer mới.
> Cập nhật: 2026-02-15 | Branch: main | Commit: e275a07

---

## 1. Tổng quan dự án

**Skill Factory** là ứng dụng web cho phép người dùng **biến video transcript thành AI skill package** — bộ kiến thức có cấu trúc mà AI assistant (Claude, Gemini...) có thể sử dụng trực tiếp.

**Workflow chính:**
```
User upload transcript → Wizard UI cấu hình → Pipeline 6 phases (Python + Claude API)
→ Knowledge atoms extracted → Verified against baseline docs
→ Packaged as SKILL.md + knowledge/*.md + references/ + ZIP
→ Xuất ra nhiều platform formats (Claude, OpenClaw, Antigravity)
```

**Tech stack:**
| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16.1.6, React 19.2, TypeScript 5, Tailwind CSS 4, shadcn/ui |
| Backend | Next.js API Routes (Node.js 20), better-sqlite3, SSE |
| Pipeline | Python 3.14, anthropic SDK, skill-seekers 3.0.0, httpx, tenacity |
| AI Model | Claude Sonnet 4 (default), Claude Haiku 4.5 (fallback) |
| Database | SQLite (single file: `data/sf.db`) |
| Auth | Password-based, HTTP-only cookie (7 ngày) |
| Deploy | Docker (multi-stage), PM2, Nginx |

---

## 2. Kiến trúc hệ thống

```
┌─────────────────────────────────────────────────────────────────┐
│                        BROWSER (React)                          │
│  Dashboard | Wizard | Build Monitor | Library | Settings        │
│                          ↕ fetch + SSE                          │
├─────────────────────────────────────────────────────────────────┤
│                    NEXT.JS API ROUTES                            │
│  /api/builds (CRUD)  /api/uploads  /api/settings  /api/auth    │
│  /api/builds/[id]/logs (SSE stream)                             │
│                          ↕                                      │
├───────────────────┬─────────────────────────────────────────────┤
│   SQLite (db.ts)  │  build-queue.ts → build-runner.ts           │
│   builds, logs,   │      ↓ spawn(python cli.py build ...)       │
│   templates,      │      ↓ stdout JSON lines → SSE → UI        │
│   settings        │      ↓ exit code → status update            │
├───────────────────┴─────────────────────────────────────────────┤
│                    PYTHON PIPELINE                               │
│  cli.py → PipelineRunner → P0→P1→P2→P3→P4→P5                  │
│  Claude API (anthropic SDK) + skill-seekers (baseline docs)     │
│  Output: per-platform packages (claude/openclaw/antigravity)    │
└─────────────────────────────────────────────────────────────────┘
```

### Giao tiếp Next.js ↔ Python
- **Spawn:** `build-runner.ts` → `child_process.spawn(python, [cli.py, "build", ...], { env })`
- **Stdout:** Python print JSON lines → `build-runner.ts` parse → DB + SSE broadcast
- **Event types:** `phase`, `log`, `quality`, `cost`, `conflict`, `package`
- **Exit code:** 0 = success/paused, non-0 = failed
- **Settings DB ưu tiên hơn env vars** cho `claude_api_key`, `python_path`...

---

## 3. Cấu trúc thư mục

```
skill-factory-web/
├── app/                          # Next.js App Router
│   ├── page.tsx                  # Dashboard
│   ├── layout.tsx                # Root layout (AuthGate + Sidebar)
│   ├── build/new/page.tsx        # Build Wizard (4-step)
│   ├── build/[id]/page.tsx       # Build Monitor (real-time SSE)
│   ├── library/page.tsx          # Skills Library
│   ├── templates/page.tsx        # Templates Catalog
│   ├── settings/page.tsx         # Settings
│   └── api/                      # API Routes (xem Section 7)
│
├── components/
│   ├── build/                    # build-wizard, phase-stepper, log-viewer,
│   │                               quality-report, conflict-review, step-*
│   ├── dashboard/                # build-card, recent-builds, stats-bar
│   ├── layout/                   # sidebar, auth-gate
│   └── ui/                       # shadcn/ui components (30+ files)
│
├── hooks/                        # use-build-stream, use-builds, use-auth
├── lib/                          # db, build-runner, build-queue, sse-manager,
│                                   config-generator, auth, cleanup, notifications
├── types/build.ts                # TypeScript interfaces
├── middleware.ts                  # Auth middleware
│
├── pipeline/                     # ★ PYTHON PIPELINE ENGINE ★
│   ├── cli.py                    # Entry point: build / resolve / status
│   ├── requirements.txt          # Python deps (anthropic, skill-seekers, etc.)
│   ├── core/
│   │   ├── types.py              # BuildConfig, KnowledgeAtom, PhaseResult...
│   │   ├── errors.py             # PhaseError, PipelineError
│   │   ├── config.py             # YAML loader + transcript discovery
│   │   ├── logger.py             # JSON stdout logger (PipelineLogger)
│   │   └── utils.py              # chunk_text, read_json, write_json, create_zip
│   ├── clients/
│   │   ├── claude_client.py      # Claude API (retry, cost, SHA256 response cache)
│   │   └── web_client.py         # Rate-limited HTTP client
│   ├── seekers/                  # Baseline knowledge engine
│   │   ├── adapter.py            # ★ SkillSeekersAdapter — wraps skill-seekers CLI
│   │   ├── scraper.py            # Legacy web scraper
│   │   ├── parser.py             # HTML→BaselineEntry parser
│   │   ├── cache.py              # SQLite cache for scraped entries
│   │   ├── lookup.py             # Topic/keyword lookup
│   │   └── taxonomy.py           # Domain-specific categories
│   ├── prompts/                  # Claude prompt templates
│   │   ├── p1_audit_prompts.py
│   │   ├── p2_extract_prompts.py # Includes P2_GAP_SYSTEM/P2_GAP_USER_TEMPLATE
│   │   ├── p3_dedup_prompts.py
│   │   ├── p4_verify_prompts.py
│   │   └── p5_build_prompts.py
│   ├── phases/                   # ★ 6-Phase implementations ★
│   │   ├── p0_baseline.py        # Baseline: skill-seekers load hoặc web scrape
│   │   ├── p1_audit.py           # Audit: topic inventory + coverage matrix
│   │   ├── p2_extract.py         # Extract: dual-stream (transcript + gap fill)
│   │   ├── p3_dedup.py           # Dedup: cross-source + per-category
│   │   ├── p4_verify.py          # Verify: keyword-based vs baseline refs
│   │   └── p5_build.py           # Build: SKILL.md + multi-platform packaging
│   ├── orchestrator/
│   │   ├── runner.py             # PipelineRunner — sequences P0→P5
│   │   └── state.py              # Checkpoint save/load/resume
│   └── tests/                    # 48 tests (all passing)
│       ├── conftest.py           # MockClaudeClient + fixtures
│       ├── test_phases.py        # 18 tests (P0-P5 + multi-platform)
│       ├── test_e2e_dry.py       # 11 tests (full pipeline dry-run)
│       ├── test_logger.py        # 10 tests (JSON event format)
│       ├── test_adapter.py       # 9 tests (skill-seekers adapter)
│       └── fixtures/
│
├── output/                       # skill-seekers baselines (external)
│   ├── fb-ads-meta/              # ★ Facebook Ads baseline (12 refs, WordStream)
│   │   ├── SKILL.md
│   │   ├── baseline_summary.json
│   │   └── references/           # 12 curated FB Ads articles
│   └── python3-test/             # Python docs baseline (testing)
│
├── data/                         # Runtime (gitignored)
│   ├── sf.db                     # SQLite database
│   ├── builds/<id>/              # Per-build: config.yaml, input/, output/
│   ├── uploads/<uuid>/           # Temp upload staging
│   └── cache/                    # Claude response cache + seekers cache
│
├── configs/seekers/              # skill-seekers scrape configs
├── docs/PROJECT-CONTEXT.md       # ★ THIS FILE ★
├── MASTER-PLAN.md                # Original implementation plan
├── Dockerfile                    # Multi-stage Docker build
└── package.json                  # Node.js dependencies
```

---

## 4. Pipeline chi tiết (6 Phases)

### Tổng quan

| Phase | Tên | Tool | Claude? | Input → Output |
|-------|------|------|---------|----------------|
| P0 | Baseline | Seekers | No | config → `baseline_summary.json` |
| P1 | Audit | Claude | Yes | transcripts → `inventory.json` (+ coverage matrix) |
| P2 | Extract | Claude | Yes | transcripts + baseline → `atoms_raw.json` |
| P3 | Dedup | Claude | Yes | atoms_raw → `atoms_deduplicated.json`, `conflicts.json` |
| P4 | Verify | Seekers | No* | atoms_dedup → `atoms_verified.json` |
| P5 | Build | Claude | Yes | atoms_verified → SKILL.md + knowledge/ + package.zip |

*P4 dùng keyword-based verification, không gọi Claude API.

### Phase function signature (tất cả giống nhau)
```python
def run_pN(config: BuildConfig, claude: ClaudeClient, cache: SeekersCache,
           lookup: SeekersLookup, logger: PipelineLogger) -> PhaseResult
```

### P0 — Baseline

**Mục đích:** Load baseline knowledge từ skill-seekers output hoặc web scrape.

**Logic:**
1. Nếu `seekers_output_dir` set → load `SKILL.md` + `references/*.md` trực tiếp
2. Nếu `baseline_sources` set → web scrape URLs, parse HTML, cache
3. Tạo `baseline_summary.json`: `{source, skill_md, references: [{path, content}], topics, total_tokens, score}`

**Chi phí:** $0 (không gọi Claude)

### P1 — Audit ★ Coverage Matrix

**Mục đích:** Tạo topic inventory từ transcripts, so sánh với baseline.

**Logic:**
1. Chunk transcripts (6000 tokens max)
2. Claude "Knowledge Auditor" → extract topics per chunk
3. Merge duplicate topics
4. **★ Coverage Matrix:** So sánh transcript topics vs baseline references
   - `OVERLAP` — topic có trong cả transcript và baseline
   - `UNIQUE_EXPERT` — chỉ có trong transcript (expert insight)
   - `GAP_TO_FILL` — có trong baseline nhưng transcript chưa cover
5. Score = quality * 0.7 + coverage * 0.3

**Output:** `inventory.json` với `topics[]`, `coverage_matrix`, `score`

### P2 — Extract ★ Dual-Stream

**Mục đích:** Extract Knowledge Atoms từ CẢ 2 nguồn.

**Logic:**
- **Stream A (Transcript):** Chunk → Claude "Atom Extractor" → atoms có `source="transcript"`
- **Stream B (Gap Fill):** Cho mỗi GAP_TO_FILL từ P1:
  - Tìm reference excerpt phù hợp (keyword matching)
  - Claude → extract 1-3 atoms có `source="baseline"`, `gap_filled=True`
  - Giới hạn `MAX_GAP_FILL_ATOMS = 10`
- **Merge:** transcript_atoms + gap_atoms
- `max_tokens=8192` cho transcript extraction

**Output:** `atoms_raw.json` — VD: 21 transcript + 10 gap-fill = 31 total

### P3 — Dedup ★ Cross-Source

**Mục đích:** Loại bỏ trùng lặp, phát hiện 3 loại vấn đề.

**Logic:**
1. **Cross-source dedup:** So sánh mọi cặp (transcript vs baseline):
   - `DUPLICATE` (keyword overlap ≥ 60%) → merge, giữ transcript
   - `CONTRADICTION` (40-60% overlap + negation/number mismatch) → flag
   - `OUTDATED` (baseline mới hơn) → replace
2. **Per-category dedup:** Group by category → Claude "Dedup Expert"
3. Nếu conflicts chưa resolve → PAUSE build

**Output:** `atoms_deduplicated.json`, `conflicts.json`, `conflict_summary`

### P4 — Verify

**Mục đích:** Cross-reference atoms với baseline documentation.

**Logic (skill-seekers mode):**
- Sample atoms (draft=30%, standard=70%, premium=100%)
- Cho mỗi atom, search baseline references bằng keyword matching
- Nếu ≥ 3 keywords match → `status="verified"` + evidence snippet
- Else → `status="verified"` + "Expert insight — not found in official docs"
- Confidence boost: +0.05 nếu baseline-verified

**Chi phí:** $0 (keyword-based, không gọi Claude)

### P5 — Build ★ Multi-Platform

**Mục đích:** Generate SKILL.md, knowledge files, đóng gói per-platform.

**Logic:**
1. Group atoms by category → pillars
2. Cho mỗi pillar: Claude "Knowledge Writer" → `knowledge/<pillar>.md`
3. Build SKILL.md: YAML frontmatter + routing logic + expert tips + advanced strategies
4. Copy baseline references → `references/`
5. **★ Multi-platform packaging:**

| Platform | Output | Chi tiết |
|----------|--------|----------|
| `claude` | SKILL.md + knowledge/ + references/ | Full YAML frontmatter, routing logic |
| `openclaw` | SKILL.md + knowledge/ + references/ | Simplified frontmatter (name, desc, version) |
| `antigravity` | system_instructions.md | 1 file duy nhất, inline tất cả (≤ 50K chars) |

6. **Backward compatible:** 1 platform → flat output. Nhiều platform → subdirectories.

**Output:** `metadata.json` (platforms_built), `package.zip`

---

## 5. Data Types quan trọng

### KnowledgeAtom
```python
@dataclass
class KnowledgeAtom:
    id: str                          # "atom_0001"
    title: str                       # "Facebook Pixel Setup"
    content: str                     # Full explanation (100-2000 chars)
    category: str                    # "campaign_management", "pixel_tracking"...
    tags: list[str]                  # ["pixel", "tracking"]
    source_video: str                # "transcript.txt"
    confidence: float                # 0.0-1.0
    status: str                      # raw → deduplicated → verified
    verification_note: str | None    # "Verified against baseline"
    baseline_reference: str | None   # Reference file path
    source: str = "transcript"       # ★ "transcript" | "baseline"
    gap_filled: bool = False         # ★ True nếu từ gap-fill stream
```

**Lifecycle:** P2 (raw) → P3 (deduplicated) → P4 (verified) → P5 (built)

### BuildConfig
```python
@dataclass
class BuildConfig:
    name: str                        # "Facebook Ads Vietnam"
    domain: str                      # "facebook-ads"
    language: str = "vi"
    quality_tier: str = "standard"   # draft | standard | premium
    platforms: list[str]             # ★ ["claude", "openclaw", "antigravity"]
    transcript_paths: list[str]      # Auto-discovered from input/
    output_dir: str
    seekers_output_dir: str = ""     # ★ Path to skill-seekers output
    claude_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"
```

### PhaseResult
```python
@dataclass
class PhaseResult:
    phase_id: str           # "p0"-"p5"
    status: str             # "done" | "failed"
    quality_score: float    # 0-100
    atoms_count: int
    api_cost_usd: float
    tokens_used: int
    output_files: list[str]
    metrics: dict           # Phase-specific (coverage_matrix, platforms_built...)
```

---

## 6. skill-seekers Integration

### Tổng quan
**skill-seekers** là Python package (v3.0.0) scrape documentation thành AI skills.
Pipeline tích hợp qua `SkillSeekersAdapter` (pipeline/seekers/adapter.py).

### Config
```yaml
# data/builds/<id>/config.yaml
seekers_output_dir: output/fb-ads-meta/   # Trỏ đến skill-seekers output
```

### Baseline Format (skill-seekers output)
```
output/fb-ads-meta/
├── SKILL.md              # Routing logic + knowledge pillars
├── baseline_summary.json # {source, skill_md, references[], topics[], score}
└── references/           # 12 curated markdown files
    ├── facebook-ad-targeting.md
    ├── facebook-ads-cost.md
    ├── facebook-learning-phase.md
    └── ... (12 files total)
```

### Cách tích hợp vào mỗi phase

| Phase | Sử dụng baseline | Chi tiết |
|-------|------------------|----------|
| P0 | Load baseline_summary.json | Đọc SKILL.md + references trực tiếp |
| P1 | Coverage matrix | So sánh transcript topics vs baseline topics/refs |
| P2 | Gap fill | Dùng baseline refs để extract atoms cho GAP_TO_FILL topics |
| P3 | Cross-source dedup | So sánh transcript vs baseline atoms |
| P4 | Keyword verification | Search baseline refs cho evidence |
| P5 | Copy references | Include baseline refs trong output + routing logic |

### Tạo baseline mới
Khi cần baseline cho domain mới, có 3 cách:
1. `skill-seekers scrape <url> --name <name>` (cho sites hỗ trợ)
2. WebFetch content → tạo references/*.md thủ công → tạo baseline_summary.json
3. Manual curation từ nhiều nguồn (đã dùng cho FB Ads baseline)

**Lưu ý:** skill-seekers không scrape được JS-rendered sites (Facebook, Wikipedia, PyPI).

---

## 7. API Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/api/auth` | GET/POST | Check/login auth |
| `/api/builds` | GET/POST | List/create builds |
| `/api/builds/[id]` | GET/DELETE | Get detail/delete build |
| `/api/builds/[id]/logs` | GET | SSE stream (real-time) |
| `/api/builds/[id]/download` | GET | Download package.zip |
| `/api/builds/[id]/stop` | POST | Stop build |
| `/api/builds/[id]/retry` | POST | Retry failed build |
| `/api/builds/[id]/review` | GET/POST | Conflict resolution |
| `/api/uploads` | POST | Upload files |
| `/api/settings` | GET/PUT | Settings CRUD |
| `/api/settings/cleanup` | POST | Cleanup old builds |
| `/api/stats` | GET | Dashboard statistics |
| `/api/templates` | GET | Templates catalog |

---

## 8. Database Schema (SQLite)

### builds
| Column | Type | Key fields |
|--------|------|-----------|
| id | TEXT PK | UUID |
| name, domain, status | TEXT | status: pending/queued/running/paused/completed/failed |
| current_phase | TEXT | p0-p5 |
| phase_progress | INTEGER | 0-100 |
| quality_score, api_cost_usd | REAL | Pipeline metrics |
| atoms_extracted, atoms_deduplicated, atoms_verified | INTEGER | Per-phase counts |
| config_yaml | TEXT | YAML content |
| review_status, review_data | TEXT | Conflict resolution |

### build_logs
| Column | Type | Description |
|--------|------|-----------|
| id | INTEGER PK | Auto-increment |
| build_id, level, phase, message | TEXT | Log entry |

### templates, settings
Pre-seeded templates (FB Ads, Google Ads, Blockchain, Custom) và settings (max_concurrent, python_path, etc.)

---

## 9. Stdout JSON Events (Python → Next.js)

```jsonc
{"event":"phase", "phase":"p2", "name":"Extract", "status":"running", "progress":50}
{"event":"phase", "phase":"p2", "name":"Extract", "status":"done", "progress":100}
{"event":"log", "level":"info", "phase":"p1", "message":"Coverage: 15 overlap, 10 unique, 10 gaps"}
{"event":"quality", "phase":"p2", "score":93.9, "pass":true, "atoms_count":31}
{"event":"cost", "api_cost_usd":0.15, "tokens_used":12000}
{"event":"conflict", "conflicts":[...], "count":3}
{"event":"package", "path":"./output/package.zip", "output_dir":"./output"}
```

---

## 10. Quality Tiers

| Tier | Verify Sample | Dedup Threshold | Max Atoms/Chunk | Estimated Cost |
|------|--------------|-----------------|-----------------|---------------|
| draft | 30% | 0.7 | 20 | $2-3 |
| standard | 70% | 0.8 | 15 | $5-10 |
| premium | 100% | 0.9 | 10 | $15-25 |

---

## 11. Testing

### Test suite: 48 tests (all passing)
```
pipeline/tests/test_phases.py     — 18 tests (P0-P5 + 6 multi-platform tests)
pipeline/tests/test_e2e_dry.py    — 11 tests (full pipeline dry-run)
pipeline/tests/test_logger.py     — 10 tests (JSON event format)
pipeline/tests/test_adapter.py    —  9 tests (skill-seekers adapter)
```

### Chạy tests
```bash
python -m pytest pipeline/tests/ -v     # 48 tests
```

### MockClaudeClient
- Returns structurally correct JSON per phase (matches system prompt keywords)
- Tracks: call_count, tokens, cost

### E2E test đã verified (real Claude API)
- **FB Ads transcript** (~88 lines, 8.9KB tiếng Việt)
- **Baseline:** 12 WordStream FB Ads articles
- **Results:** 21 transcript + 10 gap-fill = 31 atoms → 28-29 after dedup → verified → 5 pillars
- **Coverage:** 15 overlap, 10 unique expert, 10 gaps
- **Score:** 95.9%, Cost: $0.57-0.78
- **Output:** 3 platform directories (claude, openclaw, antigravity) + package.zip

---

## 12. Runtime Data Layout

```
data/builds/<build-id>/
├── config.yaml
├── input/
│   └── transcript.txt
└── output/
    ├── baseline_summary.json       # P0
    ├── inventory.json              # P1 (+ coverage_matrix)
    ├── atoms_raw.json              # P2
    ├── atoms_deduplicated.json     # P3
    ├── conflicts.json              # P3
    ├── atoms_verified.json         # P4
    ├── state.json                  # Checkpoint
    ├── metadata.json               # Platforms built, quality, etc.
    ├── package.zip                 # Final deliverable
    │
    │ ── Single platform (flat) ──
    ├── SKILL.md
    ├── knowledge/
    └── references/
    │
    │ ── Multi-platform (subdirs) ──
    ├── claude/
    │   ├── SKILL.md
    │   ├── knowledge/
    │   └── references/
    ├── openclaw/
    │   ├── SKILL.md              # Simplified frontmatter
    │   ├── knowledge/
    │   └── references/
    └── antigravity/
        └── system_instructions.md  # Single merged file
```

---

## 13. Environment Variables

```bash
# Auth
FACTORY_PASSWORD=change_me_please

# Pipeline
PYTHON_PATH=python3
PIPELINE_PATH=./pipeline
DATA_DIR=./data

# Claude API (required)
CLAUDE_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-sonnet-4-20250514

# Seekers
SEEKERS_CACHE_DIR=./data/cache
SEEKERS_CACHE_TTL_HOURS=168     # 7 days

# Windows-specific
PYTHONIOENCODING=utf-8           # Required for Vietnamese on Windows
```

**Note:** `claude_api_key`, `claude_model`, `python_path` có thể set qua Settings page (SQLite), `build-runner.ts` ưu tiên DB > env.

---

## 14. Git History (Development Timeline)

### Phase 1: Web App (Sprint 1-5)
```
90bf2d2 feat: Sprint 1-4 — Next.js app, UI, SQLite, templates, dashboard
4e50c71 feat: Sprint 5 — settings, notifications, cleanup, Dockerfile
```

### Phase 2: Pipeline Foundation (Session 1-6)
```
9c972d0 feat(pipeline): Session 1+2 — Foundation layer + Seekers engine
5d0eed5 feat(pipeline): Session 3 — Phases P0-P2
5d0d79a feat(pipeline): Session 4 — Phases P3-P5
6de2022 feat(pipeline): Session 5 — Orchestrator + CLI
793e098 feat(pipeline): Session 6 — Integration, tests, 33 tests pass
```

### Phase 3: Integration Fixes
```
28f2abf fix(pipeline): absolute imports in cli.py
236e437 fix(pipeline): pass API keys from Settings DB to subprocess
a320238 fix(pipeline): find transcripts in input/ dir
```

### Phase 4: skill-seekers Integration ★
```
a0f4ea3 feat(pipeline): add skill-seekers dependency
a644848 feat(seekers): add SkillSeekersAdapter
88debef feat(seekers): add scrape configs for Meta Ads
28c2eca test(seekers): add unit tests (9 tests)
c5c5788 feat(pipeline): upgrade P0 — load from skill-seekers output
a06f2cf feat(pipeline): upgrade P4 — verify against skill-seekers baseline
e961ede feat(pipeline): upgrade P5 — production SKILL.md with routing logic
```

### Phase 5: Pipeline Enhancement ★ (current)
```
c8156fd feat(pipeline): upgrade P1 coverage matrix + P2 dual-stream extraction
835a2c6 feat(pipeline): upgrade P3 cross-source dedup
8f41e2c fix(pipeline): increase P2 max_tokens to 8192
39d3e65 feat(baseline): add FB Ads baseline from WordStream (12 refs)
e275a07 feat(pipeline): add multi-platform packaging (claude/openclaw/antigravity)
```

---

## 15. Trạng thái hiện tại

### Đã hoàn thành
- [x] Web app (Dashboard, Wizard, Monitor, Library, Settings)
- [x] 6-phase pipeline (P0-P5) với Claude API
- [x] Real-time SSE streaming
- [x] skill-seekers integration (adapter, baseline loading, all phases)
- [x] Coverage matrix (P1) — transcript vs baseline topic comparison
- [x] Dual-stream extraction (P2) — transcript + gap fill from baseline
- [x] Cross-source dedup (P3) — DUPLICATE/CONTRADICTION/OUTDATED detection
- [x] Keyword-based verification (P4) — against baseline references
- [x] Production SKILL.md (P5) — routing logic, expert tips, advanced strategies
- [x] Multi-platform packaging (P5) — claude, openclaw, antigravity
- [x] Facebook Ads baseline (12 curated WordStream articles)
- [x] Claude response caching (SHA256 key)
- [x] Conflict detection + manual resolution UI
- [x] Auth, settings, Telegram notifications
- [x] Docker deployment
- [x] 48 tests passing

### Có thể làm tiếp
- [ ] Scrape thêm baselines cho domains khác (Google Ads, SEO, etc.)
- [ ] Thêm platform packagers mới
- [ ] Advanced conflict resolution UI (multi-way merge)
- [ ] Build pause/resume within phase (hiện chỉ pause ở P3)
- [ ] User management (hiện single password)
- [ ] Build versioning/rollback
- [ ] Prometheus metrics
- [ ] Kubernetes deployment

---

## 16. Lưu ý quan trọng cho agent

1. **Tests phải pass trước khi commit:** `python -m pytest pipeline/tests/ -v` (48 tests)
2. **Python stdout phải tuân thủ JSON event format** — build-runner.ts parse cứng
3. **Config.py auto-discovers transcripts** trong `input/` dir — không hardcode paths
4. **skill-seekers baseline** qua `seekers_output_dir` config — phải có `SKILL.md` + `baseline_summary.json` + `references/`
5. **Claude response cache** key = SHA256(system + user prompt) — không include max_tokens. Nếu thay đổi max_tokens mà bị cache hit sai → xóa file cache thủ công
6. **Windows:** cần `PYTHONIOENCODING=utf-8` cho tiếng Việt, `python3` → dùng full path
7. **Single platform → flat output** (backward compatible), **multi-platform → subdirectories**
8. **KHÔNG sửa mock_cli.py** — giữ làm fallback
9. **Settings DB ưu tiên hơn env vars** cho API keys, paths
10. **Emoji trong Python stdout** gây lỗi trên Windows cp1252 — logger dùng `ensure_ascii=True`
