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
| 5 | Dataset provenance | **DONE** | `app/provenance/dataset.py`: streamed content-hash (Level 1), schema (Level 2), per-column stats/duplicates (Level 3 groundwork). Level 4/5 explicitly deferred. 9 unit tests passing, incl. "same row count, different content/hash, same schema, different distribution" and missing/corrupted-file error cases. Full unit suite: 31/31 green. |
| 6 | Environment provenance | **DONE** | `app/provenance/environment.py`: hash over OS/arch/Python/GPU-CUDA(null)/tracked-dependency-versions; hostname/CPU/RAM captured but structurally excluded from the hash. 9 unit tests passing. Full unit suite: 40/40 green. |
| 7 | Configuration provenance | **DONE** | Canonicalization primitive + config fingerprint + 4 unit tests, all passing. |
| 8 | Randomness provenance | **DONE** | `app/provenance/randomness.py`: seed capture + determinism classification that never reaches outright `DETERMINISTIC`; declared-but-unbound stochastic params (e.g. unset `random_state`) correctly force `NON_DETERMINISTIC`. 10 unit tests passing. Full unit suite: 50/50 green. |
| 9 | Artifact provenance | **DONE** | `app/provenance/artifact.py`: content-hash + type classification for individual files and whole output directories, ready to be pointed at Phase 17's sandbox `/output` once it exists. 11 unit tests passing. Full unit suite: 61/61 green. |
| 10 | Fingerprint engine | **DONE** | `app/fingerprint/composite.py`: composite hash over the 5 category hashes with explicit-null missing-component tracking, versioned (`1.0.0`), never silently recomputed. 10 unit tests passing (incl. real end-to-end assembly from Phases 4-8's actual capture functions). Full unit suite: 71/71 green. `docs/FINGERPRINT_ALGORITHM.md` written. |
| 11 | Experiment comparison | **DONE** | `app/comparison/`: 5 pure per-category comparators (code/dataset/environment/configuration/randomness) + `engine.py` orchestrator producing unattached `ExperimentComparison`/`Difference` ORM instances (no DB session wiring - that's Phase 19). Hash fast-path + explicit NOT_COMPARABLE (both-missing, version-mismatch) / UNKNOWN (one-side-missing) handling per category, mirroring Phase 10's None-handling discipline. `metrics_status` stays `UNKNOWN` (Phase 13's job); `is_potential_contributor` stays `False` (Phase 14's job). `PARTIALLY_MATCHING` deliberately left unused - see `docs/COMPARISON_ENGINE.md`. 51 new unit tests passing, full unit suite: 122/122 green. `docs/COMPARISON_ENGINE.md` written. |
| 12 | Reproducibility classification | **DONE** | `app/reproducibility/classifier.py`: pure `classify_reproducibility()` over two categorical axes (outcome = `metrics_status`, setup = aggregate of the 5 provenance categories) mapping to the 7-state `ReproducibilityClassification` enum, no numeric thresholds. `assemble_reproducibility_assessment()` builds an unattached `ReproducibilityAssessment` ORM row (DB wiring is Phase 19's job). Correctly lands on `INSUFFICIENT_EVIDENCE`/`NOT_COMPARABLE` for essentially all real comparisons today, since `metrics_status` won't carry real signal until Phase 13. 11 new unit tests passing, full unit suite: 133/133 green. `docs/REPRODUCIBILITY_CLASSIFICATION.md` written. |
| 13 | Metric tolerance | **DONE** | `app/comparison/category_comparators/metrics.py`: documented, versioned abs/rel tolerance formula (`abs(old-new) <= max(abs_tol, rel_tol*max(|old|,|new|))`), both tolerances defaulting to `0.0` (exact equality unless explicitly configured — no arbitrary embedded threshold), with per-metric overrides. Wired into `compare_experiments()` as the 6th comparator, replacing the old hardcoded `metrics_status = UNKNOWN`. No `ExperimentRun` metrics-storage column exists yet, so callers without real metrics correctly get `NOT_COMPARABLE`; ready to be pointed at real captured metrics once a later phase stores them. Statistical tolerance/confidence intervals explicitly out of scope (need distributional data a scalar snapshot doesn't have). 13 new unit tests, full unit suite: 146/146 green. `docs/METRIC_TOLERANCE.md` written; `docs/COMPARISON_ENGINE.md` updated. |
| 14 | Contributor analysis | **DONE** | `app/contributor/ranking.py`: deterministic `rank_contributors()` combining `severity`/`confidence` (the "difference magnitude" input from spec section 32 — the only one of 7 listed inputs REPROX can compute today; the other 6 need infrastructure from Phases 22/23, both already OUT OF SCOPE, or a historical-run store that doesn't exist) into a HIGH/MODERATE/LOW evidence-strength lattice, triggered only for `NOT_REPRODUCIBLE`/`PARTIALLY_REPRODUCIBLE` classifications, excluding `METRICS`-category differences (the effect, not a cause). Only ever produces "Potential contributor" (never Validated/Confirmed — those need Phase 22/23's controlled reruns), per spec section 31's four-state model. Wired into `assemble_comparison()` as an optional `ranking` parameter (backward compatible — omitting it keeps Phase 11's `False` default). 10 new unit tests passing, full unit suite: 156/156 green. `docs/CONTRIBUTOR_ANALYSIS.md` written. |
| 15 | Experiment lineage | **DONE** | `app/lineage/graph.py`: deterministic run-to-run lineage graph construction (`build_lineage_graph`) and cycle-safe `ancestors`/`descendants` traversal. Produces 3 of the spec's 6 edge types from data that actually exists (`REPRODUCES` from `run_type`, `DERIVED_FROM` as the honest default, `COMPARES_WITH` from `ExperimentComparison`); `MODIFIES`/`COUNTERFACTUAL_OF`/`VALIDATES` explicitly deferred pending Phase 22/23 infrastructure (both already OUT OF SCOPE), documented rather than guessed at. Lineage UI (§59) and `GET /lineage/{id}` (§61) remain Phase 21/19's job. 7 new unit tests (incl. the spec's own worked tree example), full unit suite: 163/163 green. `docs/EXPERIMENT_LINEAGE.md` written. |
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
