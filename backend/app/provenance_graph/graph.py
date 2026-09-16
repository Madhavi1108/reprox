"""Provenance graph (Phase 16, spec section 37).

Represents heterogeneous entities used/produced by a run - distinct from
Phase 15's lineage graph (`app/lineage/graph.py`), which is a narrower
run-to-run execution graph. Spec: "Represent: Experiment -> Code,
Commit, Dataset, Data Split, Pipeline, Environment, Dependency, Hardware,
Configuration, Randomness, Model, Artifact, Metric. Relationships:
USED_CODE, USED_DATASET, USED_ENVIRONMENT, USED_CONFIGURATION,
PRODUCED_ARTIFACT, PRODUCED_METRIC, DERIVED_FROM, REPRODUCES,
DIFFERS_FROM. Use the graph for actual reasoning. Do not create graph
data merely for visualization."

Scope boundary (see docs/PROVENANCE_GRAPH.md for full detail): of the 13
named entity types, only 6 have a defined edge in the spec's own
relationship vocabulary (CODE/DATASET/ENVIRONMENT/CONFIGURATION/
ARTIFACT/METRIC) - Commit/Data Split/Pipeline/Dependency/Hardware/Model/
Randomness are named but have no corresponding USED_*/PRODUCED_* edge
defined, so building nodes for them would mean inventing relationship
semantics the spec never specified. `DERIVED_FROM`/`REPRODUCES` are
reused directly from Phase 15's lineage edges (not recomputed);
`DIFFERS_FROM` is reused directly from Phase 11's `ComparisonResult`
category statuses - this is the "actual reasoning" the spec asks for,
built from already-verified computations rather than a fresh guess.

`ref_id` on every node is a deterministic placeholder, not yet a real FK
into the per-category persistence tables that do exist
(`CodeSnapshot`/`DatasetVersion`/`Environment`/`Configuration`/`Artifact`/
`Metric` in `app/db/models/provenance.py`) - nothing in the codebase
builds unattached ORM rows for those tables yet (only Phases 11/12 have
`assemble_*` functions, and only for comparison/classification tables).
`ref_table` still names the real target table for forward compatibility.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum

from app.comparison.engine import ComparisonResult
from app.db.models.enums import ComparisonStatus
from app.db.models.graph import ProvenanceEdge, ProvenanceNode
from app.lineage.graph import LineageEdge, LineageEdgeType
from app.provenance.code import CodeProvenance
from app.provenance.configuration import ConfigurationProvenance
from app.provenance.dataset import DatasetProvenance
from app.provenance.environment import EnvironmentProvenance

PROVENANCE_GRAPH_ALGORITHM_VERSION = "1.0.0"

_NODE_ID_NAMESPACE = uuid.UUID("6f1e6a2e-6b8b-4b7a-9c3d-1a2b3c4d5e6f")


class ProvenanceNodeType(str, Enum):
    EXPERIMENT_RUN = "EXPERIMENT_RUN"
    CODE = "CODE"
    DATASET = "DATASET"
    ENVIRONMENT = "ENVIRONMENT"
    CONFIGURATION = "CONFIGURATION"
    ARTIFACT = "ARTIFACT"
    METRIC = "METRIC"


class ProvenanceEdgeType(str, Enum):
    USED_CODE = "USED_CODE"
    USED_DATASET = "USED_DATASET"
    USED_ENVIRONMENT = "USED_ENVIRONMENT"
    USED_CONFIGURATION = "USED_CONFIGURATION"
    PRODUCED_ARTIFACT = "PRODUCED_ARTIFACT"
    PRODUCED_METRIC = "PRODUCED_METRIC"
    DERIVED_FROM = "DERIVED_FROM"
    REPRODUCES = "REPRODUCES"
    DIFFERS_FROM = "DIFFERS_FROM"


_REF_TABLE = {
    ProvenanceNodeType.EXPERIMENT_RUN: "experiment_runs",
    ProvenanceNodeType.CODE: "code_snapshots",
    ProvenanceNodeType.DATASET: "dataset_versions",
    ProvenanceNodeType.ENVIRONMENT: "environments",
    ProvenanceNodeType.CONFIGURATION: "configurations",
    ProvenanceNodeType.ARTIFACT: "artifacts",
    ProvenanceNodeType.METRIC: "metrics",
}

_USED_EDGE_TYPE = {
    ProvenanceNodeType.CODE: ProvenanceEdgeType.USED_CODE,
    ProvenanceNodeType.DATASET: ProvenanceEdgeType.USED_DATASET,
    ProvenanceNodeType.ENVIRONMENT: ProvenanceEdgeType.USED_ENVIRONMENT,
    ProvenanceNodeType.CONFIGURATION: ProvenanceEdgeType.USED_CONFIGURATION,
}

_LINEAGE_TO_PROVENANCE_EDGE_TYPE = {
    LineageEdgeType.DERIVED_FROM: ProvenanceEdgeType.DERIVED_FROM,
    LineageEdgeType.REPRODUCES: ProvenanceEdgeType.REPRODUCES,
}

# Comparison-status field name -> in-scope provenance node type. Randomness
# and metrics have no node type in this phase's scope (see module docstring),
# so their statuses are never consulted here even if DIFFERENT.
_COMPARISON_FIELD_TO_NODE_TYPE = {
    "code_status": ProvenanceNodeType.CODE,
    "dataset_status": ProvenanceNodeType.DATASET,
    "environment_status": ProvenanceNodeType.ENVIRONMENT,
    "configuration_status": ProvenanceNodeType.CONFIGURATION,
}


def node_id_for(run_id: uuid.UUID, node_type: ProvenanceNodeType, key: str | None = None) -> uuid.UUID:
    name = f"{run_id}:{node_type.value}:{key or ''}"
    return uuid.uuid5(_NODE_ID_NAMESPACE, name)


@dataclass(frozen=True)
class ProvenanceNodeEntry:
    node_id: uuid.UUID
    node_type: ProvenanceNodeType
    run_id: uuid.UUID
    label: str
    ref_table: str
    ref_id: uuid.UUID


@dataclass(frozen=True)
class ProvenanceEdgeEntry:
    from_node_id: uuid.UUID
    to_node_id: uuid.UUID
    edge_type: ProvenanceEdgeType


@dataclass(frozen=True)
class ProvenanceGraph:
    nodes: list[ProvenanceNodeEntry] = field(default_factory=list)
    edges: list[ProvenanceEdgeEntry] = field(default_factory=list)


def _make_node(run_id: uuid.UUID, node_type: ProvenanceNodeType, label: str, key: str | None = None) -> ProvenanceNodeEntry:
    node_id = node_id_for(run_id, node_type, key)
    return ProvenanceNodeEntry(
        node_id=node_id,
        node_type=node_type,
        run_id=run_id,
        label=label,
        ref_table=_REF_TABLE[node_type],
        ref_id=node_id,
    )


def build_run_subgraph(
    run_id: uuid.UUID,
    *,
    code: CodeProvenance | None = None,
    dataset: DatasetProvenance | None = None,
    environment: EnvironmentProvenance | None = None,
    configuration: ConfigurationProvenance | None = None,
    artifacts: tuple = (),
    metrics: dict[str, float] | None = None,
) -> ProvenanceGraph:
    run_node = _make_node(run_id, ProvenanceNodeType.EXPERIMENT_RUN, label=str(run_id))
    nodes: list[ProvenanceNodeEntry] = [run_node]
    edges: list[ProvenanceEdgeEntry] = []

    category_inputs = {
        ProvenanceNodeType.CODE: code,
        ProvenanceNodeType.DATASET: dataset,
        ProvenanceNodeType.ENVIRONMENT: environment,
        ProvenanceNodeType.CONFIGURATION: configuration,
    }
    for node_type, value in category_inputs.items():
        if value is None:
            continue
        node = _make_node(run_id, node_type, label=node_type.value)
        nodes.append(node)
        edges.append(
            ProvenanceEdgeEntry(from_node_id=run_node.node_id, to_node_id=node.node_id, edge_type=_USED_EDGE_TYPE[node_type])
        )

    for artifact in artifacts:
        node = _make_node(run_id, ProvenanceNodeType.ARTIFACT, label=artifact.relative_path, key=artifact.relative_path)
        nodes.append(node)
        edges.append(
            ProvenanceEdgeEntry(
                from_node_id=run_node.node_id, to_node_id=node.node_id, edge_type=ProvenanceEdgeType.PRODUCED_ARTIFACT
            )
        )

    for name in metrics or {}:
        node = _make_node(run_id, ProvenanceNodeType.METRIC, label=name, key=name)
        nodes.append(node)
        edges.append(
            ProvenanceEdgeEntry(
                from_node_id=run_node.node_id, to_node_id=node.node_id, edge_type=ProvenanceEdgeType.PRODUCED_METRIC
            )
        )

    return ProvenanceGraph(nodes=nodes, edges=edges)


def merge_graphs(*graphs: ProvenanceGraph) -> ProvenanceGraph:
    nodes_by_id: dict[uuid.UUID, ProvenanceNodeEntry] = {}
    edges: list[ProvenanceEdgeEntry] = []
    for graph in graphs:
        for node in graph.nodes:
            nodes_by_id.setdefault(node.node_id, node)
        edges.extend(graph.edges)
    return ProvenanceGraph(nodes=list(nodes_by_id.values()), edges=edges)


def add_lineage_edges(graph: ProvenanceGraph, lineage_edges: list[LineageEdge]) -> ProvenanceGraph:
    new_edges = list(graph.edges)
    for lineage_edge in lineage_edges:
        edge_type = _LINEAGE_TO_PROVENANCE_EDGE_TYPE.get(lineage_edge.edge_type)
        if edge_type is None:
            continue
        new_edges.append(
            ProvenanceEdgeEntry(
                from_node_id=node_id_for(lineage_edge.from_run_id, ProvenanceNodeType.EXPERIMENT_RUN),
                to_node_id=node_id_for(lineage_edge.to_run_id, ProvenanceNodeType.EXPERIMENT_RUN),
                edge_type=edge_type,
            )
        )
    return ProvenanceGraph(nodes=graph.nodes, edges=new_edges)


def add_comparison_edges(
    graph: ProvenanceGraph, base_run_id: uuid.UUID, compare_run_id: uuid.UUID, comparison: ComparisonResult
) -> ProvenanceGraph:
    new_edges = list(graph.edges)
    for field_name, node_type in _COMPARISON_FIELD_TO_NODE_TYPE.items():
        if getattr(comparison, field_name) != ComparisonStatus.DIFFERENT:
            continue
        new_edges.append(
            ProvenanceEdgeEntry(
                from_node_id=node_id_for(base_run_id, node_type),
                to_node_id=node_id_for(compare_run_id, node_type),
                edge_type=ProvenanceEdgeType.DIFFERS_FROM,
            )
        )
    return ProvenanceGraph(nodes=graph.nodes, edges=new_edges)


def assemble_provenance_graph(graph: ProvenanceGraph) -> tuple[list[ProvenanceNode], list[ProvenanceEdge]]:
    """Build unattached ORM rows from a `ProvenanceGraph`. The caller is
    responsible for `session.add()`/`commit()` once a DB session exists
    (Phase 19), mirroring `app.comparison.engine.assemble_comparison`."""
    nodes = [
        ProvenanceNode(
            id=entry.node_id,
            run_id=entry.run_id,
            node_type=entry.node_type.value,
            ref_table=entry.ref_table,
            ref_id=entry.ref_id,
        )
        for entry in graph.nodes
    ]
    edges = [
        ProvenanceEdge(
            id=uuid.uuid4(),
            from_node_id=entry.from_node_id,
            to_node_id=entry.to_node_id,
            edge_type=entry.edge_type.value,
        )
        for entry in graph.edges
    ]
    return nodes, edges
