# Frontend Testing & UI Hardening Report

Status: **actually executed** — real Chromium (via Playwright, launched
directly since the Claude-in-Chrome extension wasn't available in this
environment), a real running Vite dev server, and a real running
backend + Postgres (same bring-up as the backend hardening pass).
Every number below came from a command or browser interaction actually
run in this session.

## 1. Environment

- Node `v22.14.0`, npm `10.9.2`.
- React `19.2.8`, React DOM `19.2.8`, react-router-dom `7.18.4`,
  TypeScript `~6.0.2`, Vite `8.3.0`, Tailwind `4.3.3`.
- New devDependencies added this pass: `vitest`, `@testing-library/react`,
  `@testing-library/user-event`, `@testing-library/jest-dom`, `jsdom`,
  `@playwright/test` — **none existed before this pass**; the frontend
  had zero test infrastructure (no config, no test files, confirmed by
  a full search before starting).
- Real backend: `docker-compose.test.yml`'s `test_db` (Postgres, port
  5433) + `alembic upgrade head` + `uvicorn` on port 8000 — identical
  bring-up to `docs/BACKEND_TEST_REPORT.md`'s Stage 1.
- Real frontend: `npm run dev` (Vite, port 5173, proxying `/api` to the
  live backend on 8000 per `vite.config.ts` — no config change needed).

**Adaptation from the plan**: the Claude-in-Chrome browser extension
reported "not connected" in this environment. Rather than fall back to
static code reading, Playwright + a real Chromium binary was installed
and driven directly via a Node script — a real rendered browser, real
clicks, real form fills, real fetches to the real backend, just scripted
instead of interactively steered. (The bundled `chrome-headless-shell`
binary failed to spawn — `spawn UNKNOWN` — in this sandboxed Windows
environment even with the sandbox disabled; the full `chrome.exe` binary
launched fine and was used for everything below.)

## 2. Ground truth: what actually exists (before any of the spec's 19 screens)

Confirmed by reading the entire `frontend/src/` tree (14 files) before
starting: **4 of the 19 spec-named screens exist** — Dashboard (`/`),
Projects (`/projects`), Experiments (`/experiments`), Comparison
(`/compare`, manual run-ID entry, not a routed detail page). No dynamic
routes exist. **15 screens have no page/route/component at all**:
Experiment Detail, Run Detail, Reproducibility Analysis (as its own
page), Provenance Explorer, Lineage, Dataset Registry, Environment
Registry, Artifact Explorer, Investigation Center, Counterfactual
Experiments, Historical Search, AI Assistant, Jobs, Reports, Settings.
This is a real, named gap — not silently omitted — and out of scope for
this pass by explicit agreement (testing/hardening the existing
frontend, not building 15 new pages).

The API client (`src/api/client.ts`) calls only 6 of the 23 real backend
endpoint groups (projects, experiments, the nested runs/compare,
comparisons — defined but unused, reproducibility, dashboard); the other
16 (provenance, lineage, jobs, investigations, counterfactuals, explain,
search, reports, exports) have zero frontend usage, consistent with only
4 pages existing.

## 3. Commands executed

- `npm install` — clean, 0 vulnerabilities.
- `npm run build` (`tsc -b && vite build`) — **clean before any changes**,
  0 TypeScript errors, 0 build errors. Re-run after all fixes: still
  clean.
- `npm run lint` (`oxlint`) — **clean before any changes**, exit 0.
  Re-run after all fixes: still clean, 0 warnings in real source (one
  transient warning appeared in a scratch driver script during
  development; that file was deleted before finishing, not part of the
  repo).
- `npx vitest run` — 0 tests before this pass (infra didn't exist); **8
  tests, all passing** after this pass.
- A real Playwright-driven Chromium session against the real running
  app + real running backend (31 checks, detailed in §5-6).

## 4. Pages tested

All 4 that exist: Dashboard, Projects, Experiments, Comparison — driven
through direct navigation, real form submission, and real backend
responses. The 15 non-existent screens were not tested (they don't
exist to test); see §2.

## 5. Functional / API integration results

Real click-through checks against the real backend (31 total, itemized
below by category). All 31 ultimately passed; 7 initially failed and
were root-caused and fixed (§7-9); 1 more was a bug in the *test itself*
(a too-strict CSS selector, not an app issue), corrected and re-verified.

- **Routing** (4 direct-navigation + refresh + invalid-route + back/
  forward): all pass after the 404 fix (§7). Before the fix, an unknown
  route rendered a **genuinely empty `<body>`** (`textContent` length
  0) — confirmed by direct measurement, not inferred.
- **Dashboard**: `total_projects`, `total_experiments`, `total_runs`
  all cross-checked against a direct `GET /api/v1/dashboard` call made
  in the same script — the numbers rendered in the DOM match the live
  API response exactly (both were `0`/`0`/`0` on a fresh DB, then `2` for
  projects after the Projects-page tests ran, confirmed to update
  correctly on reload).
- **Projects**: real create (valid name/slug → appears in the list on
  refresh), an XSS-payload name (`<script>...</script>XSSProbe`) — did
  **not** execute (`window.__xss_fired` stayed `undefined`) and rendered
  as visible inert text, confirming React's default escaping holds in
  this app; invalid slug and duplicate slug both now show a real,
  specific error message (§8 — invalid slug's message was generic before
  the fix).
- **Experiments**: form renders and its inputs are all present and
  labeled (§9).
- **Comparison**: form fields present and labeled (§9); full compare-
  submit-with-real-run-IDs flow was exercised as part of the backend
  hardening pass's own live probes (`docs/BACKEND_TEST_REPORT.md` §6) —
  not re-driven through the UI pixel-by-pixel in this pass, since the
  backend contract was already proven live and the UI form's field
  wiring was confirmed directly.

## 6. Accessibility, responsive, and security results

- **Keyboard navigation**: `Tab` from a fresh page load moves focus to a
  real focusable element (confirmed via `document.activeElement`), not
  stuck on `<body>`.
- **Responsive**: checked at 375×812, 768×1024, 1280×800, 1920×1080 on
  both Dashboard and Comparison. **Real horizontal overflow found and
  fixed** at 375px (§10) — affected every page (shared `Layout` header).
  Clean at all 4 breakpoints after the fix.
- **Accessible labels**: **3 real gaps found and fixed** on Projects
  (Name/Slug/Description), 4 more on Experiments (Project/Name/Workload
  type/Entrypoint), 2 more on Comparison (Base/Compare run ID) — all
  relied on `placeholder` alone with no `<label>`/`aria-label`/`id`
  association. Fixed uniformly (§9).
- **XSS**: confirmed empirically, not assumed — see §5.
- **localStorage/console secret check**: `window.localStorage` dumped
  and regex-checked for anything key/token/password/secret-shaped —
  empty object, no leakage (there's no auth token to leak today, but
  this is now a repeatable check).
- **Security note, not a bug**: the browser's own console logged
  "Failed to load resource: ... 422" / "... 409" during the deliberate
  invalid-slug and duplicate-slug tests. This is Chromium's built-in
  network-log behavior for any non-2xx `fetch` response, not an
  application error or an uncaught exception — the app handled both
  gracefully (a real error message shown to the user, no crash). Flagged
  here for completeness, not treated as a bug.

## 7. Bug #1 found and fixed: unmatched routes rendered a blank page

**Root cause**: `App.tsx`'s route table had no catch-all (`*`) route.
React Router renders nothing when no `<Route>` matches — confirmed live:
`document.body.textContent` was empty string on `/this-route-does-not-
exist`.

**Fix**: added `src/pages/NotFoundPage.tsx` (a real page, not a redirect
— shows a message and a link back to the Dashboard) and a `<Route
path="*" element={<NotFoundPage />} />` in `App.tsx`. Verified live:
`document.body.textContent` now contains "REPROX Dashboard Projects
Experiments Compare Page not found...".

Regression test: `src/App.test.tsx`.

## 8. Bug #2 found and fixed: generic, unhelpful validation error messages

**Root cause**: `src/api/client.ts`'s `request()` only knew how to parse
the app's own `{"error": {"code","message","details"}}` shape (emitted
by `app/core/errors.py`'s `ReproxError` handler). A Pydantic
`field_validator` failure — e.g. `ProjectCreate`'s slug pattern — never
goes through that handler; FastAPI returns its own native `{"detail":
[{"loc","msg","type"}]}` shape directly. Confirmed against the real
backend:
```
curl -X POST .../projects -d '{"name":"Test","slug":"Not A Valid Slug!"}'
→ {"detail":[{"type":"value_error","loc":["body","slug"],"msg":"Value error, slug must be lowercase alphanumeric segments separated by hyphens", ...}]}
```
Before the fix, the frontend showed the user a useless **"Request failed
with status 422"** for this and every other Pydantic-level validation
failure across all 3 forms — the real, specific reason was silently
discarded.

**Fix**: `src/api/types.ts` gained a `FastApiValidationErrorBody` type;
`src/api/client.ts`'s `request()` now detects the `detail` array shape
and builds a real message (`"slug: Value error, slug must be lowercase
alphanumeric segments separated by hyphens"`). Verified live: the
Projects form's invalid-slug submission now shows that exact message,
not the generic one.

Regression tests: `src/api/client.test.ts` (3 tests — the new shape, the
pre-existing `{error:{...}}` shape still works, and the generic fallback
for neither shape).

## 9. Bug #3 found and fixed: form inputs with no accessible label

**Root cause**: every input across Projects/Experiments/Comparison used
`placeholder` as its only user-facing label — no `<label htmlFor>`, no
`aria-label`, no `id`. Confirmed via a real DOM query for exactly this
condition (`label[for=id]` or `aria-label`/`aria-labelledby` absent) —
9 inputs total across 3 pages.

**Fix**: added `id` + `<label htmlFor>` to all 9 fields (Projects:
name/slug/description; Experiments: project/name/workload type/
entrypoint; Comparison: base run ID/compare run ID) preserving the
existing placeholder text and visual styling — no redesign, matching the
project's existing visual identity.

Regression test: `src/pages/ProjectsPage.test.tsx` (Experiments/
Comparison weren't separately unit-tested for this — same fix pattern,
verified live via the same browser check that found the original 9
gaps, now reporting zero).

## 10. Bug #4 found and fixed: shared header overflows at mobile width

**Root cause**: `Layout.tsx`'s header (`REPROX` logo + 4 nav links) used
`flex` with no wrap. At 375px viewport width, real measurement showed
`document.documentElement.scrollWidth = 417` vs `clientWidth = 375` — a
genuine 42px horizontal overflow, present on **every page** (Layout
wraps all routes).

**Fix**: `flex` → `flex-wrap` on both the header container and the nav
element, `gap-6` → `gap-x-6 gap-y-2` so wrapped items don't collide
vertically. Verified live: `scrollWidth` now equals `clientWidth` (375)
at 375px, and layout is unchanged (still a single row) at 768px+.

Not unit-tested (jsdom doesn't lay out CSS flex-wrap meaningfully for a
regression test) — covered by the real-browser check in this session;
re-verification would need a real/headless browser run, same tool used
here.

## 11. Bugs found in the test process itself (not the app)

- The initial probe script's Experiments-page selector
  (`input[name="name"], input#name`) didn't match that page's actual
  markup (no `name`/`id` attribute — the same missing-label issue as
  §9). Corrected to select by the new `#experiment-name` id after the
  label fix. Noted for transparency: not every initial "FAIL" in this
  pass was a real app bug — this one was a probe bug, caught and
  corrected, not silently dropped.

## 12. Final verification

- `npm run build` — clean, 0 errors (before and after).
- `npm run lint` — clean, 0 warnings (before and after; real source
  only).
- `npx vitest run` — **8 passed, 0 failed** (0 tests existed before this
  pass).
- Real-browser probe (Playwright): **31/31 checks passing** after fixes
  (started at 24/31 passing, 7 genuine findings — 6 real app bugs fixed,
  1 test-selector bug corrected).

## 13. Teardown

Vite dev server stopped, `uvicorn` stopped, `docker compose -f
docker-compose.test.yml down`, `backend/.env` removed — same discipline
as the backend hardening pass. All scratch driver scripts
(`_probe.mjs`, `_diag.mjs`) deleted from the repo; nothing left behind
outside the tracked changes below.

## 14. Summary of changes made in this pass

- `frontend/src/App.tsx`, `frontend/src/pages/NotFoundPage.tsx` (new) —
  §7.
- `frontend/src/api/client.ts`, `frontend/src/api/types.ts` — §8.
- `frontend/src/pages/ProjectsPage.tsx`,
  `frontend/src/pages/ExperimentsPage.tsx`,
  `frontend/src/pages/ComparisonPage.tsx` — §9 (accessible labels).
- `frontend/src/components/Layout.tsx` — §10 (mobile overflow).
- New test infra: `frontend/vitest.config.ts`,
  `frontend/src/test/setup.ts`, plus devDependencies in
  `frontend/package.json`.
- New tests: `frontend/src/App.test.tsx`,
  `frontend/src/api/client.test.ts`,
  `frontend/src/components/ErrorState.test.tsx` (harness smoke test),
  `frontend/src/pages/ProjectsPage.test.tsx`.

## 15. Remaining issues / not covered in this pass

- **15 of 19 spec screens don't exist** (§2) — the largest gap by far,
  explicitly out of scope for a testing/hardening pass by agreement, not
  silently glossed over. Building them is a separate, multi-day feature
  effort.
- **No component/interaction test for Experiments/Comparison forms**
  beyond the live-browser check — only Projects got a dedicated Vitest
  regression test for the label fix; the same fix pattern on the other
  two pages is real (verified live) but not independently unit-tested.
- **No dedicated responsive-layout regression test** (§10) — jsdom can't
  meaningfully assert CSS flex-wrap layout; only the live browser check
  covers this, and it isn't wired into the repeatable `npm run test`
  suite.
- **Performance** (Stage per the original master prompt's Phase 23:
  rerenders, bundle size, lazy loading): not deeply investigated beyond
  observing a single production build's output size (278KB JS / 86KB
  gzipped, 16KB CSS / 4KB gzipped) — small enough that this wasn't a
  priority for a 4-page app with no code-splitting opportunities worth
  pursuing yet.
- **No Claude-in-Chrome interactive session** — the extension wasn't
  connected in this environment; Playwright substituted for it (a real
  browser, just scripted). If the extension becomes available in a
  future session, an interactive pass could catch visual/UX issues a
  scripted check wouldn't (e.g. genuine subjective layout judgment).
