# Phase 7: Advanced Features

## Context Links
- Source: `UPGRADE-PLAN-FINAL.md` Tasks 12, 13
- Sprint: 4 (Advanced)

## Overview
- **Priority**: P3
- **Status**: complete
- **Description**: Enhanced template library with pre-optimized descriptions, self-improving pipeline with feedback loop
- **Estimated effort**: 4-6 days

## Dependencies
- **Depends on**: Phase 6 (UI features must be complete, P6 optimization must work)
- **Blocks**: none (final phase)

## File Ownership

### Task 12: Enhanced Template Library
| File | Action |
|------|--------|
| `lib/db-schema.ts` | **MODIFY** (add template columns) |
| `app/templates/page.tsx` | **MODIFY** (rich UI) |
| `app/api/templates/route.ts` | **MODIFY** (serve new columns) |
| `pipeline/core/types.py` | **MODIFY** (add `template_optimized_description` field) |

### Task 13: Self-Improving Pipeline
| File | Action |
|------|--------|
| `lib/db-schema.ts` | **MODIFY** (add feedback table) |
| `lib/feedback.ts` | **CREATE** |
| `app/api/builds/[id]/feedback/route.ts` | **CREATE** |
| `components/build/feedback-widget.tsx` | **CREATE** |
| `pipeline/core/types.py` | **MODIFY** (add `domain_lessons` field) |
| `pipeline/phases/p5_build.py` | **MODIFY** (inject lessons into prompts) |
| `lib/build-runner.ts` | **MODIFY** (pass lessons as env) |

**Conflict note**: Both tasks modify `lib/db-schema.ts` and `pipeline/core/types.py`. Must be done sequentially or coordinated carefully.

## Implementation Steps

### Task 12: Enhanced Template Library (UPGRADE-PLAN lines 2326-2414)

**12A. Extend templates table** in `lib/db-schema.ts`:

```typescript
// Migration-safe column additions
const hasCol = db.prepare("PRAGMA table_info(templates)").all()
  .some((col: any) => col.name === "optimized_description");
if (!hasCol) {
  db.exec("ALTER TABLE templates ADD COLUMN optimized_description TEXT");
  db.exec("ALTER TABLE templates ADD COLUMN eval_queries TEXT");
  db.exec("ALTER TABLE templates ADD COLUMN taxonomy TEXT");
  db.exec("ALTER TABLE templates ADD COLUMN avg_quality REAL");
}
```

**12B. Seed enhanced templates**:
- Add pre-optimized description for FB Ads template (the example from UPGRADE-PLAN lines 2380-2387)
- Other templates get null (no pre-optimized description)

**12C. Enrich template page UI** in `app/templates/page.tsx`:
- Show avg_quality badge on template card
- Show "Pre-optimized description included" indicator
- Show usage_count

**12D. Wire template description to P6**:
- Add to BuildConfig: `template_optimized_description: str = ""`
- In build-runner.ts: if template has optimized_description, pass to pipeline config
- In P6: use template description as starting point instead of extracted description

### Task 13: Self-Improving Pipeline (UPGRADE-PLAN lines 2417-2585)

**13A. Add feedback table** to `lib/db-schema.ts`:

```sql
CREATE TABLE IF NOT EXISTS build_feedback (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  build_id    TEXT NOT NULL,
  domain      TEXT,
  rating      INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
  feedback    TEXT,
  issues      TEXT,
  created_at  TEXT DEFAULT (datetime('now')),
  FOREIGN KEY (build_id) REFERENCES builds(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_feedback_domain ON build_feedback(domain);
```

**13B. Create** `lib/feedback.ts`:
- `submitFeedback(buildId, domain, rating, feedback, issues)` -- INSERT
- `getDomainLessons(domain, limit=5)` -- SELECT recent feedback, format as prompt text

```typescript
export function getDomainLessons(domain: string, limit: number = 5): string {
  const rows = getDb().prepare(`
    SELECT rating, feedback, issues FROM build_feedback
    WHERE domain = ? AND feedback IS NOT NULL AND feedback != ''
    ORDER BY created_at DESC LIMIT ?
  `).all(domain, limit);
  // Format as: "LESSONS FROM PREVIOUS BUILDS (domain: X, avg rating: Y/5):\n..."
}
```

**13C. Create API** `app/api/builds/[id]/feedback/route.ts`:
- POST: validate rating 1-5, call submitFeedback
- Returns `{ ok: true }`

**13D. Create** `components/build/feedback-widget.tsx`:
- Star rating (1-5)
- Issue tags: "Missing topics", "Inaccurate information", "Description too vague", "Too few atoms", "Redundant content", "Wrong language"
- Optional text feedback
- Submit button
- Success state after submission

**13E. Inject lessons into P5 prompts**:
- Add to BuildConfig: `domain_lessons: str = ""`
- In build-runner.ts: query `getDomainLessons(config.domain)` and pass as env var
- In p5_build.py: if `config.domain_lessons`, append to P5_SKILL_USER prompt

## Validation

```bash
# TypeScript
npm run build

# Python
cd pipeline && python -m pytest tests/ -x

# Database migration
# Start app, check templates table has new columns
# Check build_feedback table exists

# Manual test
# 1. Complete a build
# 2. Submit feedback via widget
# 3. Start new build for same domain
# 4. Verify lessons injected into P5 prompt (check pipeline logs)
```

## TODO

### Task 12
- [ ] Add 4 columns to templates table (migration-safe)
- [ ] Seed FB Ads template with optimized description
- [ ] Enrich template page UI
- [ ] Add template_optimized_description to BuildConfig
- [ ] Wire template description through to P6

### Task 13
- [ ] Create build_feedback table
- [ ] Create lib/feedback.ts
- [ ] Create feedback API endpoint
- [ ] Create feedback-widget.tsx
- [ ] Add domain_lessons to BuildConfig
- [ ] Inject lessons in build-runner.ts
- [ ] Append lessons in p5_build.py prompts

### Final
- [ ] npm run build -- compiles
- [ ] pytest -- all pass
- [ ] Manual: feedback -> lessons -> P5 prompt chain works

## Success Criteria
- Templates show pre-optimized descriptions and quality stats
- Feedback widget collects 1-5 star ratings + issue tags
- Domain lessons appear in P5 prompts for repeat-domain builds
- All database migrations are safe (IF NOT EXISTS / column check)
- Backward compatible with existing data

## Risk Assessment
- **Medium**: build-runner.ts (951 LOC) is the largest file -- modifications need careful placement
- **Medium**: Passing domain_lessons through env vars has size limits -- consider temp file for large feedback
- **Low**: SQLite ALTER TABLE migrations are well-tested pattern
- **Low**: Feedback widget is isolated, no impact on core build flow

## Security Considerations
- Feedback text is user input -- store as-is but sanitize when displaying in UI
- Rating validation: CHECK constraint in DB + API validation
- No PII in feedback (build metadata only)
