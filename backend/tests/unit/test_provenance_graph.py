import uuid

from app.comparison.engine import ComparisonResult
from app.db.models.enums import ArtifactType, ComparisonStatus
from app.lineage.graph import LineageEdge, LineageEdgeType
from app.provenance.artifact import ArtifactProvenance
from app.provenance.configuration import capture_configuration_provenance
from app.provenance.dataset import capture_dataset_provenance
from app.provenance.environment import capture_environment_provenance
from app.provenance_graph.graph import (
    ProvenanceEdgeType,
    ProvenanceNodeType,
    add_comparison_edges,
    add_lineage_edges,
    build_run_subgraph,
    merge_graphs,
    node_id_for,
)

SAME = ComparisonStatus.SAME
DIFFERENT = ComparisonStatus.DIFFERENT
NOT_COMPARABLE = ComparisonStatus.NOT_COMPARABLE


def _comparison(**overrides) -> ComparisonResult:
    kwargs = dict(
        base_run_id=None,
        compare_run_id=None,
        code_status=SAME,
        dataset_status=SAME,
        environment_status=SAME,
        configuration_status=SAME,
        randomness_status=SAME,
        metrics_status=SAME,
        comparison_algorithm_version="1.0.0",
        differences=[],
    )
    kwargs.update(overrides)
    return ComparisonResult(**kwargs)


def test_subgraph_with_no_inputs_has_only_the_run_node():
    run_id = uuid.uuid4()
    graph = build_run_subgraph(run_id)
    assert len(graph.nodes) == 1
    assert graph.nodes[0].node_type == ProvenanceNodeType.EXPERIMENT_RUN
    assert graph.edges == []


def test_subgraph_used_edges_for_each_provided_category(tmp_path):
    run_id = uuid.uuid4()
    (tmp_path / "data.csv").write_text("x,y\n1,2\n3,4\n")
    dataset = capture_dataset_provenance(tmp_path / "data.csv")
    environment = capture_environment_provenance()
    configuration = capture_configuration_provenance({"model": "logreg"})

    graph = build_run_subgraph(run_id, dataset=dataset, environment=environment, configuration=configuration)

    node_types = {n.node_type for n in graph.nodes}
    assert node_types == {
        ProvenanceNodeType.EXPERIMENT_RUN,
        ProvenanceNodeType.DATASET,
        ProvenanceNodeType.ENVIRONMENT,
        ProvenanceNodeType.CONFIGURATION,
    }
    edge_types = {e.edge_type for e in graph.edges}
    assert edge_types == {
        ProvenanceEdgeType.USED_DATASET,
        ProvenanceEdgeType.USED_ENVIRONMENT,
        ProvenanceEdgeType.USED_CONFIGURATION,
    }


def test_subgraph_artifact_and_metric_nodes():
    run_id = uuid.uuid4()
    artifacts = (
        ArtifactProvenance(artifact_type=ArtifactType.MODEL, relative_path="model.joblib", content_hash="a" * 64, size_bytes=10),
        ArtifactProvenance(artifact_type=ArtifactType.LOG, relative_path="stdout.log", content_hash="b" * 64, size_bytes=20),
    )
    metrics = {"accuracy": 0.9, "loss": 0.1}

    graph = build_run_subgraph(run_id, artifacts=artifacts, metrics=metrics)

    artifact_nodes = [n for n in graph.nodes if n.node_type == ProvenanceNodeType.ARTIFACT]
    metric_nodes = [n for n in graph.nodes if n.node_type == ProvenanceNodeType.METRIC]
    assert len(artifact_nodes) == 2
    assert len(metric_nodes) == 2
    assert {n.label for n in artifact_nodes} == {"model.joblib", "stdout.log"}
    assert {n.label for n in metric_nodes} == {"accuracy", "loss"}

    produced_artifact_edges = [e for e in graph.edges if e.edge_type == ProvenanceEdgeType.PRODUCED_ARTIFACT]
    produced_metric_edges = [e for e in graph.edges if e.edge_type == ProvenanceEdgeType.PRODUCED_METRIC]
    assert len(produced_artifact_edges) == 2
    assert len(produced_metric_edges) == 2


def test_node_id_is_deterministic_across_independent_calls():
    run_id = uuid.uuid4()
    assert node_id_for(run_id, ProvenanceNodeType.CODE) == node_id_for(run_id, ProvenanceNodeType.CODE)
    assert node_id_for(run_id, ProvenanceNodeType.ARTIFACT, key="a.txt") == node_id_for(
        run_id, ProvenanceNodeType.ARTIFACT, key="a.txt"
    )
    assert node_id_for(run_id, ProvenanceNodeType.ARTIFACT, key="a.txt") != node_id_for(
        run_id, ProvenanceNodeType.ARTIFACT, key="b.txt"
    )


def test_merge_graphs_deduplicates_repeated_run_node():
    run_id = uuid.uuid4()
    graph_a = build_run_subgraph(run_id)
    graph_b = build_run_subgraph(run_id)

    merged = merge_graphs(graph_a, graph_b)

    assert len(merged.nodes) == 1


def test_add_lineage_edges_converts_derived_from_and_reproduces():
    parent, child = uuid.uuid4(), uuid.uuid4()
    graph = merge_graphs(build_run_subgraph(parent), build_run_subgraph(child))
    lineage_edges = [LineageEdge(from_run_id=parent, to_run_id=child, edge_type=LineageEdgeType.REPRODUCES)]

    graph = add_lineage_edges(graph, lineage_edges)

    assert len(graph.edges) == 1
    edge = graph.edges[0]
    assert edge.edge_type == ProvenanceEdgeType.REPRODUCES
    assert edge.from_node_id == node_id_for(parent, ProvenanceNodeType.EXPERIMENT_RUN)
    assert edge.to_node_id == node_id_for(child, ProvenanceNodeType.EXPERIMENT_RUN)


def test_add_lineage_edges_ignores_compares_with():
    parent, child = uuid.uuid4(), uuid.uuid4()
    graph = merge_graphs(build_run_subgraph(parent), build_run_subgraph(child))
    lineage_edges = [LineageEdge(from_run_id=parent, to_run_id=child, edge_type=LineageEdgeType.COMPARES_WITH)]

    graph = add_lineage_edges(graph, lineage_edges)

    assert graph.edges == []


def test_add_comparison_edges_only_for_different_in_scope_categories():
    base_run, compare_run = uuid.uuid4(), uuid.uuid4()
    graph = merge_graphs(build_run_subgraph(base_run), build_run_subgraph(compare_run))
    comparison = _comparison(dataset_status=DIFFERENT, environment_status=SAME, randomness_status=DIFFERENT)

    graph = add_comparison_edges(graph, base_run, compare_run, comparison)

    assert len(graph.edges) == 1
    edge = graph.edges[0]
    assert edge.edge_type == ProvenanceEdgeType.DIFFERS_FROM
    assert edge.from_node_id == node_id_for(base_run, ProvenanceNodeType.DATASET)
    assert edge.to_node_id == node_id_for(compare_run, ProvenanceNodeType.DATASET)


def test_add_comparison_edges_ignores_not_comparable_and_unknown():
    base_run, compare_run = uuid.uuid4(), uuid.uuid4()
    graph = merge_graphs(build_run_subgraph(base_run), build_run_subgraph(compare_run))
    comparison = _comparison(code_status=NOT_COMPARABLE, dataset_status=ComparisonStatus.UNKNOWN)

    graph = add_comparison_edges(graph, base_run, compare_run, comparison)

    assert graph.edges == []


def test_end_to_end_two_run_scenario():
    base_run, compare_run = uuid.uuid4(), uuid.uuid4()
    base_graph = build_run_subgraph(base_run, metrics={"accuracy": 0.9})
    compare_graph = build_run_subgraph(compare_run, metrics={"accuracy": 0.8})

    graph = merge_graphs(base_graph, compare_graph)
    assert len(graph.nodes) == 4  # 2 run nodes + 2 metric nodes
    assert len(graph.edges) == 2  # 2 PRODUCED_METRIC edges

    graph = add_lineage_edges(
        graph, [LineageEdge(from_run_id=base_run, to_run_id=compare_run, edge_type=LineageEdgeType.REPRODUCES)]
    )
    comparison = _comparison(dataset_status=DIFFERENT)
    graph = add_comparison_edges(graph, base_run, compare_run, comparison)

    assert len(graph.edges) == 4
    edge_types = {e.edge_type for e in graph.edges}
    assert edge_types == {ProvenanceEdgeType.PRODUCED_METRIC, ProvenanceEdgeType.REPRODUCES, ProvenanceEdgeType.DIFFERS_FROM}
