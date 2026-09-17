# Performance Optimization (Phase 30)

Status: implemented, **REDUCED SCOPE**, unit-tested (no live Postgres or
Docker daemon in this dev environment, so nothing here was measured
against real infrastructure - see "What's still deferred" below).

## Spec requirement

The spec's own 32-phase roadmap names Phase 30 "Performance
optimization" with no further concrete requirement text (unlike most
other phases, which quote a specific spec section). Prior tracker rows
marked it "OUT OF SCOPE for MVP - no load/scale testing yet." This phase
turns that into the concrete work that's actually achievable without a
reachable database or container runtime: schema indexes and N+1 query
elimination, both verifiable by code inspection and unit test rather
than by measurement against live infra.

## What was done

### 1. Indexes on filtered/joined FK columns

Before this phase, only `Project.slug` had an explicit index. Every
other foreign key actually filtered or joined on by a router or the
Excel export lacked one, meaning Postgres would sequential-scan the
owning table for every such lookup once tables grow past a trivial size.
Added `index=True` to:

- `Experiment.project_id` (`app/db/models/core.py`) - filtered by
  `GET /experiments?project_id=`.
- `ExperimentRun.experiment_id` (`core.py`) - filtered by
  `GET /lineage/{run_id}` and the Excel export's lineage sheet.
- `ExperimentComparison.base_run_id` / `compare_run_id`
  (`app/db/models/comparison.py`) - filtered by the same two call sites.
- `Difference.comparison_id` (`comparison.py`) - joined by
  `GET /search?q=`.
- `ProvenanceNode.run_id`, `ProvenanceEdge.from_node_id` /
  `to_node_id` (`app/db/models/graph.py`) - filtered by
  `GET /provenance/{run_id}`.

`ReproducibilityAssessment.comparison_id` was left alone - it already
carries `unique=True`, which Postgres backs with an implicit unique
index.

Migration: `backend/alembic/versions/f0645ccda9ee_phase_30_performance_indexes.py`,
chained after the Phase 2 initial migration. Hand-written rather than
`alembic revision --autogenerate` (same reason every DB migration in
this project has been hand-written or unverified: no reachable Postgres
in this session to generate or apply against). Structurally mirrors the
initial migration's `op.create_index`/`op.f()` naming convention;
**never run against a real database here.**

### 2. Eliminated two N+1 query sites in the Excel export

Both were in `app/export/excel.py`, introduced in Phase 27:

- `_lineage_edges_for_experiments()` issued one `ExperimentRun` query and
  one conditional `ExperimentComparison` query *per experiment*
  (`1 + 2N` queries for N experiments). Rewritten to fetch all runs and
  all comparisons once, then group them by experiment in Python with
  dictionaries built from the run→experiment mapping - 3 fixed queries
  regardless of N.
- `_reports_for_comparisons()` issued two `db.get(ExperimentRun)` calls,
  one `db.get(Experiment)`, and one `ReproducibilityAssessment` filter
  query *per comparison* (`1 + 4N` queries for N comparisons). Rewritten
  to bulk-fetch all needed runs/experiments/assessments via
  `.filter(Model.id.in_(...))` once each, then look them up from
  in-memory dicts - 4 fixed queries regardless of N.

Both functions produce identical output to before; only the query shape
changed, not the returned `LineageEdge` tuples or `report` objects.

Regression tests: `backend/tests/unit/test_export_query_count.py`. A
minimal fake `Session` (`_CountingSession`/`_CountingQuery`) counts
`db.query()` calls and serves fixed in-memory rows (ignoring filter
predicates - adequate since the point under test is call *count*, not
SQL correctness). Each rewritten function is run once against a 2-item
fixture and once against a 10-item fixture; both assert the same fixed
query count (3 for lineage, 4 for reports), proving the fix, not just
asserting a number - a version of this test run against the old code
would fail (5 vs 21, and 9 vs 41, respectively). 3 new tests, full unit
suite: 297/297 green (1 pre-existing unrelated failure in
`test_api_app_wiring.py` - route-registration wiring, not touched by
this phase - was already failing before Phase 30 and is out of this
phase's scope).

## What's still deferred, and why

- **Real load/scale/stress testing.** This needs a reachable Postgres
  and, for the sandbox execution path, a Docker daemon - neither exists
  in this dev environment, and no phase has been able to exercise either
  live (see every DB/Docker-touching phase's caveat, e.g. Phase 17/19's
  notes). Nothing here should be read as "performance-verified at scale,"
  only "the obvious static inefficiencies found by code review are
  fixed."
- **`search/provider.py`'s `TfidfSearchProvider.score()`** re-fits its
  vocabulary and TF-IDF matrix from scratch on every call, with no
  persistent index across queries. Fine at MVP corpus sizes; building a
  persistent/incremental index is a real feature, not a small fix, so
  it's left as a documented gap rather than attempted here.
- **`provenance/dataset.py`'s schema/stats capture** (`pd.read_csv()`)
  loads a full dataset into memory even though the separate hashing step
  (`_stream_sha256()`) is correctly streamed in 1 MiB chunks. A chunked
  rewrite of the stats path is a genuine improvement but a larger,
  separate change than this phase's scope.
- **`export/excel.py`'s `generate_full_export()`** still issues 12
  unfiltered `db.query(Model).all()` calls with no pagination - this was
  an intentional Phase 27 design decision ("single full-database export,
  matching every other unfiltered bulk query in this codebase"), not a
  regression, and isn't revisited here.
