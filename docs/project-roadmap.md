# Development Roadmap

**Project:** Skill Factory Web | **Version:** 2.12.1 | **Updated:** 2026-02-25 | **Branch:** v2-upgrade

## Current Status

| Metric | Value |
|--------|-------|
| **Version** | 2.13.0 |
| **Phase 1** | ✅ COMPLETE (Core pipeline + Web UI) |
| **Phase 2** | ✅ COMPLETE (v2-upgrade merged, all 10 patches shipped) |
| **Phase 3** | 📋 PLANNED (Multi-user, team features) |
| **Phase 4** | 📋 FUTURE (Mobile, marketplace, CI/CD) |

## Phase 1: Core Platform (COMPLETE)

**Duration:** 3-4 months | **Status:** Shipped to production

**Achievements:**
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

**Key Metrics:**
- Build success rate: ~95% (Draft tier)
- Avg build time (Standard): 12-18 min
- API cost per build: $5-15
- SSE reliability: 99.8%

**Known Limitations:**
- P5 prompts need refinement (improvements planned in v2 Sprint 1)
- No progressive disclosure (all config visible)
- Limited UI for build history + filtering
- No skill evaluation/testing in UI
- No self-improvement loop

## Phase 2: Quality & UX Improvements (COMPLETE)

**Duration:** 4 weeks | **Merged:** 2026-02-25 | **Release:** v2.13.0

**Branch:** `v2-upgrade` (merged to main)

### Sprint 1: Prompt & Architecture Rewrite (COMPLETE)

**Focus:** Improve quality output, reduce costs, better phase reasoning

**Patches Delivered:**
1. ✅ **P5 Prompt Rewrite** — WHY-driven content with structure examples
2. ✅ **Progressive Disclosure** — Hidden advanced config in P5 step
3. ✅ **WHY-Driven Prompts** (P1-P5) — Contextual atom extraction
4. ✅ **Multi-Model Strategy** — PHASE_MODEL_MAP routing (Draft/Standard/Premium)

**Results:**
- All P1-P5 prompts rewritten for clarity and context
- Multi-model enables 30-40% cost reduction for Draft tier
- Progressive disclosure reduces initial config fields by 50%
- Test coverage: 325/325 tests passing

### Sprint 2: Next Phase (P6) & Validation (COMPLETE)

**Focus:** Add description optimizer, quick validation layer

**Patches Delivered:**
5. ✅ **P6 Description Optimizer** (NEW PHASE)
   - Refines SKILL.md descriptions for clarity and brevity
   - Claude-powered endpoint for marketplace quality
   - Cost: $1-2 additional per build

6. ✅ **Smoke Test (P55)** (INLINE VALIDATION)
   - Embedded in P4 verification phase
   - Catches issues before P5 (min atoms, structure, tokens)
   - Non-blocking quality check with recommendations
   - Improves reliability and reduces wasted compute

**Results:**
- P6 enabled in frontend (PhaseId, PHASES, PHASE_COLORS)
- P55 integrated as inline sub-step in verification
- Quality report 2.0 displays smoke test and P6 sections

### Sprint 3: UI Features (COMPLETE)

**Focus:** Build history, evaluation, templating

**Patches Delivered:**
7. ✅ **Eval Trigger Panel** — Test phase outputs in browser
8. ✅ **Build Compare Page** — Side-by-side build comparison
9. ✅ **Script Auto-Bundler** — Auto-attach scripts in P5 packaging

**Results:**
- Users can evaluate builds before downloading
- Side-by-side comparison for quality assessment
- Scripts automatically included in package.zip
- New APIs: Reports, Compare, Feedback

### Sprint 4: Analytics & Self-Learning (COMPLETE)

**Focus:** Quality insights, continuous improvement

**Patches Delivered:**
10. ✅ **Quality Report 2.0** — Smoke test + P6 sections with insights
11. ✅ **Self-Improving Pipeline** — Domain lessons injection framework
12. ✅ **Feedback Widget** — User feedback collection for continuous learning

**Results:**
- Enhanced quality report with per-phase breakdown
- Domain lessons framework for self-improvement
- Feedback collection mechanism for quality refinement
- Logger sub-phase guard for robustness

**Total v2 Duration:** 4 weeks (2026-02-25, all phases complete)

## Phase 2 Success Criteria

| Criterion | Target | Validation |
|-----------|--------|-----------|
| Build quality score (avg) | > 85 | 10 manual audits per tier |
| Cost per build (Draft) | < $2 | Cost tracking in DB |
| Cost per build (Standard) | < $8 | Cost tracking in DB |
| SSE uptime | > 99.5% | Monitor during testing |
| P5 output quality | > 80 atoms well-formed | Schema + content validation |
| UI test coverage | > 80% | Jest snapshots + playwright |
| Python test coverage | > 85% | pytest coverage report |
| Zero regressions | All Phase 1 features work | Regression test suite |

## Merge & Release Plan

**v2-upgrade → main:**
1. All 10 patches merged and tested
2. Regression test suite passes
3. 5 production-like test builds succeed
4. Code review from lead
5. Deploy to staging for final validation
6. Merge to main, tag v2.13.0
7. Deploy to production

**Estimated Date:** 2026-03-21

**Breaking Changes:** None (backward compatible)

## Phase 3: Multi-User & Team (FUTURE)

**Duration:** 6-8 weeks | **Target Start:** 2026-04

**Vision:** Enable team collaboration, skill marketplace, advanced analytics

**Planned Features:**
- Multi-user authentication (OAuth2 / email + password)
- Role-based access (admin, editor, viewer)
- Team workspaces (shared templates, baselines, builds)
- Skill versioning + history
- Approval workflow (draft → review → published)
- Usage analytics (who uses which skills)
- Shareable skill links
- Comments + feedback on builds

**Technical Changes:**
- PostgreSQL migration (from SQLite)
- User/team database tables
- Workspace isolation in queries
- Audit logging
- Rate limiting per user/team

**Success Metrics:**
- 5+ concurrent teams
- < 100ms API latency (P95)
- Zero data leaks between teams

## Phase 4: Ecosystem & Scale (FUTURE)

**Duration:** 10-12 weeks | **Target Start:** 2026-06

**Vision:** Marketplace, automation, deep insights

**Planned Features:**
- Skill marketplace (S3 storage, CDN, search, rating)
- CI/CD integration (GitHub Actions, GitLab CI)
- Mobile app (iOS/Android) for monitoring
- Advanced analytics (quality trends, cost breakdown)
- Webhooks + API for third-party integration
- Scheduled builds (cron jobs)
- Batch build processing
- Custom model support (OpenAI, Gemini, local)

**Technical Changes:**
- S3 + CloudFront for storage
- API versioning + client SDKs
- Webhook delivery system
- Task scheduler (Bull queue)
- Analytics database

**Success Metrics:**
- 100+ published skills in marketplace
- 50+ API integrations
- 10k+ monthly builds

## Backlog (Unscheduled)

**Nice-to-have Features:**
- [ ] Dark mode toggle (Tailwind supports, just need UI)
- [ ] Slack integration (alongside Telegram)
- [ ] Custom branding for SaaS customers
- [ ] Skill templates gallery (100+ pre-built)
- [ ] A/B testing framework (compare 2 configs)
- [ ] Atom-level quality scoring (beyond phase-level)
- [ ] Multi-language support (i18n)
- [ ] Advanced search in library (semantic search)
- [ ] Skill dependency mapping

**Technical Debt:**
- [ ] Reduce build-runner.ts size (> 950 LOC)
- [ ] Add e2e tests (Playwright)
- [ ] Database query optimization (analyze EXPLAIN PLAN)
- [ ] Dockerfile security hardening
- [ ] Rate limiting implementation
- [ ] Error tracking integration (Sentry)
- [ ] APM instrumentation (NewRelic, DataDog)
- [ ] Load testing (k6, locust)

## Known Issues & Fixes (v2.12.1)

| Issue | Severity | Status | ETA Fix |
|-------|----------|--------|---------|
| P5 prompt sometimes misses examples | Medium | v2-upgrade Sprint 1 | 2026-03-07 |
| SSE timeout on slow connections | Low | Known, not blocking | v3 |
| SQLite lock during cleanup | Low | Rare, PM2 restart workaround | v3 (PostgreSQL) |
| No conflict UI indication | Medium | v2-upgrade Sprint 1 | 2026-03-07 |
| Telegram test not obvious | Low | v2-upgrade Sprint 3 | 2026-03-18 |

## Metrics Dashboard (Tracking)

**Build Success Rate:**
- Target: > 95%
- Current (Phase 1): ~94%
- v2 Goal: > 96%

**Average Build Cost (Standard tier):**
- Target: < $10
- Current (Phase 1): $8-12
- v2 Goal: < $8

**Average Build Time (Standard tier):**
- Target: < 15 min
- Current (Phase 1): 12-18 min
- v2 Goal: < 12 min (via cost optimization)

**Quality Score (avg):**
- Target: > 80
- Current (Phase 1): 78-82
- v2 Goal: > 85

**User Satisfaction:**
- Surveys: (not yet conducted)
- NPS: (future)

## Dependencies & Risks

### Technical Dependencies
- Anthropic API stability (single vendor)
  - Mitigation: Add OpenAI fallback in Phase 4
- Python subprocess stability
  - Mitigation: Robust error handling, orphan recovery
- Database file system availability
  - Mitigation: PostgreSQL migration in Phase 3

### Resource Constraints
- Small team (1-2 developers)
  - Mitigation: Prioritize high-impact features, avoid scope creep
- Limited budget for AI API calls
  - Mitigation: Multi-model strategy, cost tracking, quality tiers

### Market Risks
- Competing tools (ChatGPT plugins, competitor skill builders)
  - Mitigation: Focus on ease of use, quality, speed
- LLM model changes (new API formats)
  - Mitigation: Abstract model calls, stay on latest anthropic SDK

## Release Schedule

| Version | Phase | Release Date | Status |
|---------|-------|--------------|--------|
| 2.12.1 | Phase 1 | ✅ Shipped | Production |
| 2.13.0 | Phase 2 (v2-upgrade) | ✅ 2026-02-25 | Shipped |
| 3.0.0 | Phase 3 (Multi-user) | 2026-05-01 | Planned |
| 3.5.0 | Phase 4 (Ecosystem) | 2026-07-01 | Planned |

## Documentation Updates (v2.13)

**Completed:**
- ✅ Updated roadmap with all Sprint outcomes
- ✅ System architecture updated with P6/P55 phases
- ✅ Code standards reflect multi-model strategy + prompt rewrites

**Before v3.0 Release:**
- [ ] Document team/workspace model
- [ ] Create admin setup guide
- [ ] Add PostgreSQL migration guide
- [ ] Document OAuth integration

## How to Track Progress

**Daily:**
- Check v2-upgrade branch commits
- Review test results in CI/CD

**Weekly:**
- Team sync on patch status
- Update issue tracker

**Sprint-level:**
- Sprint review demo
- Update roadmap with achievements
- Identify blockers

## Contributing

**For developers joining the project:**
1. Read [Project Overview & PDR](./project-overview-pdr.md)
2. Read [System Architecture](./system-architecture.md)
3. Read [Code Standards](./code-standards.md)
4. Pick task from roadmap (v2-upgrade branch)
5. Create feature branch off v2-upgrade
6. Reference issue + roadmap item in PR

**Question or blocker?** Check existing docs first, then ask lead.

## Future Vision (5-Year)

**2026:** Core platform (Phases 1-2) + multi-user foundation (Phase 3)
**2027:** Ecosystem + marketplace (Phase 4) + international expansion
**2028:** Custom models + edge deployment + advanced analytics
**2029:** Industry standard for AI skill creation (1000+ organizations)
**2030:** Autonomous skill improvement + self-learning pipelines

**Mission:** Make AI skill creation as easy as building a web app.
