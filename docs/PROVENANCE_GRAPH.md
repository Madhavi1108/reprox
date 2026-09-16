# Provenance Graph

Status: implemented (Phase 16), unit-tested, MVP scope.

Spec section 37 (pulled directly from `REPROX.pdf` pages 33–34, since
`pages_out.txt` doesn't cover it) requires:

> Represent: Experiment → Code, Commit, Dataset, Data Split, Pipeline, Environment, Dependency, Hardware, Configuration, Randomness, Model, Artifact, Metric. Relationships: `USED_CODE`, `USED_DATASET`, `USED_ENVIRONMENT`, `USED_CONFIGURATION`, `PRODUCED_ARTIFACT`, `PRODUCED_METRIC`, `DERIVED_FROM`, `REPRODUCES`, `DIFFERS_FROM`. Use the graph for actual reasoning. Do not create graph data merely for visualization.

Implemented in `app/provenance_graph/graph.py`
(`PROVENANCE_GRAPH_ALGORITHM_VERSION = "1.0.0"`).

## Lineage vs. Provenance Graph (Phase 15 vs 16)

See `docs/EXPERIMENT_LINEAGE.md` for the full boundary discussion. In
short: lineage (§36, Phase 15) is a narrower run-to-run execution graph;
provenance graph (§37, this phase) covers heterogeneous entities used or
produced *within* a run, plus the same run-to-run facts represented as
edges between run nodes in this richer graph.

## Node types: 6 of 13 (+ the run hub)

The spec names 13 entity types, but only 6 have a corresponding edge
defined in its own relationship vocabulary:

| Entity | Node type | Edge |
|---|---|---|
| Code | `CODE` | `USED_CODE` |
| Dataset | `DATASET` | `USED_DATASET` |
| Environment | `ENVIRONMENT` | `USED_ENVIRONMENT` |
| Configuration | `CONFIGURATION` | `USED_CONFIGURATION` |
| Artifact | `ARTIFACT` | `PRODUCED_ARTIFACT` |
| Metric | `METRIC` | `PRODUCED_METRIC` |

`Commit`, `Data Split`, `Pipeline`, `Dependency`, `Hardware`, `Model`, and
`Randomness` are named as entities in the spec's list but have **no**
corresponding `USED_*`/`PRODUCED_*` edge in its relationship list.
Building nodes for them would mean inventing relationship semantics the
spec never specified — deferred and documented, not silently dropped.
(`Commit` is already represented as a field on the `CODE` node's
underlying data; `Dependency`/`Hardware` are fields on `ENVIRONMENT`.)

Every run also gets one `EXPERIMENT_RUN` hub node, the source of every
`USED_*`/`PRODUCED_*` edge for that run.

## Edge types: 9 of 9 — full coverage

Unlike the node scope, all 9 spec-listed edge types are implemented:

- `USED_CODE`/`USED_DATASET`/`USED_ENVIRONMENT`/`USED_CONFIGURATION`,
  `PRODUCED_ARTIFACT`/`PRODUCED_METRIC` — built directly by
  `build_run_subgraph()` from whichever categories/artifacts/metrics are
  given (each optional).
- `DERIVED_FROM`/`REPRODUCES` — **reused from Phase 15**, not
  recomputed. `add_lineage_edges()` takes Phase 15's `LineageEdge` list
  (`app.lineage.graph`) and converts the `DERIVED_FROM`/`REPRODUCES`
  entries into edges between the two runs' `EXPERIMENT_RUN` nodes
  (`COMPARES_WITH` lineage edges are ignored here — that fact is
  represented differently, see below).
- `DIFFERS_FROM` — **reused from Phase 11's `ComparisonResult`**.
  `add_comparison_edges()` adds one edge per in-scope category
  (code/dataset/environment/configuration) whose comparator status is
  exactly `DIFFERENT` — never for `SAME`/`UNKNOWN`/`NOT_COMPARABLE`/
  `PARTIALLY_MATCHING`. `randomness_status`/`metrics_status` are never
  consulted, since those categories have no node type in this phase's
  scope. This is the spec's "actual reasoning" requirement satisfied
  directly: every `DIFFERS_FROM` edge traces back to a real, already-
  verified Phase 11 comparator result, never a guess.

Reusing Phases 11/15 rather than re-deriving these facts means the
provenance graph can never disagree with the comparison/lineage results
it's built from — there's only one source of truth for "did X differ" or
"was Y reproduced from Z."

## Deterministic node identity

`node_id_for(run_id, node_type, key=None)` derives a `uuid.uuid5` from a
fixed namespace constant. Singleton-per-run categories (`EXPERIMENT_RUN`,
`CODE`, `DATASET`, `ENVIRONMENT`, `CONFIGURATION`) use `key=None`;
multi-instance types (`ARTIFACT` keyed by `relative_path`, `METRIC` keyed
by name) use `key`. Determinism means two independent calls describing
the same run/category always produce the same node id — `merge_graphs()`
can de-duplicate by id, and `add_lineage_edges()`/`add_comparison_edges()`
can reference a run's category node by recomputing its id rather than
searching a node list.

**Caller responsibility**: `add_comparison_edges()` computes edge
endpoints via `node_id_for()` without checking the target nodes actually
exist in the graph. Callers must build both runs' subgraphs (via
`build_run_subgraph()`) with the relevant categories present before
merging and adding comparison edges, or the resulting edge will
dangle — the same caller-assembles-correctly contract every other pure
function in this codebase already relies on (e.g. `compare_metrics`
trusts its caller to pass consistent inputs).

## `ref_id` is a documented placeholder

Real per-category persistence tables *do* exist —
`CodeSnapshot`/`DatasetVersion`/`Environment`/`Configuration`/`Artifact`/
`Metric` in `app/db/models/provenance.py` — but nothing in the codebase
yet builds unattached ORM rows for them (Phases 4–9 only produce capture
*dataclasses*; only Phases 11/12 have `assemble_*` functions, and only
for the comparison/classification tables). Building that assembly layer
for 6 more tables is a separate, substantial task outside this phase's
scope. Each `ProvenanceNodeEntry.ref_id` therefore equals its own
`node_id` — a placeholder, not yet a real foreign key — while
`ref_table` still names the real target table for forward compatibility.
Wiring real `ref_id` values is future work once that assembly layer
exists, likely alongside Phase 19.

## Assembly

`assemble_provenance_graph(graph) -> (list[ProvenanceNode], list[ProvenanceEdge])`
builds unattached ORM rows (`app.db.models.graph`), storing
`node_type`/`edge_type` as `.value` strings — those columns are plain
`String(50)`, not a DB enum, so no migration was needed. No DB session is
touched here; wiring persistence is Phase 19's job, mirroring
`app.comparison.engine.assemble_comparison`.
