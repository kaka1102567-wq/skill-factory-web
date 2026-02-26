# Code Health Report — Skill Factory Web

- **Ngay:** 2026-02-27
- **Commit:** 29470e6
- **Branch:** main

---

## Tong ket

| Tool | Scope | Issues | Critical | Warning | Info |
|------|-------|--------|----------|---------|------|
| tsc --noEmit | TypeScript (*.ts, *.tsx) | **0** | 0 | 0 | 0 |
| ruff | Python pipeline/ | **57** | 0 | 4 (ambiguous var) | 53 (unused imports, f-strings) |
| Semgrep | Full codebase (security) | **10** | 8 (XXE) | 2 (MD5) | 0 |
| pytest | Python tests (356) | **356 passed** | 0 failed | 0 errors | 0 skipped |
| React Doctor | React/Next.js | **381** | 14 (fetch-in-useEffect) | 82 | ~285 (unused files) |

**Overall: TypeScript clean, Python tests 100% pass, 10 security findings (8 in .claude/ skills, 2 in pipeline)**

---

## Critical — Phai fix ngay

### Security (tu Semgrep)

#### XXE Vulnerability — `use-defused-xml-parse` (8 findings)

| # | File | Line | Severity | Mo ta |
|---|------|------|----------|-------|
| 1 | `.claude/skills/document-skills/docx/ooxml/scripts/validation/redlining.py` | 34 | ERROR | `ET.parse()` vulnerable to XXE |
| 2 | same | 86 | ERROR | same |
| 3 | same | 88 | ERROR | same |
| 4 | `.claude/skills/document-skills/pptx/ooxml/scripts/validation/redlining.py` | 34 | ERROR | same |
| 5 | same | 86 | ERROR | same |
| 6 | same | 88 | ERROR | same |
| 7 | `.claude/skills/mcp-builder/scripts/evaluation.py` | 67 | ERROR | same |
| 8 | `.opencode/skills/mcp-builder/scripts/evaluation.py` | 67 | ERROR | same |

**Cach sua:** Thay `ET.parse()` bang `defusedxml.etree.ElementTree.parse()`. Install: `pip install defusedxml`.

#### Insecure Hash — MD5 (2 findings)

| # | File | Line | Severity | Mo ta |
|---|------|------|----------|-------|
| 1 | `pipeline/seekers/parser.py` | 36 | WARNING | `hashlib.md5()` for entry ID generation |
| 2 | `pipeline/seekers/parser.py` | 119 | WARNING | same |

**Cach sua:** Thay `hashlib.md5()` bang `hashlib.sha256()` va cat `[:10]` tuong tu.

### Type Errors (tu tsc)

**0 errors** — TypeScript compiles clean.

---

## Warning — Nen fix

### Python Lint (tu ruff) — 57 issues

| Rule | Count | Mo ta | Files chinh |
|------|-------|-------|-------------|
| F401 (unused import) | 31 | Import khong dung | `fetch_urls.py`, `logger.py`, `types.py`, `runner.py`, `p1_audit.py`, `p3_dedup.py`, `p4_verify.py`, `p55_smoke_test.py`, `p6_optimize.py`, `auto_discovery.py`, `scraper.py`, test files |
| F841 (unused variable) | 7 | Bien gan nhung khong dung | `analyze_repo.py:290`, `p0_baseline.py:120`, `p5_build.py:741`, `p6_optimize.py:72`, test files |
| F541 (f-string no placeholders) | 7 | f-string khong co variable | `mock_cli.py` (4), `p5_build.py` (3) |
| E741 (ambiguous var name) | 5 | Bien ten `l` trong list comprehension | `extract_pdf.py` (2), `test_e2e_dry.py`, `test_logger.py` (2) |
| E401 (multiple imports) | 2 | `import a, b` tren 1 dong | `test_phases.py` (2) |
| F401 (re-export) | 1 | `SkillSeekersAdapter` in `__init__.py` | `seekers/__init__.py` |

**44/57 auto-fixable** voi `ruff check --fix`.

### React/TypeScript (tu React Doctor) — 82 warnings

Xem chi tiet trong `docs/react-doctor-analysis.md`. Top issues:
- fetch() trong useEffect (14) — dung SWR/react-query
- Array index as key (19) — dung stable ID
- Missing keyboard listeners (6) + missing roles (6) — accessibility
- Too many useState (6) — dung useReducer
- Large components (2) — tach sub-components

---

## Info — Tuy chon

| Category | Count | Chi tiet |
|----------|-------|----------|
| Unused UI components | ~10 | shadcn/ui components chua dung (avatar, card, dialog, etc.) |
| Unused exports | 16 | buttonVariants, auth, db, build-queue, etc. |
| Unused types | 7 | PhaseInfo, KnowledgeAtom in various files |
| Unused files (.claude/, .opencode/) | ~250 | Tool config files — false positives |
| f-string without placeholders | 7 | mock_cli.py (4), p5_build.py (3) |

---

## Thong ke theo thu muc

| Thu muc | tsc | ruff | Semgrep | React Doctor | Tong |
|---------|-----|------|---------|--------------|------|
| app/ | 0 | — | 0 | 31 | 31 |
| components/ | 0 | — | 0 | 37 | 37 |
| lib/ | 0 | — | 0 | 8 | 8 |
| hooks/ | 0 | — | 0 | 3 | 3 |
| types/ | 0 | — | 0 | 1 | 1 |
| pipeline/phases/ | — | 14 | 0 | — | 14 |
| pipeline/clients/ | — | 0 | 0 | — | 0 |
| pipeline/commands/ | — | 5 | 0 | — | 5 |
| pipeline/core/ | — | 2 | 0 | — | 2 |
| pipeline/seekers/ | — | 3 | 2 | — | 5 |
| pipeline/orchestrator/ | — | 3 | 0 | — | 3 |
| pipeline/tests/ | — | 20 | 0 | — | 20 |
| .claude/skills/ | — | 0 | 7 | ~125 | ~132 |
| .opencode/skills/ | — | 0 | 1 | ~125 | ~126 |

---

## Top 10 Issues nen fix truoc

| # | Severity | Tool | File | Mo ta | Effort |
|---|----------|------|------|-------|--------|
| 1 | Critical | Semgrep | `pipeline/seekers/parser.py:36,119` | MD5 hash — thay SHA256 | 5 min |
| 2 | Warning | ruff | 31 files | Unused imports — `ruff check --fix` | 2 min |
| 3 | Warning | React Doctor | `app/build/[id]/page.tsx` | 313 lines, fetch-in-useEffect, 3+ setState | 1-2h |
| 4 | Warning | React Doctor | `components/build/skill-preview.tsx` | 5 inline renders + 10 index keys | 30 min |
| 5 | Warning | React Doctor | `app/compare/page.tsx:16` | useSearchParams without Suspense | 5 min |
| 6 | Warning | React Doctor | 6 files | Missing keyboard listeners + roles | 30 min |
| 7 | Warning | ruff | `pipeline/seekers/parser.py` + test files | Ambiguous var name `l` | 10 min |
| 8 | Warning | ruff | `pipeline/phases/p6_optimize.py:72` | Unused `use_light` variable | 2 min |
| 9 | Warning | ruff | `pipeline/commands/analyze_repo.py:290` | Unused `code_path` variable | 2 min |
| 10 | Info | ruff | `mock_cli.py` | 4 f-strings without placeholders | 2 min |

---

## False Positives (KHONG can fix)

| Issue | Ly do bo qua |
|-------|--------------|
| 8 XXE findings trong `.claude/skills/`, `.opencode/skills/` | Tool config scripts, khong phai application code. Chay trong sandbox. |
| 278 unused files (React Doctor) | ~250 la `.claude/`, `.opencode/`, `.venv/` — tool infrastructure files |
| Unused shadcn/ui components | Installed san cho future use |
| fetch-in-useEffect cho build pages | Build pages can real-time polling — SWR la upgrade tot nhung khong phai bug |
| `SkillSeekersAdapter` re-export warning | Can thiet cho package API |

---

## Test Health

| Metric | Value |
|--------|-------|
| Total | 356 tests |
| Passed | 356 (100%) |
| Failed | 0 |
| Errors | 0 |
| Skipped | 0 |
| Duration | 53.12s |
| Python | 3.14.3 |
| pytest | 9.0.2 |

---

## Tool Versions

| Tool | Version |
|------|---------|
| tsc (TypeScript) | 5.x (Next.js bundled) |
| ruff | latest (pip) |
| Semgrep | 1.153.0 |
| pytest | 9.0.2 |
| React Doctor | 0.0.29 |
| Node.js | (project bundled) |
| Python | 3.14.3 |
