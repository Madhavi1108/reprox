# Testing (Phase 32, spec-required, §73 Testing)

Status: new. Maps the spec's required test structure (Unit / Integration
/ Security) to what actually exists in `backend/tests/`.

## Current numbers

`pytest --collect-only` (from `backend/`): **308 tests collected**.
Full run: **307 passing, 1 pre-existing failure**
(`tests/unit/test_api_app_wiring.py::test_all_spec_endpoints_are_registered`
— a route-registration wiring assertion unrelated to any single phase's
functional correctness; not touched or explained away by any phase since
it first appeared).

## Unit tests (`backend/tests/unit/`)

The bulk of the suite. Spec §73 names exactly these required unit-test
areas — all present:

- fingerprinting (`test_composite_fingerprint.py`)
- canonicalization (`test_configuration_fingerprint.py`)
- hashing (`test_dataset_fingerprint.py`, `test_code_fingerprint.py`)
- dataset comparison (`test_comparison_engine.py`)
- schema comparison (`test_dataset_fingerprint.py`)
- dependency comparison (`test_environment_fingerprint.py`)
- environment comparison (`test_environment_fingerprint.py`)
- configuration comparison (`test_comparison_engine.py`)
- randomness comparison (`test_randomness_fingerprint.py`)
- reproducibility classification (`test_reproducibility_classifier.py`)
- metric tolerance (`test_compare_metrics.py`)
- contributor ranking (`test_contributor_ranking.py`)

Plus every other phase's own unit coverage (sandbox security, job
tracker, AI provider, search provider, Excel export, benchmark scenarios,
export query-count regressions, etc.) — the per-phase breakdown and exact
test counts as of each phase are in `docs/PHASE_TRACKER.md`, not repeated
here since they'd immediately go stale.

Almost all of these mock the DB session (`MagicMock`) or test pure
functions with no DB at all — a deliberate choice while no reachable
Postgres existed, not an oversight (see every phase's own "no reachable
Postgres" caveat).

## Integration tests (`backend/tests/integration/`)

Spec §73 names: "API + database + workers + experiment executor +
provenance engine." This directory still holds only an empty
`__init__.py` — genuinely never built. Phase 31's `backend/tests/e2e/`
covers a meaningfully overlapping surface (real API + real database, via
an in-memory SQLite substitute — see below) but stops short of "workers +
experiment executor" (Phase 17/18's sandbox/job path is explicitly
patched out of the E2E flows, `docs/E2E_TESTING.md`) and isn't organized
under `tests/integration/`. This gap is real and named here rather than
quietly worked around by relabeling `tests/e2e/` as satisfying it.

## E2E tests (`backend/tests/e2e/`)

Phase 31: 10 tests, real HTTP requests through `TestClient` against a
real (SQLite-backed, not Postgres) database via `app.dependency_overrides
[get_db]` — genuine multi-endpoint persistence flows (project → experiment
→ runs → compare → reproducibility → report; provenance/lineage;
investigation/counterfactual; search/dashboard), not mocks. Full
rationale and the SQLite-JSONB-compatibility finding: `docs/E2E_TESTING.md`.

## Security tests

Phase 29: `tests/unit/test_security.py` — command injection, secret
leakage, prompt injection, unauthorized access, and a static SQL-
injection regression guard. Full threat-model mapping:
`docs/SECURITY_MODEL.md`.

## What's not tested, and why

- **Real Postgres.** No test in this repo has ever run against a live
  Postgres instance (`docs/OUT_OF_SCOPE.md`).
- **Real Docker workload execution.** `SandboxRunner` is unit-tested
  against a mocked client; Phase 31 confirmed Docker *is* reachable here
  and a real (failing, since the image was never built)
  `containers.run()` call completes in ~3.6s, but no test asserts a
  *successful* real container run.
- **Frontend tests.** `frontend/`'s own build/lint (`npm run build`,
  `npm run lint`) pass (Phase 20/21), but there is no Vitest/Jest unit
  test suite and no Playwright browser E2E.
- **Load/performance tests.** See `docs/EVALUATION_PLAN.md`.
