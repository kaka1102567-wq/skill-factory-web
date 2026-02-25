# Development Roadmap

**Project:** Skill Factory Web | **Version:** 2.12.1 | **Updated:** 2026-02-25 | **Branch:** v2-upgrade

## Current Status

| Metric | Value |
|--------|-------|
| **Version** | 2.12.1 |
| **Phase 1** | ✅ COMPLETE (Core pipeline + Web UI) |
| **Phase 2** | 🚀 IN PROGRESS (v2-upgrade branch, Sprint 1-4) |
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

## Phase 2: Quality & UX Improvements (IN PROGRESS)

**Duration:** 4-6 weeks | **Target Merge:** End of Sprint 4 (est. 2026-03-21)

**Branch:** `v2-upgrade` | **Tracking:** UPGRADE-PLAN-FINAL.md

### Sprint 1: Prompt & Architecture Rewrite (CURRENT)

**Focus:** Improve quality output, reduce costs, better phase reasoning

**Patches:**
1. **P5 Prompt Rewrite** (HIGHEST PRIORITY)
   - Current: Generic SKILL.md generation
   - Goal: Enhanced structure, better Why-driven content, examples
   - Impact: Quality score +5-10 pts
   - Effort: 3-4 days
   - Success: P5 output rated > 85 quality by manual review

2. **Progressive Disclosure**
   - Hide advanced config by default (clean UI for 80% users)
   - Power-user panel: YAML editor, seekers tuning, quality weights
   - Impact: UX improvement (easier onboarding)
   - Effort: 2 days
   - Success: 50% reduction in config form fields on initial view

3. **WHY-Driven Prompts** (P2-P5)
   - Current: "Extract knowledge atoms"
   - Goal: "Extract why knowledge matters, why pattern matters"
   - Impact: More contextual, fewer generic atoms
   - Effort: 2 days
   - Success: Manual audit shows > 80% atoms have WHY context

4. **Multi-Model Strategy**
   - Current: Sonnet for P1, P2, P5; Haiku for P3, P4
   - Goal: Route by phase complexity + cost (Draft: Haiku, Premium: Sonnet)
   - Impact: 30-40% cost reduction for Draft tier
   - Effort: 1 day
   - Success: Draft build cost < $2

**Timeline:** Sprint 1 = 2026-02-25 to 2026-03-07 (10 days)

**Testing:**
- 5 test builds per tier (Draft, Standard, Premium)
- Quality score comparison vs main branch
- Cost tracking per phase
- Manual audit (10% of atoms)

### Sprint 2: Next Phase (P6) & Validation (PLANNED)

**Focus:** Add description optimizer, quick validation layer

**Patches:**
5. **P6 Description Optimizer** (NEW PHASE)
   - Input: SKILL.md from P5
   - Process: Claude refines descriptions for clarity + brevity
   - Output: Optimized SKILL.md
   - Impact: Better skill marketplace positioning
   - Effort: 4-5 days
   - Cost: ~$1-2 additional per build

6. **Smoke Test (P5.5)** (EARLY VALIDATION)
   - Input: atoms_verified from P4
   - Process: Quick sanity checks (min atoms, structure, tokens)
   - Output: Validation report + recommendations
   - Impact: Catch issues before P5 (saves time/cost)
   - Effort: 2 days
   - Success: Catch 90% of potential failures

**Timeline:** Sprint 2 = 2026-03-08 to 2026-03-14 (1 week)

### Sprint 3: UI Features (PLANNED)

**Focus:** Build history, evaluation, templating

**Patches:**
7. **Eval Query UI**
   - Test skills against sample queries in browser
   - Input: Query + SKILL.md from completed build
   - Output: Claude response using skill context
   - Impact: User can validate quality before downloading
   - Effort: 3 days
   - UI: Modal with query input + response display

8. **Build History Dashboard**
   - Filter: by domain, status, date range, cost, quality
   - Sort: by date, quality, cost
   - Actions: Duplicate, compare, export CSV
   - Impact: Better project management
   - Effort: 2 days

9. **Script Bundler**
   - Allow users to attach Python/JS helper scripts to skill
   - Package scripts inside .zip alongside knowledge files
   - Impact: Skills more executable, less manual integration
   - Effort: 2 days

**Timeline:** Sprint 3 = 2026-03-15 to 2026-03-18 (4 days, overlaps with Sprint 4)

### Sprint 4: Analytics & Self-Learning (PLANNED)

**Focus:** Quality insights, continuous improvement

**Patches:**
10. **Quality Report 2.0**
    - Per-atom analysis (quality score, evidence strength, sources)
    - Phase breakdown (what went well, what needs improvement)
    - Recommendations (e.g., "Add more examples for clarity")
    - Impact: Help users understand quality drivers
    - Effort: 3 days

11. **Template Manager UI**
    - Create/edit templates in UI (instead of YAML only)
    - Clone, test, publish
    - Impact: Enable community templates
    - Effort: 3 days
    - Status: LOWER PRIORITY (may defer to Phase 3)

12. **Self-Improving Pipeline** (OPTIONAL)
    - Learn from user conflict resolutions (P3)
    - Adjust merge confidence thresholds
    - Track which phases improve quality
    - Impact: Better dedup accuracy over time
    - Effort: 4-5 days
    - Status: RESEARCH PHASE (may skip if time-boxed)

**Timeline:** Sprint 4 = 2026-03-19 to 2026-03-21 (3 days final push)

**Total v2 Duration:** 4 weeks (2026-02-25 to 2026-03-21)

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

| Version | Phase | Target Date | Status |
|---------|-------|-------------|--------|
| 2.12.1 | Phase 1 | ✅ Current | Shipping |
| 2.13.0 | Phase 2 (v2-upgrade) | 2026-03-21 | In progress |
| 3.0.0 | Phase 3 (Multi-user) | 2026-05-01 | Planned |
| 3.5.0 | Phase 4 (Ecosystem) | 2026-07-01 | Planned |

## Documentation Updates Required

**Before v2.13 Release:**
- [ ] Update this roadmap with Sprint outcomes
- [ ] Document P6 phase in pipeline docs
- [ ] Update API docs for Eval Query endpoint
- [ ] Add troubleshooting guide for common user errors
- [ ] Create skill packaging guide for end users

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
