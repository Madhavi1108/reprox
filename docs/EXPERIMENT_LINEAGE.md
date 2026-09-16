# Experiment Lineage

Status: implemented (Phase 15), unit-tested, MVP scope.

Spec section 36 (pulled directly from `REPROX.pdf` pages 32–33, since the
tracked `pages_out.txt` excerpt doesn't cover this section) requires
REPROX to "build an experiment lineage graph" where each node represents
an actual execution and edges represent: `DERIVED_FROM`, `REPRODUCES`,
`MODIFIES`, `COUNTERFACTUAL_OF`, `VALIDATES`, `COMPARES_WITH`. Implemented
in `app/lineage/graph.py` (`LINEAGE_ALGORITHM_VERSION = "1.0.0"`).

## Lineage vs. Provenance Graph (Phase 15 vs 16)

Spec section 37, immediately following section 36, defines a distinct
and much broader **Provenance Graph**: nodes are heterogeneous entities
(Code, Commit, Dataset, Environment, Dependency, Hardware, Configuration,
Randomness, Model, Artifact, Metric), with `USED_*`/`PRODUCED_*`/
`DERIVED_FROM`/`REPRODUCES`/`DIFFERS_FROM` edges. That's Phase 16 (already
`REDUCED SCOPE`, with its own `provenance_nodes`/`provenance_edges`
tables). This document and module cover only the narrower **run-to-run
execution graph** — nodes are `ExperimentRun`s, nothing else.

## Why only 3 of 6 edge types are produced

The spec wants 6 edge types, but only two data sources exist to derive
edges from today:

- `ExperimentRun.parent_run_id` + `run_type` (`ORIGINAL | REPRODUCTION | INVESTIGATION` — confirmed, no richer enum exists)
- `ExperimentComparison.base_run_id`/`compare_run_id` (Phase 11)

| Edge type | Produced? | Basis |
|---|---|---|
| `REPRODUCES` | Yes | `run_type == REPRODUCTION` with a parent — the enum value states this directly. |
| `DERIVED_FROM` | Yes | Any other parent link (`ORIGINAL`/`INVESTIGATION`) — the generic, honest default. |
| `COMPARES_WITH` | Yes | An `ExperimentComparison` row exists between the two runs. |
| `MODIFIES` | No | Would need to know *which specific factor* an investigation run changed — not recorded anywhere. |
| `COUNTERFACTUAL_OF` | No | Requires Phase 23 (counterfactual experiments) — `OUT OF SCOPE for MVP`. |
| `VALIDATES` | No | Requires Phase 22 (controlled investigation) confirming a rerun actually validated something — `OUT OF SCOPE for MVP`. |

`run_type == INVESTIGATION` alone doesn't distinguish "changed one factor
deliberately" (`MODIFIES`) from "restored one factor as a counterfactual"
(`COUNTERFACTUAL_OF`) from "reran to validate a prior finding"
(`VALIDATES`) — assigning any of those without that evidence would
overclaim. This mirrors `docs/CONTRIBUTOR_ANALYSIS.md`'s same principle:
default to the weaker, defensible state absent controlled evidence,
rather than guess. `LineageEdgeType` still declares all 6 values so the
vocabulary is complete and forward-compatible with Phases 22/23, even
though `build_lineage_graph` only ever emits 3 of them today.

## Graph construction

`build_lineage_graph(runs: list[RunNode], comparisons: list[ComparisonLink] = None) -> LineageGraph`:

- For each run with a `parent_run_id`: emit one edge, `parent → run`,
  typed `REPRODUCES` or `DERIVED_FROM` per the table above.
- For each `ComparisonLink`: emit one `COMPARES_WITH` edge,
  `base_run_id → compare_run_id` (directional field naming inherited
  from `ExperimentComparison`, though the relationship is conceptually
  symmetric).

`RunNode` and `ComparisonLink` are small decoupled dataclasses (not the
SQLAlchemy ORM types) so the module stays pure and DB-free, matching
Phases 10–14's style — callers (Phase 19) project real `ExperimentRun`/
`ExperimentComparison` rows into these before calling in.

## Traversal

`ancestors(graph, run_id)` and `descendants(graph, run_id)` walk only
`DERIVED_FROM`/`REPRODUCES` edges (never `COMPARES_WITH` — a comparison
is not a parent/child relationship). Both include a visited-set cycle
guard: the schema's tree semantics should never produce a cycle, but a
malformed one must not hang a traversal, so each walk stops the moment it
would revisit an already-seen run.

## Scope deferred to later phases

- Lineage UI (spec §59: "select a node and inspect what changed / why it
  was derived / what results changed") — Phase 21/UI work, not built
  here; this phase only provides the graph and traversal it would call.
- `GET /lineage/{id}` endpoint (spec §61) — Phase 19's job (FastAPI);
  no DB session or HTTP layer exists in this module.
- `MODIFIES`/`COUNTERFACTUAL_OF`/`VALIDATES` edges — pending Phase 22/23
  infrastructure, as above.
