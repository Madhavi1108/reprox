# REPROX Phase Tracker

Tracks progress against the spec's own 32-phase roadmap (REPROX.pdf §82),
not a condensed order. I will implement **one phase at a time and stop for
your review/go-ahead after each phase**, rather than continuing through
multiple phases automatically.

Status legend: `DONE` (implemented+tested+verified), `IN PROGRESS`,
`NOT STARTED`, `REDUCED SCOPE` (built at MVP depth per the approved plan's
scoping decisions, not the full spec depth — noted explicitly so nothing
is silently dropped).

| # | Phase | Status | Notes |
|---|-------|--------|-------|
| 1 | Project foundation | **DONE** | Repo scaffold, docker-compose (Postgres), backend venv, `/health` + `/health/db`, verified live. |
| 2 | Database | **DONE** | 22-table SQLAlchemy schema, Alembic initial migration applied, FK integrity smoke-tested against real Postgres. |
| 3 | Experiment domain model | **DONE** | `User`/`Project`/`Experiment`/`ExperimentRun` models (built alongside Phase 2's migration). CRUD API endpoints are **not** built yet — that's part of Phase 19 (FastAPI). |
| 4 | Git/code provenance | **DONE** | `app/provenance/code.py`: tree fingerprint from on-disk content (not commit SHA), dirty/detached-HEAD/shallow-clone/no-repo detection. 8 unit tests passing (real temp git repos), 22/22 total unit suite green. |
| 5 | Dataset provenance | NOT STARTED | Content hash, schema, stats, multi-level comparison groundwork. |
| 6 | Environment provenance | NOT STARTED | OS/Python/deps capture + fingerprint. |
| 7 | Configuration provenance | **DONE** | Canonicalization primitive + config fingerprint + 4 unit tests, all passing. |
| 8 | Randomness provenance | NOT STARTED | Seed capture + determinism classification (was about to start when paused). |
| 9 | Artifact provenance | NOT STARTED | Artifact recording (schema exists; capture logic pending — depends on Phase 17 sandbox producing real artifacts). |
| 10 | Fingerprint engine | NOT STARTED | Composite fingerprint assembly + versioning (depends on Phases 4–9). |
| 11 | Experiment comparison | NOT STARTED | Per-category comparators. |
| 12 | Reproducibility classification | NOT STARTED | Deterministic decision-table classifier. |
| 13 | Metric tolerance | NOT STARTED | Abs/rel tolerance module. |
| 14 | Contributor analysis | **REDUCED SCOPE** (per approved MVP plan) | `Difference.is_potential_contributor` flag exists in schema; ranking algorithm deferred to a later session — see `docs/OUT_OF_SCOPE.md` (to be written). |
| 15 | Experiment lineage | **REDUCED SCOPE** | `parent_run_id` exists on `ExperimentRun`; lineage graph traversal/UI deferred. |
| 16 | Provenance graph | **REDUCED SCOPE** | `provenance_nodes`/`provenance_edges` tables exist (schema only); no traversal/reasoning logic. |
| 17 | Execution sandbox | NOT STARTED | Docker-based sklearn runner, resource/time limits. |
| 18 | Background jobs | **REDUCED SCOPE** (planned) | In-process asyncio job tracker with the spec's state machine, not a Redis/queue worker — documented substitution. |
| 19 | FastAPI | NOT STARTED | Projects/Experiments/Runs/Compare/Reproducibility/Jobs/Dashboard endpoints. |
| 20 | React dashboard | NOT STARTED | Vite+Tailwind scaffold + Dashboard/Projects/Experiments pages. |
| 21 | Comparison UI | NOT STARTED | Side-by-side MATCH/DIFFERENCE/UNKNOWN view. |
| 22 | Investigation engine | **OUT OF SCOPE for MVP** | Full controlled-investigation workflow deferred; only the `INVESTIGATION` run-type enum value exists. |
| 23 | Counterfactual engine | **OUT OF SCOPE for MVP** | Deferred entirely. |
| 24 | AI explanation layer | **REDUCED SCOPE** (per approved MVP plan) | `AIProvider` interface + `NullProvider` stub only; no live LLM wired (no API key available). |
| 25 | Semantic search | **OUT OF SCOPE for MVP** | Deferred; only structured filtering via normal API query params. |
| 26 | Reporting | **OUT OF SCOPE for MVP** | Deferred. |
| 27 | Excel export | **OUT OF SCOPE for MVP** | Deferred. |
| 28 | Benchmarking | **REDUCED SCOPE** | A handful of concrete acceptance scenarios (identical rerun, config-only change, dataset-only change, missing provenance) instead of the full drift-type benchmark suite. |
| 29 | Security hardening | **REDUCED SCOPE** | Docker sandbox isolation (Phase 17) is real; full security test suite (path traversal, injection, secret-leakage, etc.) deferred. No auth/RBAC — single seeded user. |
| 30 | Performance optimization | **OUT OF SCOPE for MVP** | Deferred; no load/scale testing yet. |
| 31 | End-to-end testing | **REDUCED SCOPE** | API-level e2e scenarios (Phase 12/13 dependent); no Playwright browser E2E yet. |
| 32 | Documentation | IN PROGRESS | This tracker + `docs/MVP.md`/`docs/OUT_OF_SCOPE.md` to be written; algorithm docs (`FINGERPRINT_ALGORITHM.md` etc.) written alongside each relevant phase. |

## Scope note

This tracker reconciles the spec's full 32-phase roadmap with the
scoping decisions you already approved (see the plan file and
`docs/MVP.md`): several phases are marked **REDUCED SCOPE** or **OUT OF
SCOPE for MVP** rather than skipped outright, so every phase from the PDF
has an explicit status and reasoning — nothing is silently dropped. If
you'd rather build any of the reduced/out-of-scope phases at full depth
now instead of later, tell me which ones and I'll re-sequence.

## Working agreement

I will implement **one phase at a time**, run its tests, report results,
and **stop and wait for your go-ahead** before starting the next phase —
no more auto-continuing through the whole build order.
