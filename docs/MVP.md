# MVP Scope (Phase 32, spec-required — see docs list at REPROX.pdf, the
page immediately preceding "80. PHASE 0 — ARCHITECTURE & PLANNING")

Status: written now, in the final phase, but referenced by nearly every
other phase doc throughout the build ("your approved plan and
docs/MVP.md") — this backfills the pointer with real content rather than
leaving it dangling.

## What REPROX's MVP actually is

REPROX is an experiment-provenance, reproducibility-classification, and
root-cause-analysis platform: capture code/dataset/environment/
configuration/randomness/artifact provenance for an ML experiment run,
compare two runs, classify whether the reproduction actually reproduces
the original, rank likely contributors when it doesn't, and surface all
of that through an API, a React dashboard, Excel export, and an optional
AI explanation layer.

The MVP built here is:

- **Single-user.** `app/api/deps.py`'s `get_current_user_id` fetches-or-
  creates one seeded user row rather than implementing auth/RBAC — a
  scoping choice, not a spec requirement (the spec has no auth/RBAC
  section at all; see `docs/SECURITY_MODEL.md`).
- **Offline-testable by construction.** No phase depends on a reachable
  Postgres or Docker daemon to be *implemented and unit-tested* — Phase
  31 additionally proved genuine DB-backed multi-endpoint flows are
  testable via an in-memory SQLite substitute (`docs/E2E_TESTING.md`).
  Live Postgres/Docker verification remains a real, repeatedly-documented
  gap (see `docs/OUT_OF_SCOPE.md` and `docs/DEPLOYMENT.md`).
- **Honest about partial data.** Provenance is accepted as an inline
  JSON payload at compare-time (`POST /runs/{id}/compare`), not captured
  server-side from a filesystem the API has no access to (Phase 19's
  documented architecture choice). Every downstream consumer (reporting,
  Excel export, dashboard) reports missing data as `NOT_COMPARABLE` /
  `NOT_AVAILABLE` / empty rather than inventing values — spec RULE 12.

The authoritative, phase-by-phase record of what was built, at what
depth, and why is `docs/PHASE_TRACKER.md` — this document doesn't
duplicate it, only summarizes the shape of the whole.

## Spec-required documentation set: name mapping

The spec (`REPROX.pdf`) names 12 required doc files verbatim. 9 exist
under that exact name. 3 exist under a different name chosen during
their own phase, before this cross-check was done; renaming them now
would break every existing cross-reference to them (`PHASE_TRACKER.md`
and other phase docs link them by their current names) for zero benefit,
so the mapping is recorded here instead:

| Spec-named file | Actual file | Phase |
|---|---|---|
| `docs/COUNTERFACTUAL_ENGINE.md` | `docs/COUNTERFACTUAL_EXPERIMENTS.md` | 23 |
| `docs/EXPERIMENT_EXECUTION.md` | `docs/EXECUTION_SANDBOX.md` | 17 |
| `docs/BENCHMARK.md` | `docs/BENCHMARKING.md` | 28 |

All 12 required topics are covered by real content; only the filename
differs for these 3.

## Where to look

- Phase-by-phase build record: `docs/PHASE_TRACKER.md`
- Everything explicitly deferred, consolidated: `docs/OUT_OF_SCOPE.md`
- Data handling / third-party data flows: `docs/PRIVACY_MODEL.md`
- Threat model: `docs/SECURITY_MODEL.md`
- Test coverage shape: `docs/TESTING.md`
- Known edge cases and how they're handled: `docs/EDGE_CASES.md`
- What's actually deployable today vs. not: `docs/DEPLOYMENT.md`
- Spec evaluation-metric coverage: `docs/EVALUATION_PLAN.md`
