import uuid

from app.db.models.enums import RunType
from app.lineage.graph import (
    ComparisonLink,
    LineageEdgeType,
    RunNode,
    ancestors,
    build_lineage_graph,
    descendants,
)

ORIGINAL = RunType.ORIGINAL
REPRODUCTION = RunType.REPRODUCTION
INVESTIGATION = RunType.INVESTIGATION


def _uuids(n: int) -> list[uuid.UUID]:
    return [uuid.uuid4() for _ in range(n)]


def _spec_example_tree():
    # Experiment 001
    # ├── Experiment 002
    # ├── Experiment 003
    # │   └── Experiment 007
    # └── Experiment 004
    exp001, exp002, exp003, exp004, exp007 = _uuids(5)
    runs = [
        RunNode(run_id=exp001, parent_run_id=None, run_type=ORIGINAL),
        RunNode(run_id=exp002, parent_run_id=exp001, run_type=ORIGINAL),
        RunNode(run_id=exp003, parent_run_id=exp001, run_type=ORIGINAL),
        RunNode(run_id=exp004, parent_run_id=exp001, run_type=ORIGINAL),
        RunNode(run_id=exp007, parent_run_id=exp003, run_type=ORIGINAL),
    ]
    return runs, dict(exp001=exp001, exp002=exp002, exp003=exp003, exp004=exp004, exp007=exp007)


def test_spec_worked_tree_example_structure():
    runs, ids = _spec_example_tree()
    graph = build_lineage_graph(runs)

    assert len(graph.nodes) == 5
    assert len(graph.edges) == 4  # every run except the root has a parent edge

    edge_pairs = {(e.from_run_id, e.to_run_id) for e in graph.edges}
    assert (ids["exp001"], ids["exp002"]) in edge_pairs
    assert (ids["exp001"], ids["exp003"]) in edge_pairs
    assert (ids["exp001"], ids["exp004"]) in edge_pairs
    assert (ids["exp003"], ids["exp007"]) in edge_pairs


def test_spec_worked_tree_example_ancestors_and_descendants():
    runs, ids = _spec_example_tree()
    graph = build_lineage_graph(runs)

    assert ancestors(graph, ids["exp007"]) == [ids["exp003"], ids["exp001"]]
    assert ancestors(graph, ids["exp001"]) == []

    descendants_of_001 = set(descendants(graph, ids["exp001"]))
    assert descendants_of_001 == {ids["exp002"], ids["exp003"], ids["exp004"], ids["exp007"]}
    assert descendants(graph, ids["exp004"]) == []


def test_reproduction_run_type_yields_reproduces_edge():
    parent, child = _uuids(2)
    runs = [
        RunNode(run_id=parent, parent_run_id=None, run_type=ORIGINAL),
        RunNode(run_id=child, parent_run_id=parent, run_type=REPRODUCTION),
    ]
    graph = build_lineage_graph(runs)
    assert graph.edges[0].edge_type == LineageEdgeType.REPRODUCES


def test_original_and_investigation_run_types_yield_derived_from_edge():
    for run_type in (ORIGINAL, INVESTIGATION):
        parent, child = _uuids(2)
        runs = [
            RunNode(run_id=parent, parent_run_id=None, run_type=ORIGINAL),
            RunNode(run_id=child, parent_run_id=parent, run_type=run_type),
        ]
        graph = build_lineage_graph(runs)
        assert graph.edges[0].edge_type == LineageEdgeType.DERIVED_FROM


def test_comparison_link_yields_compares_with_edge_independent_of_parentage():
    run_a, run_b = _uuids(2)
    runs = [
        RunNode(run_id=run_a, parent_run_id=None, run_type=ORIGINAL),
        RunNode(run_id=run_b, parent_run_id=None, run_type=ORIGINAL),
    ]
    comparisons = [ComparisonLink(base_run_id=run_a, compare_run_id=run_b)]

    graph = build_lineage_graph(runs, comparisons)

    assert len(graph.edges) == 1
    assert graph.edges[0].edge_type == LineageEdgeType.COMPARES_WITH
    assert graph.edges[0].from_run_id == run_a
    assert graph.edges[0].to_run_id == run_b

    # COMPARES_WITH is not a parent/child relationship - excluded from traversal.
    assert ancestors(graph, run_b) == []
    assert descendants(graph, run_a) == []


def test_root_run_has_no_ancestors():
    root = uuid.uuid4()
    runs = [RunNode(run_id=root, parent_run_id=None, run_type=ORIGINAL)]
    graph = build_lineage_graph(runs)
    assert ancestors(graph, root) == []
    assert descendants(graph, root) == []


def test_cycle_guard_terminates_on_malformed_input():
    a, b = _uuids(2)
    # Malformed: a's parent is b, and b's parent is a (a real cycle should never
    # occur given the schema's tree semantics, but the traversal must not hang).
    runs = [
        RunNode(run_id=a, parent_run_id=b, run_type=ORIGINAL),
        RunNode(run_id=b, parent_run_id=a, run_type=ORIGINAL),
    ]
    graph = build_lineage_graph(runs)

    result = ancestors(graph, a)
    assert result == [b]  # stops once it would revisit `a`

    result = descendants(graph, a)
    assert result == [b]
