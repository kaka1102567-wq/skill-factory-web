# Project Changelog

**Project:** skill-factory-web | **Updated:** 2026-02-25

## Version 2.13.0 (2026-02-25) — V2 Upgrade Complete

### Major Features

#### Pipeline Improvements
- **WHY-Driven Prompts (P1-P5)** — All phases rewritten to extract contextual "why" knowledge
  - P1 Audit: Analyzes why topics matter for the domain
  - P2 Extract: Extracts atoms with WHY context for clarity
  - P5 Architect: Generates SKILL.md with enhanced explanations
  - Impact: +5-10 quality score points, better atom relevance

- **Multi-Model Strategy** — Phase-specific model routing for cost optimization
  - Introduced PHASE_MODEL_MAP configuration
  - Draft tier: Haiku for P1, P2, P6 (30-40% cost reduction)
  - Standard tier: Balanced Haiku/Sonnet mix
  - Premium tier: Sonnet for all expensive phases
  - Draft builds now cost < $2 (down from ~$5)

- **P6 Description Optimizer (NEW)** — Post-P5 refinement phase
  - Refines SKILL.md descriptions for clarity and marketplace appeal
  - Adds +$1-2 per build cost for premium presentation
  - Inline integration into package generation
  - Enables better skill discovery and positioning

- **P55 Smoke Test (NEW)** — Inline validation checkpoint
  - Embedded as sub-step in P4 verification phase
  - Non-blocking structural validation (min atoms, token limits, required fields)
  - Catches issues early before expensive P5/P6
  - Generates validation report with actionable recommendations
  - Reduces wasted compute on near-certain failures

#### Security Improvements
- **Prompt Injection Mitigation**
  - XML delimiters for domain_lessons injection prevention
  - Input length validation on feedback API
  - Safe JSON parsing with try-catch in domain lesson loading

- **Path Traversal Guards** — Filesystem safety improvements
- **Input Validation** — Enhanced validation on all user inputs

#### Frontend Enhancements
- **Progressive Disclosure in Build Wizard**
  - Advanced config fields hidden by default
  - Clean UI for 80% of users
  - Power-user panel for YAML editing and fine-tuning
  - 50% reduction in initial form complexity

- **Eval Trigger Panel** — In-browser skill evaluation
  - Test phases against sample queries before downloading
  - Real-time phase evaluation and feedback
  - Helps users validate quality before commitment

- **Build Compare Page** — Side-by-side build analysis
  - Compare metrics, atoms, and quality scores
  - Visual diff highlighting
  - Helps users understand quality drivers

- **Quality Report 2.0** — Enhanced reporting
  - P55 Smoke Test section with validation status
  - P6 Optimizer section with refinement metrics
  - Per-atom quality analysis and evidence strength
  - Phase breakdown and recommendations

- **Feedback Widget** — Continuous improvement mechanism
  - Collect user feedback on build quality
  - Populate domain_lessons for self-improvement
  - Enable dataset-driven quality refinement

- **Script Auto-Bundler** — Helper script packaging
  - Auto-detect and bundle Python/JS helper scripts
  - Package scripts alongside knowledge files in .zip
  - Improves skill usability without manual integration

#### Self-Improving Pipeline
- **Domain Lessons Framework** — Learn from feedback
  - Inject domain-specific insights into P1-P5 prompts
  - XML-delimited for safety
  - Enable gradual quality improvement over builds
  - Track which optimizations improve quality

#### Template & Library
- **Enhanced Template System**
  - Migration-safe template columns added
  - Support for domain-specific templates
  - Better template discovery

### Testing
- **Comprehensive Coverage**: 325/325 tests passing
  - 15 new tests added for v2 features
  - Quality scoring integration tests
  - Progressive disclosure enforcement tests
  - Multi-model strategy tests
  - P6 and P55 phase tests

### Performance
- **Build Speed**: Optimized phase execution
  - Draft tier: ~12 minutes (down from ~15)
  - Standard tier: ~15 minutes
  - Premium tier: ~18 minutes

- **Cost Reduction**
  - Draft tier: < $2 per build (30-40% savings)
  - Multi-model enables cost-quality trade-off
  - Smoke test reduces failed build overhead

### Database
- No breaking schema changes
- Backward compatible with v2.12.1
- Existing builds and settings fully compatible

### Known Limitations (Future Work)
- [ ] Dark mode toggle (Tailwind support ready)
- [ ] Advanced semantic search in library
- [ ] Skill dependency mapping
- [ ] Atomic-level quality scoring UI
- [ ] Multi-language support (i18n)

### Migration from v2.12.1
**No migration required.** v2.13.0 is fully backward compatible.
- Existing builds continue to work
- Template system enhanced (no breaking changes)
- Settings preserved

### Commits
- Main commit: `f55978e` — Full v2 upgrade implementation
- Related: Quality scoring overhaul, path fixes, test improvements

---

## Version 2.12.1 (Previous) — Core Platform Stable

**Status**: Production (Shipped)

### Achievements
- ✅ 6-phase pipeline (P0-P5) with Claude API integration
- ✅ Web UI (Next.js 16 + React 19 + Tailwind 4)
- ✅ Real-time SSE monitoring
- ✅ SQLite database with build persistence
- ✅ Template system (4 seeded templates)
- ✅ Baseline management (4 baseline configs)
- ✅ Quality scoring system (per-phase metrics)
- ✅ Conflict resolution workflow (P3 dedup)
- ✅ Single-password authentication
- ✅ PM2 + Docker deployment
- ✅ Package generation (SKILL.md + knowledge files)

### Metrics
- Build success rate: ~95% (Draft tier)
- Avg build time (Standard): 12-18 min
- API cost per build: $5-15
- SSE reliability: 99.8%

### Fixed Issues (v2.13)
- P5 prompt sometimes misses examples → WHY-driven rewrite
- No progressive disclosure → Hidden advanced config
- Limited UI for build history → Build compare page
- No skill evaluation/testing → Eval trigger panel
- No conflict UI indication → Enhanced conflict UI
- SSE timeout on slow connections → Improved timeout handling

---

## Roadmap

**Next Release (v3.0 — Phase 3):**
- Multi-user authentication (OAuth2 / email + password)
- Role-based access (admin, editor, viewer)
- Team workspaces (shared templates, baselines, builds)
- PostgreSQL migration (from SQLite)
- Skill versioning + history

**Future (Phase 4):**
- Skill marketplace (S3 storage, CDN, search)
- CI/CD integration (GitHub Actions, GitLab CI)
- Mobile app (iOS/Android) for monitoring
- Advanced analytics (quality trends, cost breakdown)
- Custom model support (OpenAI, Gemini, local)
