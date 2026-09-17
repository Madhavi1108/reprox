# Backend Testing, Validation & Hardening Report

Status: **actually executed** — real Postgres, a real running `uvicorn`
process, real HTTP calls, real SQL query counting. Every number below
came from a command run in this session; nothing here is inferred from
reading code alone. Scope was agreed as **depth over breadth**: fewer
areas, but genuinely run and verified rather than shallow coverage of
every category in the original request.

## 1. Architecture discovered

REPROX: FastAPI (Python 3.12) backend + React/Vite frontend, SQLAlchemy
2.0 ORM over Postgres, Alembic migrations, Docker-based sandboxed
experiment execution. Full component map: `docs/PHASE_TRACKER.md` (32
build phases), `docs/API.md`, `docs/MVP.md`. 23 real HTTP routes across
15 routers (`app/api/v1/routers/`), enumerated and verified against the
app's own live OpenAPI schema during this pass (see §3).

## 2. Test infrastructure discovered

- `backend/tests/unit/` — mocked-DB/pure-function tests (the bulk of the
  suite).
- `backend/tests/e2e/` — Phase 31's real HTTP flows against an in-memory
  SQLite substitute (`app.dependency_overrides[get_db]`).
- `backend/tests/integration/` — empty until this pass (no reachable
  Postgres had ever existed in this dev environment before now).
- Test command: `.venv/Scripts/python.exe -m pytest tests/ -q`, from
  `backend/`.

## 3. Environment validation & live bring-up (actually executed)

- `docker --version` → 29.7.2; `docker compose version` → v5.5.1 — both
  present.
- `docker compose up -d db` (the repo's dev compose file) **failed**:
  port 5432 was already bound by an unrelated project's Postgres
  container (`insightforge-postgres`) running on this host. Did not
  touch that container. Used the repo's existing, purpose-built
  `docker-compose.test.yml` (`test_db` service, port 5433, ephemeral
  `tmpfs` storage) instead — no port conflict, no changes to the dev
  compose file.
- `docker compose -f docker-compose.test.yml up -d test_db` → started,
  reached `healthy` on the first health check.
- Wrote `backend/.env` (git-ignored, not committed) pointing
  `DATABASE_URL` at the real `reprox_test` database on port 5433.
- `alembic upgrade head` → **ran cleanly, for the first time ever in this
  repo's history** against a real Postgres: `c6dd8a238406` (initial
  schema) → `f0645ccda9ee` (Phase 30 indexes). Verified via `psql \dt`
  (22 model tables + `alembic_version`) and `psql \di` (47 indexes,
  including all 7 of Phase 30's new FK indexes, confirmed present by
  name).
- Started the real app: `uvicorn app.main:app --host 127.0.0.1 --port
  8000`, against the real Postgres. `GET /health` → `200 {"status":
  "ok"}`. `GET /health/db` → `200 {"status":"ok"}` (a real `SELECT 1`
  round-trip to real Postgres, not a mock). `GET /openapi.json` → `200`,
  23 paths listed.
- Installed versions actually running: `fastapi 0.141.1`, `starlette
  1.6.0`, `sqlalchemy 2.0.53`, `pydantic 2.13.5`, `python 3.12.10` (the
  project only pins `fastapi>=0.115` — a much newer version resolved;
  this turned out to matter, see §5).

## 4. Baseline test run (before any fixes)

`pytest tests/ -q` with `DATABASE_URL` pointed at the real Postgres:
**307 passed, 1 failed** — `test_api_app_wiring.py::
test_all_spec_endpoints_are_registered`, the same failure every phase
doc since Phase 19 restated without re-diagnosing.

## 5. Bug #1 found and fixed: route-wiring test broken by FastAPI version drift

**Root cause, actually diagnosed, not assumed**: the test built its
"actual routes" set by walking `app.routes` and filtering for objects
with a `.methods` attribute. As of the installed `fastapi 0.141.1` /
`starlette 1.6.0`, `app.include_router()` no longer flattens a
sub-router's routes into `app.routes` eagerly — it stores an opaque,
lazily-expanded `_IncludedRouter` wrapper instead. That wrapper has no
`.methods` attribute, so the filter silently dropped all 23 routes from
every included router, leaving only the 6 directly-declared ones
(`/health`, `/health/db`, `/docs`, `/docs/oauth2-redirect`, `/redoc`,
`/openapi.json`). Confirmed directly: `python -c "from app.main import
app; print(len(app.routes))"` → `7` objects, one of which prints as
`_IncludedRouter(...)`.

**This was a test bug, not an application bug** — confirmed by the live
server itself: `GET /api/v1/projects` → real `200`, and `GET
/openapi.json` lists all 23 paths correctly (FastAPI's OpenAPI generator
walks the router tree correctly; only the test's naive `app.routes`
introspection was broken by the internal representation change).

**Fix**: `tests/unit/test_api_app_wiring.py` — rewrote
`test_all_spec_endpoints_are_registered` to derive the actual-routes set
from `app.openapi()["paths"]` (the same document served at
`/openapi.json`, a stable public contract) instead of walking internal
`app.routes` objects. Verified: `pytest tests/unit/test_api_app_wiring.py
-q` → 6/6 passed (was 5/6).

This is, unintentionally, exactly the kind of failure REPROX itself is
built to detect and explain: an unpinned dependency (`fastapi>=0.115`)
drifted to a version with different internal behavior, and a test that
depended on that internal behavior broke as a result — dependency drift
causing a false negative.

## 6. Live HTTP edge-case testing (Stage 3)

A driver script (`httpx` against the real running server, not
`TestClient`) exercised all 23 routes: valid requests, missing required
fields, wrong types, malformed JSON, invalid/malformed UUIDs, nonexistent
resources, pagination boundary values (`limit=0`, `limit=101`,
`limit=-5`, `offset=-1`, non-numeric), duplicate-slug conflicts, path-
traversal-shaped path segments, SQL-injection-shaped string values, and
a 5-way concurrent create against the same unique slug.

**49 checks executed, 49 passed** (after the fix in §7). Full command
output captured in this session. Notably:
- The concurrent-duplicate-slug race (5 simultaneous `POST /projects`
  with an identical slug) correctly resolved to exactly **one** `201`
  and four `409`s, backed by the real Postgres `UNIQUE` constraint on
  `projects.slug` — this is real concurrent-transaction behavior no
  mock/SQLite test in this repo could have exercised before now.
- SQL-injection-shaped strings (`'; DROP TABLE projects; --`, `' OR
  '1'='1`) in both a request body field and a query parameter were
  handled safely (parameterized ORM queries) — verified by observing the
  actual response and confirming the `projects` table still exists
  afterward, not by code inspection alone.
- Path-traversal-shaped path segments (`..%2F..%2F..%2Fetc%2Fpasswd` in
  a UUID path parameter) correctly hit FastAPI's UUID-type path
  validation and returned `404`/`422`, never reaching any filesystem
  code.

## 7. Bug #2 found and fixed: unbounded request-body fields

**Found live**: `POST /api/v1/projects` with a 20MB `description` field
returned `201` and persisted the full 20MB string — unlike `name`/
`slug`/`entrypoint_script` (all explicitly `max_length`-bounded in their
Pydantic schemas), `ProjectCreate.description` and
`ExperimentCreate.description` had no length bound at all. This is a
real input-validation gap (a DoS-shaped vector: unbounded storage/memory
per request) that's inconsistent with every other string field on the
same schemas.

**Fix**: `app/schemas/project.py` and `app/schemas/experiment.py` —
added `max_length=5000` to both `description` fields (no DB migration
needed; the underlying column is `Text`, already unbounded at the SQL
level, so this only tightens the API-layer contract). Verified live,
before and after restarting the server with the fix:
- Before: `POST /projects` with a 20MB description → `201`.
- After: identical request → `422`, `"String should have at most 5000
  characters"`; a normal-length description still → `201`.

Regression tests added: `test_oversized_project_description_is_
rejected_by_schema_validation` and `test_oversized_experiment_
description_is_rejected_by_schema_validation` in
`tests/unit/test_api_app_wiring.py`.

## 8. Bug #3 found and fixed: a real N+1 that Phase 30's own regression test couldn't catch

**Found live, via real SQL-statement counting against real Postgres**
(`sqlalchemy.event.listens_for(engine, "before_cursor_execute")` — not a
mock): with 11 real `ExperimentComparison` rows in the database,
`app.export.excel._reports_for_comparisons()` — the function Phase 30
specifically fixed to be O(1) — issued **15** real SQL statements, not
the fixed 4 its own mocked regression test asserts.

**Root cause**: `generate_report()` (called once per comparison inside
that function) reads `comparison.differences` — a lazily-loaded
SQLAlchemy relationship (`ExperimentComparison.differences`, no `lazy=`
override) — which issues its own `SELECT` on first access, once per
comparison object. Phase 30's bulk-fetch of comparisons never eager-
loaded that relationship, so the "fixed 4 queries" claim was only true
for the explicit `.query()` calls the function itself makes — the
implicit per-row relationship lazy-load was invisible to it.

**Why Phase 30's own test suite didn't catch this**: its
`_CountingSession`/`_CountingQuery` test double (`tests/unit/
test_export_query_count.py`) counts `db.query()` *calls*, and its
`_comparison()` fixtures are `MagicMock` objects — `.differences` on a
`MagicMock` is just an auto-created mock attribute, never a real
`InstrumentedAttribute` that could trigger a lazy-load query. A mock
that stands in for the DB session structurally cannot see relationship-
lazy-loading behavior; only a real engine can. This is the single
clearest justification for this whole hardening pass: it found a real
bug that 288 passing mocked tests had been silently missing since Phase
30.

**Fix**: `app/export/excel.py` — added
`.options(selectinload(ExperimentComparison.differences))` to the bulk
comparison fetch, folding the N per-comparison lazy-loads into one
additional bulk query. Verified live, before/after, against real
Postgres with 11 real comparisons: **15 → 5** real SQL statements, `len
(reports)` unchanged (11).

Regression tests added:
- `tests/unit/test_export_query_count.py` — updated docstring to record
  this exact limitation of the mock, added a no-op `.options()` to
  `_CountingQuery` (needed for the fixed code to run against the fake at
  all); its `db.query()`-call-count assertion (4) is unchanged and still
  correct for what it measures.
- `tests/integration/test_reports_query_count_real_db.py` (new) — the
  first test in this repo's history to run against a real, reachable
  Postgres. Creates real `Experiment`/`ExperimentRun`/
  `ExperimentComparison`/`Difference` rows, counts real SQL statements
  via a real `event.listens_for` hook, and asserts the count doesn't
  change when 4 more comparisons are added. Skips gracefully (via a
  fast, 3-second-timeout connectivity probe) when no Postgres is
  reachable, so it won't break a future session without live infra.
  Cleans up every row it creates.

## 9. Engine-level gap check (Stage 4, targeted)

Checked the one item flagged as worth verifying: `ComparisonStatus.
PARTIALLY_MATCHING` is referenced in an old Phase 11 docstring as
"deliberately left unused." Grep confirmed it's genuinely wired and used
by Phase 13's `metrics.py` (tolerance-matched-but-not-exact metrics) and
covered by `test_compare_metrics.py`/`test_reproducibility_classifier.py`
— the docstring predates Phase 13 and is stale wording, not a live bug.
Additionally drove this path live end-to-end (real compare request with
metrics differing beyond default `0.0` tolerance) and confirmed the
documented default-tolerance behavior (`metrics_status: DIFFERENT`,
`classification: NOT_REPRODUCIBLE`) holds against real Postgres exactly
as designed — no per-metric tolerance override exists in the current API
surface, consistent with `docs/METRIC_TOLERANCE.md`.

## 10. Security probes (Stage 5, live)

Against the real running server: SQL-injection-shaped strings (body
field + query param), path-traversal-shaped path segments, oversized
JSON body (20MB, §7), malformed JSON, malformed/non-numeric query
params. All handled safely — no `500`, no stack trace in any response,
no secret in any response or in the server's stdout/stderr log
(`grep -i "password"` against the full session log: zero matches).
FastAPI's default (non-debug) error handling was confirmed live, not
assumed from reading `main.py`.

## 11. Real performance observations (Stage 6)

Measured against the live server + real Postgres (5 requests each,
min/max/avg):
- `GET /health`: 2.5–8.8ms (avg 4.0ms) — no DB touch.
- `GET /health/db`: 6.0–8.3ms (avg 6.9ms) — real `SELECT 1` round-trip.
- `POST /projects`: 14.6–15.9ms (avg 15.2ms) — real insert + commit +
  refresh.
- `GET /exports/excel` (8 experiments, ~11 comparisons persisted):
  267–359ms (avg 324ms) before the §8 fix; not re-measured after, since
  the fix changes query *count* (15→5), not wall-clock-dominant work at
  this small a fixture size — the real value of the fix is that it no
  longer scales with data volume, verified via the fixed query count,
  not via a wall-clock delta too small to be a meaningful signal at N=11.

These are real numbers from this specific run on this specific machine —
not a benchmark claim about production hardware, and not the exhaustive
load/scale testing `docs/EVALUATION_PLAN.md` already documents as out of
scope (would need sustained load and a production-sized dataset, neither
attempted here).

## 12. Final verification

`pytest tests/ -q` from a clean invocation, after all fixes: **311
passed, 0 failed** (300 unit + 10 e2e + 1 new real-Postgres integration
test). Breakdown by directory, each run in isolation and confirmed:
- `tests/unit/`: 300 passed
- `tests/e2e/`: 10 passed
- `tests/integration/`: 1 passed (was 0 tests — directory was empty
  before this pass)

No coverage tool was configured in this repo (`pyproject.toml` has no
`pytest-cov`/coverage config) — no coverage percentage is reported here,
per the instruction not to fabricate one.

## 13. Teardown

Per agreed scope: `uvicorn` stopped, `docker compose -f
docker-compose.test.yml down` run for the `test_db` container,
`backend/.env` removed. The repo working tree and host environment are
restored to their pre-session state except for the tracked code/test
changes listed below.

## 14. Summary of changes made in this pass

- `backend/tests/unit/test_api_app_wiring.py` — fixed the route-wiring
  test (§5); added 2 regression tests for §7.
- `backend/app/schemas/project.py`, `backend/app/schemas/experiment.py`
  — bounded `description` fields (§7).
- `backend/app/export/excel.py` — `selectinload` fix for the real N+1
  (§8).
- `backend/tests/unit/test_export_query_count.py` — documented the
  mock's blind spot, added `.options()` passthrough (§8).
- `backend/tests/integration/test_reports_query_count_real_db.py` (new)
  — real-Postgres regression test for §8, the first test of its kind in
  this repo.

Nothing else in the ~300-test existing suite required a fix — every
previously-passing test remained correct under real Postgres, real HTTP,
and real concurrency.

## 15. Remaining limitations / not covered in this pass

Consistent with the "depth over breadth" scope agreed at the start:

- **Not covered**: the master prompt's full combinatorial edge-case
  matrix (every dataset-format × GPU × framework × dependency-manager
  permutation, zip bombs, malicious repository content, AI-provider
  failure/retry/prompt-injection-through-external-content testing beyond
  what Phase 24/29 already built and this pass didn't re-verify,
  worker-crash/stale-job recovery beyond Phase 18's existing state-
  machine tests, frontend testing of any kind). These are real gaps,
  same honesty standard as every other doc in this repo — not silently
  implied to be covered.
- **Not covered**: sustained load/stress testing, memory-leak detection,
  and the full spec evaluation-metric list (`docs/EVALUATION_PLAN.md`
  already documents exactly which of those are and aren't measurable
  without dedicated load-testing infrastructure this pass didn't build).
- **A real, previously-undetectable class of bug was found** (§8) by
  virtue of finally having a real Postgres to run against — this is
  strong evidence that the "no reachable Postgres" constraint every
  prior phase operated under was hiding real behavior, not just an
  inconvenience. Recommended follow-up: keep `docker-compose.test.yml`
  wired into a real CI pipeline (none exists in this repo currently) so
  this class of bug is caught automatically going forward, rather than
  only during an occasional manual hardening pass like this one.
