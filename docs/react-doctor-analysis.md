## React Doctor Analysis — Skill Factory Web

- **Ngày chạy:** 2026-02-27
- **Tool:** react-doctor v0.0.29
- **Điểm tổng:** 87 / 100 (Great)
- **Tổng số issues:** 381 (14 errors + 367 warnings)
- **Framework:** Next.js | React 19.2.3 | TypeScript
- **Files scanned:** 196

---

### Phân loại Issues theo mức độ

#### 🔴 Critical (14 errors)

| # | Rule | File | Lines | Mô tả | Cách sửa đề xuất |
|---|------|------|-------|--------|-------------------|
| 1 | fetch-in-useEffect | `app/build/[id]/page.tsx` | 68, 104 | fetch() trong useEffect | Dùng react-query/SWR hoặc Server Component |
| 2 | fetch-in-useEffect | `components/layout/auth-gate.tsx` | 14 | fetch() trong useEffect | Dùng SWR hoặc Server Component |
| 3 | fetch-in-useEffect | `components/build/step-template.tsx` | 17 | fetch() trong useEffect | Dùng react-query |
| 4 | fetch-in-useEffect | `components/build/step-review.tsx` | 40 | fetch() trong useEffect | Dùng react-query |
| 5 | fetch-in-useEffect | `app/templates/page.tsx` | 11 | fetch() trong useEffect | Chuyển sang Server Component |
| 6 | fetch-in-useEffect | `app/settings/page.tsx` | 26 | fetch() trong useEffect | Dùng SWR |
| 7 | fetch-in-useEffect | `app/library/page.tsx` | 14 | fetch() trong useEffect | Chuyển sang Server Component |
| 8 | fetch-in-useEffect | `components/build/step-data-sources.tsx` | 44 | fetch() trong useEffect | Dùng react-query |
| 9 | fetch-in-useEffect | `components/build/skill-preview.tsx` | 23 | fetch() trong useEffect | Dùng react-query |
| 10 | fetch-in-useEffect | `components/build/quality-report.tsx` | 27 | fetch() trong useEffect | Dùng react-query |
| 11 | fetch-in-useEffect | `app/baselines/baseline-detail-panel.tsx` | 37 | fetch() trong useEffect | Dùng SWR |
| 12 | fetch-in-useEffect | `components/build/eval-trigger-panel.tsx` | 31 | fetch() trong useEffect | Dùng react-query |
| 13 | fetch-in-useEffect | `app/compare/page.tsx` | 26 | fetch() trong useEffect | Dùng SWR |

> **Note:** Tất cả 14 errors đều cùng rule: `fetch() inside useEffect`. Đây là pattern phổ biến nhưng react-doctor khuyến nghị dùng data fetching library hoặc Server Components.

---

#### 🟡 Warning — Hiệu năng + Code quality (82 warnings, không tính unused)

| # | Rule | Count | Files chính | Cách sửa |
|---|------|-------|-------------|----------|
| 1 | Large component (>300 lines) | 2 | `app/build/[id]/page.tsx` (313 lines), `build-wizard.tsx` | Tách sub-components |
| 2 | 3+ setState in single useEffect | 8 | `page.tsx`, `step-review`, `templates`, `settings`, `library`, `step-data-sources`, `skill-preview`, `baseline-detail-panel` | Dùng useReducer |
| 3 | Client-side redirect in useEffect | 4 | `app/build/[id]/page.tsx` (3), `app/compare/page.tsx` (1) | Dùng redirect() trong Server Component hoặc middleware |
| 4 | useEffect simulating event handler | 1 | `app/build/[id]/page.tsx:104` | Chuyển logic vào onClick/onChange |
| 5 | autoFocus attribute | 1 | `components/layout/auth-gate.tsx:73` | Bỏ autoFocus |
| 6 | Clickable element missing keyboard listener | 6 | `step-upload` (2), `smoke-test-detail` (1), `baselines/page` (1), `baseline-detail-panel` (2) | Thêm onKeyDown/onKeyUp |
| 7 | Static HTML element missing role | 6 | Same files as above | Thêm role="button" hoặc dùng `<button>` |
| 8 | Array index as key | 19 | `step-upload` (2), `step-data-sources` (1), `smoke-test-detail` (1), `skill-preview` (10), `baselines/page` (1), `baseline-detail-panel` (2), `log-viewer` (1), `eval-trigger-panel` (1) | Dùng stable ID |
| 9 | Form label not associated | 6 | `settings/page.tsx` (3), `baselines/page.tsx` (3) | Thêm htmlFor hoặc wrap label |
| 10 | Too many useState (7+) | 6 | `settings`, `skill-preview`, `baselines/page`, `feedback-widget`, `compare/page`, `build-wizard` | Dùng useReducer |
| 11 | Inline render function | 5 | `skill-preview.tsx` (5) | Extract named components |
| 12 | Default prop [] creates new ref | 1 | `phase-stepper.tsx:120` | Extract to module-level const |
| 13 | useSearchParams without Suspense | 1 | `app/compare/page.tsx:16` | Wrap trong `<Suspense>` |

---

#### 🟢 Info — Dead code + Unused (285 warnings)

| Rule | Count | Chi tiết |
|------|-------|----------|
| Unused files | 278 | ~250 là `.claude/`, `.opencode/`, `.venv/` (false positives). ~10 là UI components chưa dùng, ~10 là hooks/lib exports |
| Unused exports | 16 | `buttonVariants`, auth, db, build-queue, config-generator, badge, alert-dialog, tabs, notifications |
| Unused types | 7 | `PhaseInfo` (types/build.ts), types in config-generator, build-runner, use-build-stream, baseline-registry, use-wizard-state |

---

### Thống kê theo thư mục

| Thư mục | Errors | Warnings (code) | Warnings (unused) | Tổng |
|---------|--------|-----------------|-------------------|------|
| `app/build/` | 2 | 8 | 0 | 10 |
| `app/baselines/` | 1 | 8 | 0 | 9 |
| `app/` (other pages) | 4 | 8 | 0 | 12 |
| `components/build/` | 5 | 18 | 1 | 24 |
| `components/layout/` | 1 | 1 | 0 | 2 |
| `components/ui/` | 0 | 2 | 9 | 11 |
| `hooks/` | 0 | 0 | 3 | 3 |
| `lib/` | 0 | 0 | 8 | 8 |
| `types/` | 0 | 0 | 1 | 1 |
| `.claude/`, `.opencode/` | 0 | 0 | ~250 | ~250 |
| **Tổng** | **14** | **82** | **~285** | **~381** |

---

### Top 5 Issues nên fix ngay

1. **`app/build/[id]/page.tsx`** — 313 lines, 2 fetch-in-useEffect, 3 client-side redirects, 3+ setState. File "nóng" nhất. Cần refactor: tách sub-components, dùng useReducer, chuyển redirects sang middleware.

2. **`components/build/skill-preview.tsx`** — 5 inline render functions + 10 array-index keys + fetch-in-useEffect + nhiều useState. Cần extract named components và dùng stable keys.

3. **`app/compare/page.tsx`** — useSearchParams() không có Suspense boundary → toàn page bail out khỏi SSR. Fix: wrap `<Suspense>`.

4. **Accessibility: 12 issues** (6 missing keyboard + 6 missing role) across `step-upload`, `smoke-test-detail`, `baselines/page`, `baseline-detail-panel`. Fix: thêm role="button" + onKeyDown cho các clickable div.

5. **`app/settings/page.tsx`** — 7 useState + 3 label không liên kết control + fetch-in-useEffect. Fix: useReducer + htmlFor.

---

### Issues KHÔNG nên fix (false positives / không áp dụng)

| Issue | Lý do bỏ qua |
|-------|--------------|
| **278 unused files** (~250 trong `.claude/`, `.opencode/`, `.venv/`) | Tool config files, hooks, skills scripts — không phải React source code. React Doctor không exclude được dotfiles. |
| **Unused UI components** (`avatar`, `card`, `dialog`, `dropdown-menu`, `scroll-area`, `select`, `separator`, `sheet`, `sonner`, `tooltip`) | shadcn/ui components được install sẵn cho future use. Bỏ đi dễ cần lại. |
| **`hooks/use-auth.ts` unused** | Có thể đang develop hoặc dùng trong page chưa scan. Cần verify thủ công. |
| **`feedback-widget.tsx` unused** | Có thể được lazy-load hoặc conditionally rendered. Cần verify. |
| **fetch-in-useEffect cho build pages** | Nhiều page cần real-time polling (build status, logs) — không phù hợp Server Component. SWR/react-query là đúng hướng nhưng không phải lỗi logic. |
| **autoFocus trên auth-gate** | Login form autoFocus input là UX pattern phổ biến và chấp nhận được cho auth flows. |
