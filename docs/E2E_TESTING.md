# End-to-End Testing (Phase 31)

Status: implemented, **REDUCED SCOPE**, running (not just unit-tested —
these tests genuinely execute against a real, if SQLite-backed, database
in this environment).

## Spec requirement

The spec's 32-phase roadmap names Phase 31 "End-to-end testing" with no
further concrete requirement text. The prior tracker row said "API-level
e2e scenarios (Phase 12/13 dependent); no Playwright browser E2E yet" —
that note was a stale placeholder; `backend/tests/e2e/` held nothing but
an empty `__init__.py` until this phase.

## The blocker this phase removed

Every DB-touching test written before this phase either mocked the
`Session` entirely (`MagicMock`) or explicitly documented that it
couldn't run against real persistence: `test_api_app_wiring.py`'s own
docstring says "no reachable Postgres exists in this environment... real
request/response behavior against a live database is unverified here."
`test_job_orchestrator.py` goes further, asserting "Postgres-specific
JSONB/UUID columns rule out a quick sqlite substitute."

That blanket assumption doesn't hold for plain DB-backed flows. Verified
directly: `sqlalchemy.dialects.postgresql.UUID` is, as of SQLAlchemy 2.0,
a thin subclass of the generic cross-dialect `Uuid` type — it already
compiles and round-trips correctly through SQLite with real Python
`uuid.UUID` values, no shim needed. The **only** genuine incompatibility
is `postgresql.JSONB`, whose DDL compiler has no SQLite rendering at all
(`CompileError: can't render element of type JSONB`). One
`@compiles(JSONB, "sqlite")` hook mapping it to SQLite's native `JSON`
type (`backend/tests/e2e/conftest.py`) fixes this completely — confirmed
by a full insert/commit/query round-trip through a real
`ReproducibilityAssessment.rationale_json` column returning the exact
dict written. No other Postgres-specific column type exists anywhere in
`app/db/models/` (only `UUID`/`JSONB` are imported from
`sqlalchemy.dialects.postgresql` across all 5 model modules).

This does **not** contradict `test_job_orchestrator.py`'s note — that
one is specifically about `execute_experiment_run`, which also needs a
real Docker daemon to do anything meaningful; the SQLite shim only solves
the DB side. Phase 17/18's sandbox/job execution path remains untested
against live infrastructure, unchanged from every earlier phase's
caveat.

## What was built

`backend/tests/e2e/conftest.py`: registers the JSONB compile hook and a
`client` fixture that, per test, creates a fresh in-memory SQLite engine
(`StaticPool` so every connection in the test shares the same in-memory
DB — a bare `sqlite:///:memory:` engine otherwise hands each connection
its own empty database), runs `Base.metadata.create_all()`, and overrides
`app.dependency_overrides[get_db]` so the real FastAPI app
(`app.main.app`), driven through `fastapi.testclient.TestClient`, reads
and writes that real session. Overrides are cleared on teardown so they
never leak into unit tests run in the same `pytest` invocation (verified:
full suite is 307/307 minus the one pre-existing unrelated failure,
whether or not `tests/e2e` runs before `tests/unit`).

Run creation (`POST /experiments/{id}/runs`) schedules a real
`BackgroundTasks` callback into Phase 17's sandbox, which `TestClient`
executes synchronously as part of the request. Docker *is* reachable in
this dev environment (confirmed directly — `docker.from_env()` connects
and a real image-pull attempt fails after ~3.6s with a 404, handled
gracefully by `SandboxRunner`), but relying on it makes these tests slow
and network-dependent. `execute_experiment_run` is patched to a no-op for
the `client` fixture's lifetime — Phase 17/18 already have their own
dedicated (mocked-Docker-client) coverage; Phase 31 isn't re-testing
sandbox execution, just the DB/API flow around it.

Three real, multi-endpoint flows, each asserting cross-endpoint
consistency of genuinely persisted data (not just 200 OK):

- `test_experiment_lifecycle_e2e.py`: project → experiment → 2 runs →
  compare (with deliberately differing inline code + metrics provenance)
  → reproducibility → report. Asserts the report's reproducibility
  classification matches the dedicated `/reproducibility` endpoint, and
  its experiment/run/difference counts match what was actually created.
- `test_provenance_and_lineage_e2e.py`: `/provenance` (asserts the
  documented "always empty, well-formed" behavior — Phase 16's tables are
  never written to by any phase) and `/lineage` (asserts the real
  `COMPARES_WITH` edge between the two runs just compared).
- `test_investigation_and_search_e2e.py`: investigation + counterfactual
  generation from a real comparison whose classification lands on
  `NOT_REPRODUCIBLE`/`PARTIALLY_REPRODUCIBLE` (the only classifications
  Phase 14's `rank_contributors()` ever flags a potential contributor
  for — achieved by making both code *and* metrics differ between the
  two runs); a 422 case for a comparison with no potential contributor;
  `/search` finding a real persisted project by name; `/dashboard`'s
  counts incrementing after real project/experiment creation.

10 new tests, all green, running against real SQLite-backed persistence.
Full backend suite: 307/307 (1 pre-existing, unrelated failure in
`test_api_app_wiring.py::test_all_spec_endpoints_are_registered` predates
this phase and isn't touched by it).

## What's still explicitly deferred, and why

- **Playwright / real-browser E2E.** Needs a running frontend dev
  server, a running backend, and real browser automation — none
  available in this environment. `frontend/` has never been served
  alongside a live backend in any phase (Phase 20/21's own caveats).
- **Real Postgres-specific behavior.** The SQLite shim proves the ORM
  layer and query logic are dialect-portable, but it can't reproduce
  genuine Postgres-only behavior (exact constraint-violation wording,
  concurrent-transaction semantics, `JSONB` operators). A real Postgres
  run remains unverified, same as every earlier DB-touching phase.
- **Real sandbox/job execution.** `execute_experiment_run` is
  deliberately patched out of these flows (see above) — Phase 17/18 own
  that surface, and neither has been exercised against a real Docker
  daemon end-to-end with a real workload image, only unit-tested against
  a mocked client / a real-but-failing image pull.
