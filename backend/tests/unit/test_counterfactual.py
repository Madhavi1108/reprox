import uuid
from dataclasses import dataclass

from app.comparison.category_comparators.metrics import ToleranceConfig
from app.db.models.enums import Confidence, DifferenceCategory, Severity
from app.investigation.counterfactual import CounterfactualOutcome, evaluate_counterfactual_result, generate_counterfactual_plan

TOLERANCE = ToleranceConfig(default_abs_tolerance=0.5)


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


def test_generates_plan_with_reproduction_as_baseline():
    comparison_id, base_run_id, compare_run_id = _ids()
    differences = [
        _Diff(DifferenceCategory.ENVIRONMENT, "dependencies.torch", "2.5", "2.6", Severity.HIGH, Confidence.MEDIUM),
    ]

    plan = generate_counterfactual_plan(comparison_id, base_run_id, compare_run_id, differences)

    assert plan is not None
    assert plan.restored_category == DifferenceCategory.ENVIRONMENT
    assert plan.restored_field == "dependencies.torch"
    assert plan.restored_value == "2.5"  # ORIGINAL - what we'd restore it to
    assert plan.reproduction_value == "2.6"  # current (reproduction) value
    assert DifferenceCategory.ENVIRONMENT not in plan.held_at_reproduction
    assert plan.outcome is None


def test_picks_highest_evidence_strength_same_as_investigation():
    comparison_id, base_run_id, compare_run_id = _ids()
    differences = [
        _Diff(DifferenceCategory.CONFIGURATION, "model.C", "1.0", "2.0", Severity.LOW, Confidence.HIGH),
        _Diff(DifferenceCategory.ENVIRONMENT, "dependencies.torch", "2.5", "2.6", Severity.HIGH, Confidence.MEDIUM),
    ]

    plan = generate_counterfactual_plan(comparison_id, base_run_id, compare_run_id, differences)

    assert plan is not None
    assert plan.restored_category == DifferenceCategory.ENVIRONMENT


def test_returns_none_without_potential_contributors():
    comparison_id, base_run_id, compare_run_id = _ids()
    assert generate_counterfactual_plan(comparison_id, base_run_id, compare_run_id, []) is None


def test_evaluate_supports_contribution_when_moved_to_original():
    outcome = evaluate_counterfactual_result(
        original_value=94.27, reproduction_value=81.43, counterfactual_value=94.25, tolerance=TOLERANCE
    )
    assert outcome == CounterfactualOutcome.SUPPORTS_CONTRIBUTION


def test_evaluate_does_not_support_when_unchanged_from_reproduction():
    outcome = evaluate_counterfactual_result(
        original_value=94.27, reproduction_value=81.43, counterfactual_value=81.45, tolerance=TOLERANCE
    )
    assert outcome == CounterfactualOutcome.DOES_NOT_SUPPORT


def test_evaluate_inconclusive_when_moved_only_partway():
    outcome = evaluate_counterfactual_result(
        original_value=94.27, reproduction_value=81.43, counterfactual_value=88.0, tolerance=TOLERANCE
    )
    assert outcome == CounterfactualOutcome.INCONCLUSIVE


def test_evaluate_inconclusive_when_moved_further_away():
    outcome = evaluate_counterfactual_result(
        original_value=94.27, reproduction_value=81.43, counterfactual_value=70.0, tolerance=TOLERANCE
    )
    assert outcome == CounterfactualOutcome.INCONCLUSIVE


def test_evaluate_defaults_to_exact_equality_without_configured_tolerance():
    # No tolerance configured -> only an exact match counts, per Phase 13's
    # own "no arbitrary threshold" default policy.
    outcome = evaluate_counterfactual_result(original_value=94.27, reproduction_value=81.43, counterfactual_value=94.25)
    assert outcome == CounterfactualOutcome.INCONCLUSIVE


def test_evaluate_exact_match_to_original_supports():
    outcome = evaluate_counterfactual_result(original_value=100.0, reproduction_value=50.0, counterfactual_value=100.0)
    assert outcome == CounterfactualOutcome.SUPPORTS_CONTRIBUTION


def test_evaluate_exact_match_to_reproduction_does_not_support():
    outcome = evaluate_counterfactual_result(original_value=100.0, reproduction_value=50.0, counterfactual_value=50.0)
    assert outcome == CounterfactualOutcome.DOES_NOT_SUPPORT
