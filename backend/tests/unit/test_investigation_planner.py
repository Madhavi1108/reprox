import uuid
from dataclasses import dataclass

from app.db.models.enums import Confidence, DifferenceCategory, Severity
from app.investigation.planner import InvestigationStore, generate_investigation_plan


@dataclass(frozen=True)
class _Diff:
    category: DifferenceCategory
    field: str
    old_value: str | None
    new_value: str | None
    severity: Severity
    confidence: Confidence
    is_potential_contributor: bool = True


def _ids():
    return uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


def test_picks_the_single_highest_evidence_strength_factor():
    comparison_id, base_run_id, compare_run_id = _ids()
    differences = [
        _Diff(DifferenceCategory.ENVIRONMENT, "dependencies.torch", "2.5", "2.6", Severity.HIGH, Confidence.MEDIUM),
        _Diff(DifferenceCategory.ENVIRONMENT, "dependencies.cuda", "12.1", "12.4", Severity.MEDIUM, Confidence.HIGH),
        _Diff(DifferenceCategory.CONFIGURATION, "model.C", "1.0", "2.0", Severity.LOW, Confidence.HIGH),
    ]

    plan = generate_investigation_plan(comparison_id, base_run_id, compare_run_id, differences)

    assert plan is not None
    assert plan.changed_category == DifferenceCategory.ENVIRONMENT
    assert plan.changed_field == "dependencies.torch"
    assert plan.original_value == "2.5"
    assert plan.target_value == "2.6"


def test_held_constant_excludes_only_the_changed_category():
    comparison_id, base_run_id, compare_run_id = _ids()
    differences = [
        _Diff(DifferenceCategory.CODE, "files.train.py", "aaa", "bbb", Severity.HIGH, Confidence.HIGH),
    ]

    plan = generate_investigation_plan(comparison_id, base_run_id, compare_run_id, differences)

    assert plan is not None
    assert plan.changed_category == DifferenceCategory.CODE
    assert DifferenceCategory.CODE not in plan.held_constant
    assert set(plan.held_constant) == {
        DifferenceCategory.DATASET,
        DifferenceCategory.ENVIRONMENT,
        DifferenceCategory.CONFIGURATION,
        DifferenceCategory.RANDOMNESS,
    }


def test_metrics_differences_are_never_investigation_candidates():
    comparison_id, base_run_id, compare_run_id = _ids()
    differences = [
        _Diff(DifferenceCategory.METRICS, "metrics.accuracy", "0.94", "0.81", Severity.HIGH, Confidence.HIGH),
    ]

    plan = generate_investigation_plan(comparison_id, base_run_id, compare_run_id, differences)

    assert plan is None


def test_non_contributor_differences_are_ignored():
    comparison_id, base_run_id, compare_run_id = _ids()
    differences = [
        _Diff(
            DifferenceCategory.CODE,
            "files.train.py",
            "aaa",
            "bbb",
            Severity.HIGH,
            Confidence.HIGH,
            is_potential_contributor=False,
        ),
    ]

    plan = generate_investigation_plan(comparison_id, base_run_id, compare_run_id, differences)

    assert plan is None


def test_returns_none_when_no_differences_at_all():
    comparison_id, base_run_id, compare_run_id = _ids()
    assert generate_investigation_plan(comparison_id, base_run_id, compare_run_id, []) is None


def test_deterministic_tie_break_on_equal_evidence_strength():
    comparison_id, base_run_id, compare_run_id = _ids()
    # Both have identical severity/confidence -> equal evidence strength;
    # tie-break falls to category name, then field name (alphabetical).
    differences = [
        _Diff(DifferenceCategory.DATASET, "schema.y", "int64", "float64", Severity.HIGH, Confidence.HIGH),
        _Diff(DifferenceCategory.CODE, "files.b.py", "aaa", "bbb", Severity.HIGH, Confidence.HIGH),
    ]

    plan = generate_investigation_plan(comparison_id, base_run_id, compare_run_id, differences)

    assert plan is not None
    assert plan.changed_category == DifferenceCategory.CODE  # "CODE" < "DATASET" alphabetically


def test_plan_ids_and_references_are_set():
    comparison_id, base_run_id, compare_run_id = _ids()
    differences = [
        _Diff(DifferenceCategory.RANDOMNESS, "other_seeds.random_state", "None", "42", Severity.HIGH, Confidence.HIGH),
    ]

    plan = generate_investigation_plan(comparison_id, base_run_id, compare_run_id, differences)

    assert plan is not None
    assert plan.comparison_id == comparison_id
    assert plan.base_run_id == base_run_id
    assert plan.compare_run_id == compare_run_id
    assert isinstance(plan.id, uuid.UUID)
    assert plan.created_at is not None


def test_store_list_all_returns_every_created_plan():
    comparison_id, base_run_id, compare_run_id = _ids()
    differences = [
        _Diff(DifferenceCategory.CODE, "files.train.py", "aaa", "bbb", Severity.HIGH, Confidence.HIGH),
    ]
    plan = generate_investigation_plan(comparison_id, base_run_id, compare_run_id, differences)

    store = InvestigationStore()
    assert store.list_all() == []
    store.create(plan)
    assert store.list_all() == [plan]
