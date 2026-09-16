import uuid

from app.comparison.engine import ComparisonResult
from app.db.models.enums import ComparisonStatus, ReproducibilityClassification
from app.reproducibility.classifier import (
    REPRODUCIBILITY_ALGORITHM_VERSION,
    assemble_reproducibility_assessment,
    classify_reproducibility,
)

SAME = ComparisonStatus.SAME
DIFFERENT = ComparisonStatus.DIFFERENT
UNKNOWN = ComparisonStatus.UNKNOWN
PARTIAL = ComparisonStatus.PARTIALLY_MATCHING
NOT_COMPARABLE = ComparisonStatus.NOT_COMPARABLE


def _result(
    *,
    code=SAME,
    dataset=SAME,
    environment=SAME,
    configuration=SAME,
    randomness=SAME,
    metrics=UNKNOWN,
) -> ComparisonResult:
    return ComparisonResult(
        base_run_id=None,
        compare_run_id=None,
        code_status=code,
        dataset_status=dataset,
        environment_status=environment,
        configuration_status=configuration,
        randomness_status=randomness,
        metrics_status=metrics,
        comparison_algorithm_version="1.0.0",
        differences=[],
    )


def test_total_blackout_is_not_comparable():
    result = _result(
        code=NOT_COMPARABLE,
        dataset=NOT_COMPARABLE,
        environment=NOT_COMPARABLE,
        configuration=NOT_COMPARABLE,
        randomness=NOT_COMPARABLE,
        metrics=NOT_COMPARABLE,
    )
    outcome = classify_reproducibility(result)
    assert outcome.classification == ReproducibilityClassification.NOT_COMPARABLE
    assert outcome.rationale["rule"] == "all_categories_not_comparable"


def test_missing_metrics_with_perfect_setup_is_insufficient_evidence():
    result = _result(metrics=UNKNOWN)
    outcome = classify_reproducibility(result)
    assert outcome.classification == ReproducibilityClassification.INSUFFICIENT_EVIDENCE
    assert outcome.rationale["rule"] == "no_outcome_evidence"


def test_missing_metrics_not_comparable_is_insufficient_evidence_not_blackout():
    result = _result(metrics=NOT_COMPARABLE, dataset=DIFFERENT)
    outcome = classify_reproducibility(result)
    assert outcome.classification == ReproducibilityClassification.INSUFFICIENT_EVIDENCE


def test_outcome_mismatch_is_not_reproducible_regardless_of_setup():
    result = _result(metrics=DIFFERENT)
    outcome = classify_reproducibility(result)
    assert outcome.classification == ReproducibilityClassification.NOT_REPRODUCIBLE

    result_degraded_setup = _result(metrics=DIFFERENT, dataset=DIFFERENT, environment=UNKNOWN)
    outcome_degraded = classify_reproducibility(result_degraded_setup)
    assert outcome_degraded.classification == ReproducibilityClassification.NOT_REPRODUCIBLE


def test_exact_outcome_full_setup_is_exactly_reproducible():
    result = _result(metrics=SAME)
    outcome = classify_reproducibility(result)
    assert outcome.classification == ReproducibilityClassification.EXACTLY_REPRODUCIBLE
    assert outcome.rationale["setup"] == "FULL"


def test_exact_outcome_changed_setup_is_conditionally_reproducible():
    result = _result(metrics=SAME, environment=DIFFERENT)
    outcome = classify_reproducibility(result)
    assert outcome.classification == ReproducibilityClassification.CONDITIONALLY_REPRODUCIBLE
    assert outcome.rationale["setup"] == "CHANGED_OR_DEGRADED"


def test_exact_outcome_degraded_setup_is_conditionally_reproducible():
    result = _result(metrics=SAME, randomness=UNKNOWN)
    outcome = classify_reproducibility(result)
    assert outcome.classification == ReproducibilityClassification.CONDITIONALLY_REPRODUCIBLE


def test_tolerance_outcome_full_setup_is_reproducible_within_tolerance():
    result = _result(metrics=PARTIAL)
    outcome = classify_reproducibility(result)
    assert outcome.classification == ReproducibilityClassification.REPRODUCIBLE_WITHIN_TOLERANCE


def test_tolerance_outcome_degraded_setup_is_partially_reproducible():
    result = _result(metrics=PARTIAL, configuration=DIFFERENT)
    outcome = classify_reproducibility(result)
    assert outcome.classification == ReproducibilityClassification.PARTIALLY_REPRODUCIBLE


def test_rationale_records_all_category_statuses():
    result = _result(metrics=SAME, code=DIFFERENT)
    outcome = classify_reproducibility(result)
    assert outcome.rationale["category_statuses"] == {
        "code_status": "DIFFERENT",
        "dataset_status": "SAME",
        "environment_status": "SAME",
        "configuration_status": "SAME",
        "randomness_status": "SAME",
        "metrics_status": "SAME",
    }


def test_assemble_reproducibility_assessment_builds_unattached_orm_row():
    result = _result(metrics=SAME)
    classification_result = classify_reproducibility(result)
    comparison_id = uuid.uuid4()

    assessment = assemble_reproducibility_assessment(comparison_id, classification_result)

    assert assessment.comparison_id == comparison_id
    assert assessment.classification == ReproducibilityClassification.EXACTLY_REPRODUCIBLE
    assert assessment.rationale_json == classification_result.rationale
    assert assessment.algorithm_version == REPRODUCIBILITY_ALGORITHM_VERSION
