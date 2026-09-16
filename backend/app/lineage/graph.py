"""Experiment lineage graph (Phase 15, spec section 36).

Builds a run-to-run lineage graph: "Each node represents an actual
execution. Edges should represent: DERIVED_FROM, REPRODUCES, MODIFIES,
COUNTERFACTUAL_OF, VALIDATES, COMPARES_WITH."

This is the narrower run-execution graph, distinct from Phase 16's
provenance graph (spec section 37), which represents heterogeneous
entities (code/dataset/environment/.../artifact/metric) rather than just
runs - see docs/EXPERIMENT_LINEAGE.md for the full boundary discussion.

Only 3 of the 6 spec edge types can be honestly derived from data that
exists today:

- `run_type == REPRODUCTION` with a parent -> `REPRODUCES`
- any other parent link (`ORIGINAL`/`INVESTIGATION`) -> `DERIVED_FROM`,
  the generic, honest default - `INVESTIGATION` alone doesn't tell us
  *which* factor changed or whether a counterfactual/validation rerun
  actually took place, so assigning `MODIFIES`/`COUNTERFACTUAL_OF`/
  `VALIDATES` without that evidence would overclaim
- an `ExperimentComparison` between two runs -> `COMPARES_WITH`

`MODIFIES`, `COUNTERFACTUAL_OF`, `VALIDATES` require Phase 22/23
infrastructure (controlled investigation / counterfactual experiments),
both already OUT OF SCOPE for MVP - the enum still declares all 6 values
for a complete, forward-compatible vocabulary, but only the 3 above are
ever produced by `build_lineage_graph`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum

from app.db.models.enums import RunType

LINEAGE_ALGORITHM_VERSION = "1.0.0"


class LineageEdgeType(str, Enum):
    DERIVED_FROM = "DERIVED_FROM"
    REPRODUCES = "REPRODUCES"
    MODIFIES = "MODIFIES"
    COUNTERFACTUAL_OF = "COUNTERFACTUAL_OF"
    VALIDATES = "VALIDATES"
    COMPARES_WITH = "COMPARES_WITH"


_PARENT_CHILD_EDGE_TYPES = frozenset({LineageEdgeType.DERIVED_FROM, LineageEdgeType.REPRODUCES})


@dataclass(frozen=True)
class RunNode:
    run_id: uuid.UUID
    parent_run_id: uuid.UUID | None
    run_type: RunType


@dataclass(frozen=True)
class ComparisonLink:
    base_run_id: uuid.UUID
    compare_run_id: uuid.UUID


@dataclass(frozen=True)
class LineageEdge:
    from_run_id: uuid.UUID
    to_run_id: uuid.UUID
    edge_type: LineageEdgeType


@dataclass(frozen=True)
class LineageGraph:
    nodes: list[RunNode] = field(default_factory=list)
    edges: list[LineageEdge] = field(default_factory=list)


def build_lineage_graph(runs: list[RunNode], comparisons: list[ComparisonLink] | None = None) -> LineageGraph:
    comparisons = comparisons or []
    edges: list[LineageEdge] = []

    for run in runs:
        if run.parent_run_id is None:
            continue
        edge_type = LineageEdgeType.REPRODUCES if run.run_type == RunType.REPRODUCTION else LineageEdgeType.DERIVED_FROM
        edges.append(LineageEdge(from_run_id=run.parent_run_id, to_run_id=run.run_id, edge_type=edge_type))

    for link in comparisons:
        edges.append(
            LineageEdge(
                from_run_id=link.base_run_id, to_run_id=link.compare_run_id, edge_type=LineageEdgeType.COMPARES_WITH
            )
        )

    return LineageGraph(nodes=list(runs), edges=edges)


def ancestors(graph: LineageGraph, run_id: uuid.UUID) -> list[uuid.UUID]:
    parent_of: dict[uuid.UUID, uuid.UUID] = {
        edge.to_run_id: edge.from_run_id for edge in graph.edges if edge.edge_type in _PARENT_CHILD_EDGE_TYPES
    }

    result: list[uuid.UUID] = []
    visited: set[uuid.UUID] = {run_id}
    current = run_id
    while current in parent_of:
        parent = parent_of[current]
        if parent in visited:
            break
        result.append(parent)
        visited.add(parent)
        current = parent

    return result


def descendants(graph: LineageGraph, run_id: uuid.UUID) -> list[uuid.UUID]:
    children_of: dict[uuid.UUID, list[uuid.UUID]] = {}
    for edge in graph.edges:
        if edge.edge_type in _PARENT_CHILD_EDGE_TYPES:
            children_of.setdefault(edge.from_run_id, []).append(edge.to_run_id)

    result: list[uuid.UUID] = []
    visited: set[uuid.UUID] = {run_id}
    queue: list[uuid.UUID] = list(children_of.get(run_id, []))
    while queue:
        child = queue.pop(0)
        if child in visited:
            continue
        visited.add(child)
        result.append(child)
        queue.extend(children_of.get(child, []))

    return result
