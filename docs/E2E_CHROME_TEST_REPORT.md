# Real Google Chrome End-to-End Test Report

Status: **actually executed** — real Postgres, real running backend,
real running Vite dev server, and a **real, installed Google Chrome**
(not Playwright's bundled Chromium), driven by Playwright's test runner.
Every number below came from an actual `npx playwright test` invocation
in this session.

## REAL CHROME VERIFICATION

- **Browser**: Google Chrome
- **Chrome version**: `153.0.8010.48` (printed live by
  `browser.version()` in `01-smoke.spec.ts`, matches the installed
  binary's own `VersionInfo.ProductVersion`)
- **Executable**: `C:\Program Files\Google\Chrome\Application\chrome.exe`
  (confirmed present via `Test-Path` before writing any test)
- **Launch method**: `playwright.config.ts` → `use: { channel: 'chrome'
  }` / `projects: [{ name: 'chrome', use: { ...devices['Desktop
  Chrome'], channel: 'chrome' } }]` — Playwright's `channel: 'chrome'`
  resolves to the system-installed Chrome, not its own bundled
  Chromium/`chrome-headless-shell` build. Confirmed this is a real,
  meaningful distinction: Playwright's bundled `chrome-headless-shell`
  binary failed to spawn at all in this sandboxed environment (`spawn
  UNKNOWN`, reproduced identically from both Bash and PowerShell, with
  the OS sandbox disabled); the real Chrome binary launched
  successfully both standalone and through every test run in this
  report. `--no-sandbox` is passed via `launchOptions.args` because this
  environment's process model cannot create Chrome's own internal
  sandbox — documented as an environment limitation of this specific
  dev machine, not a general recommendation.
- **Frontend URL**: `http://localhost:5173` (Vite dev server)
- **Backend URL**: `http://127.0.0.1:8000` (real `uvicorn`, real
  Postgres via `docker-compose.test.yml`, port 5433)
- **Tests run**: 89
- **Result**: **89 passed, 0 failed** (two consecutive full runs, both
  clean — see §"Flaky test" below for the one instability found and
  fixed during development)

## 1. Test environment

- Node `v22.14.0`, npm `10.9.2`
- `@playwright/test` `1.63.0`
- Real Postgres: `docker-compose.test.yml`'s `test_db` service (port
  5433 — port 5432 was occupied by an unrelated project's container,
  same situation as the backend hardening pass)
- Real backend: `alembic upgrade head` + `uvicorn app.main:app` on 8000
- Real frontend: `npm run dev` (Vite) on 5173, proxying `/api/*` to 8000
  server-side (the browser itself never talks to port 8000 directly —
  this mattered, see §"Bugs found in the test suite itself")

## 2. Test architecture

`frontend/playwright.config.ts` (separate from `vitest.config.ts`,
which now explicitly excludes `tests/e2e/**` so the two suites never
collide). `frontend/tests/e2e/`:
- `fixtures.ts` — shared console/network-failure monitoring, attached to
  every test via a custom Playwright fixture.
- `api-bridge.ts`, `comparison-helpers.ts` — direct-API helpers used
  **only** to bridge the workflow steps that have no UI at all (see §3).
- 18 numbered spec files, `01-smoke.spec.ts` through
  `18-accessibility.spec.ts`, matching the requested structure.

Selectors throughout: `getByLabel`, `getByRole`, `getByText` — no
CSS-position-based selectors anywhere in the suite.

## 3. UI reality vs. the master prompt's assumed 13-step core workflow

Established during the earlier frontend hardening pass, unchanged: only
4 of 19 spec screens exist (Dashboard, Projects, Experiments,
Comparison). Of the master prompt's core workflow, only **Create
Project** and **Create Experiment** have real UI entry points. Per your
explicit direction, every other step is either driven through the real
Comparison page's genuinely-existing "advanced provenance JSON" fields
(the real centerpiece, §6-7) or bridged with a direct API call and
clearly labeled as such — never silently faked as a UI interaction that
didn't happen.

| Master prompt step | How it was actually tested |
|---|---|
| Create Project | Real UI (`02-projects.spec.ts`) |
| Create Experiment | Real UI (`03-experiments.spec.ts`) |
| Execute Experiment / Capture Provenance | No UI exists. API-bridged run creation (`04-runs.spec.ts`), consumed by the real Comparison UI |
| Create/Execute Reproduction | Same as above — REPROX's own model doesn't distinguish an "original run" from a "reproduction run" at creation time, only at comparison time |
| Compare / Detect Differences | Real UI, real Scenario A-G matrix (`06-comparison.spec.ts`) |
| Classify Reproducibility | Real UI, cross-checked against live API, never hard-coded (`07-reproducibility.spec.ts`) |
| Contributor analysis | No UI. Real API verified directly (`08-contributors.spec.ts`) |
| Provenance graph / Lineage | No UI. Comparison page's per-category sections + real `/lineage` API (`05-provenance.spec.ts`, `09-lineage.spec.ts`) |
| Investigation | No UI. Real API verified directly, including the "original run untouched" requirement (`10-investigation.spec.ts`) |
| Search | No UI. Real API verified directly (`11-search.spec.ts`) |
| Jobs | No dedicated UI. Dashboard's real active-jobs count + real API (`12-jobs.spec.ts`) |
| Generate/Download Report | No UI. Real API verified directly, including a real downloadable `.xlsx` (`13-reports.spec.ts`) |

## 4. Full user journey actually exercised

Project → Experiment → 2 Runs (API-bridged) → Compare (real UI, real
advanced-JSON provenance) → Reproducibility classification (real UI,
API-cross-checked) → Investigation plan + Report + Excel export (real
API, since no UI exists for any of the three) — end to end against real
Postgres, with the real classification decision table exercised, not
assumed.

## 5. API integration verification

Every one of the 23 real backend routes touched by at least one test in
this suite, either through the real UI or a direct API bridge call. No
mocked core engine anywhere — every provenance/fingerprint/comparison/
reproducibility/contributor result in this report came from the real
backend logic running against real Postgres.

## 6. Real bugs found and fixed this pass

### Bug: advanced provenance JSON textareas had zero accessible-name association

Found by `getByLabel` timing out (not by manual inspection) in an early
draft of `05-provenance.spec.ts`. `ComparisonPage.tsx`'s "Base/Compare
provenance JSON" `<label>`s had no `htmlFor`/`id` at all — not just a
weaker association than ideal (the earlier frontend hardening pass's
Name/Slug/etc. gap), but literally zero programmatic link, invisible to
both `getByLabel` and a real screen reader. Fixed with matching
`htmlFor`/`id` pairs. Regression test added:
`frontend/src/pages/ComparisonPage.test.tsx` (Vitest/RTL).

No other real application bugs were found in this pass — every other
initial test failure (11 of them across development) was a bug in the
test itself, root-caused and fixed rather than the assertion being
weakened. Documented individually below for the same transparency
`docs/BACKEND_TEST_REPORT.md` applied to its own findings.

## 7. Bugs found in the test suite itself (not the app) — full transparency

- **Wrong classification assumed for "zero provenance"**: initially
  hard-coded `INSUFFICIENT_EVIDENCE` for a comparison with no inline
  provenance on either side, from memory of the decision table's
  description. The real backend returns `NOT_COMPARABLE` (the
  `all_categories_not_comparable` short-circuit in
  `app/reproducibility/classifier.py` runs before the
  `no_outcome_evidence` rule). Read the actual classifier source,
  corrected both the test and its comment, and added a second scenario
  (setup evidence present, metrics missing) to genuinely exercise
  `INSUFFICIENT_EVIDENCE` — exactly the master prompt's own "validate
  actual backend behavior, don't hard-code" instruction, self-applied.
- **Wrong provenance dataclass field names**: `DatasetProvenance`/
  `ConfigurationProvenance`/`RandomnessProvenance` payloads initially
  used made-up field names (`content_hash`/`row_count` alone,
  `learning_rate` directly, `seed`/`is_deterministic`) instead of the
  real dataclass shapes in `app/provenance/*.py`. Fixed by reading the
  real dataclasses and building matching helper functions in
  `comparison-helpers.ts`.
- **Non-unique locators against a shared, persistent dev DB**: several
  early Projects/Experiments assertions searched for fixed display text
  ("CIFAR-10 ResNet50 Baseline", "Persistence Check") that becomes
  ambiguous once the suite has run more than once against the same
  real, never-reset Postgres instance. Fixed by scoping every assertion
  to a per-test-run unique slug/name.
- **Route pattern targeted the wrong origin**: `page.route()` calls
  aimed at `http://127.0.0.1:8000/**` never matched anything, because
  the browser only ever calls the frontend's own relative `/api/v1/*`
  path — Vite's dev-server proxy forwards it to the backend **server-
  side**, invisible to the browser and therefore to Playwright's route
  interception. Fixed by routing on `**/api/v1/**` instead.
- **Ambiguous substring match**: a "no search results" test's query
  string (`zzz-definitely-no-match-zzz`) happened to share the token
  "no" with this suite's own `repro-no-contrib` fixture names, producing
  a genuine (if tiny) nonzero TF-IDF cosine-similarity score — not a
  search-relevance bug, a coincidental token collision from this
  suite's own naming. Fixed with a token that shares no vocabulary with
  any real word.
- **Lint tooling false positive**: `oxlint`'s `react-hooks/rules-of-
  hooks` rule flagged Playwright fixture callbacks' `use` parameter as
  if it were React's `use()` hook (purely because of the name — `use`
  is just a parameter name Playwright's fixture API lets you choose
  freely). Renamed to `provideValue` in `fixtures.ts`; no rule disabled.
- **Vitest picking up Playwright specs**: `vitest.config.ts`'s default
  include glob matched `tests/e2e/**/*.spec.ts`, causing Vitest to try
  running Playwright tests with the wrong `test`/`expect` API (18 files,
  all failing). Fixed with an explicit `exclude`.

## 8. Flaky test found and fixed

One instability: `09-lineage.spec.ts`'s single test failed once in an
89-test run at 8 parallel workers, then passed reliably (3/3) when
re-run in isolation. Root cause: this suite drives one shared, stateful
backend process (real Postgres + a single `uvicorn` process, not one
instance per worker), and every run creation (`04-runs.spec.ts`'s API
bridge, used throughout) triggers a real `BackgroundTasks` callback into
Phase 17's Docker sandbox attempt — genuine resource contention under
high parallelism against a single dev-grade backend process, not a
product bug. Fixed by capping `workers: 4` in `playwright.config.ts`
(down from Playwright's CPU-count default of 8 on this machine), with
the reasoning documented inline. **Verified stable across two full
consecutive 89-test runs at 4 workers after the change** — no retries
used to paper over the flake; the actual concurrency was reduced.

## 9. Console / network validation

Every spec file uses the shared `consoleErrors`/`networkFailures`
fixture; `assertNoUnexpectedErrors()` is called explicitly wherever a
test isn't itself deliberately triggering an error response. No
uncaught exception, React error, or unexpected 4xx/5xx was found in any
passing test run.

## 10. Accessibility, security, responsive — results

- **Responsive**: all 8 requested viewports (320×800 through 1920×1080)
  × all 4 real pages = 32 checks, 0 horizontal overflow anywhere
  (`17-responsive.spec.ts`).
- **Accessibility**: full keyboard-only project creation flow works
  end-to-end (`18-accessibility.spec.ts`); every input across all 3
  forms has a real accessible name (this pass's own Bug fix, §6,
  closed the one remaining gap); the error-state retry button is
  keyboard-activatable.
- **Security**: XSS/HTML-injection payloads render as inert text; a
  malicious deep-linked query string triggers no reflected execution;
  no secret-shaped value in localStorage/sessionStorage/console/any
  backend response; a SQL-injection-shaped project name is stored and
  rendered safely with no data loss (`15-security.spec.ts`).

## 11. Final test results

- `npx playwright test` (real Chrome, 4 workers, full suite): **89
  passed, 0 failed, 0 skipped** — two consecutive clean runs.
- `npx vitest run` (component/unit tests, unrelated jsdom suite): **9
  passed, 0 failed**, after excluding the new Playwright specs from
  Vitest's own discovery.
- `npm run build`: clean, 0 TypeScript errors.
- `npm run lint`: clean, 0 warnings (after fixing the false-positive
  react-hooks rule trigger).
- Screenshots/videos/traces: configured (`only-on-failure`/`retain-on-
  failure`) — none retained, since the final two full runs had zero
  failures; artifacts from the debugging process were generated and
  inspected during development, then cleaned up along with
  `tests/e2e/test-results/`.

## 12. Remaining known limitations

- **15 of 19 spec screens still don't exist** — unchanged from the
  frontend hardening pass, and out of scope for this E2E pass by the
  same explicit agreement (test what's real, don't build the missing
  screens). Every one of those 15 workflow areas was verified at the
  API level instead, and every file says so explicitly in its own
  header comment.
- **No real job execution success ever observed**: creating a run does
  trigger a real Docker sandbox attempt (confirmed, not assumed — this
  is what caused §8's flake), but the `reprox-sklearn-runner:latest`
  image was never built in this environment, so every real execution
  attempt fails at the image-pull step. This suite doesn't test a
  genuinely successful `COMPLETED` job lifecycle for the same reason
  `docs/BACKEND_TEST_REPORT.md` already documents this gap.
- **No video/trace artifacts are attached to this report** — the final
  runs passed cleanly, so none were generated to attach; the
  configuration to capture them on failure is real and was exercised
  during development (multiple real screenshots/traces were inspected
  while debugging the issues in §6-7).
- **This dev Postgres is shared and persistent across the whole
  session** — every test that needs a "no other data" condition (e.g.
  empty search results) had to be written defensively around that,
  documented inline at each such test.
