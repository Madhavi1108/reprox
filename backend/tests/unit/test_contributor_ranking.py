from app.comparison.difference import RawDifference
from app.comparison.engine import ComparisonResult
from app.contributor.ranking import EvidenceStrength, rank_contributors
from app.db.models.enums import (
    ComparisonStatus,
    Confidence,
    DifferenceCategory,
    DifferenceType,
    ReproducibilityClassification,
    Severity,
)

SAME = ComparisonStatus.SAME
DIFFERENT = ComparisonStatus.DIFFERENT

NOT_REPRODUCIBLE = ReproducibilityClassification.NOT_REPRODUCIBLE
PARTIALLY_REPRODUCIBLE = ReproducibilityClassification.PARTIALLY_REPRODUCIBLE
EXACTLY_REPRODUCIBLE = ReproducibilityClassification.EXACTLY_REPRODUCIBLE
INSUFFICIENT_EVIDENCE = ReproducibilityClassification.INSUFFICIENT_EVIDENCE
NOT_COMPARABLE = ReproducibilityClassification.NOT_COMPARABLE


def _diff(
    category=DifferenceCategory.ENVIRONMENT,
    field="dependencies.torch",
    severity=Severity.MEDIUM,
    confidence=Confidence.MEDIUM,
) -> RawDifference:
    return RawDifference(
        category=category,
        field=field,
        old_value="2.5",
        new_value="2.6",
        difference_type=DifferenceType.VALUE_CHANGED,
        evidence_source="environment.dependencies",
        severity=severity,
        confidence=confidence,
    )


def _result(differences: list[RawDifference], metrics=DIFFERENT) -> ComparisonResult:
    return ComparisonResult(
        base_run_id=None,
        compare_run_id=None,
        code_status=SAME,
        dataset_status=SAME,
        environment_status=DIFFERENT,
        configuration_status=SAME,
        randomness_status=SAME,
        metrics_status=metrics,
        comparison_algorithm_version="1.0.0",
        differences=differences,
    )


def test_not_triggered_classification_marks_nothing_as_contributor():
    result = _result([_diff()])
    outcome = rank_contributors(result, EXACTLY_REPRODUCIBLE)
    assert outcome.triggered is False
    assert len(outcome.ranked_differences) == 1
    ranked = outcome.ranked_differences[0]
    assert ranked.is_potential_contributor is False
    assert ranked.rank is None
    assert ranked.evidence_strength is None


def test_insufficient_evidence_and_not_comparable_are_not_triggered():
    result = _result([_diff()])
    for classification in (INSUFFICIENT_EVIDENCE, NOT_COMPARABLE):
        outcome = rank_contributors(result, classification)
        assert outcome.triggered is False


def test_not_reproducible_triggers_ranking():
    result = _result([_diff()])
    outcome = rank_contributors(result, NOT_REPRODUCIBLE)
    assert outcome.triggered is True
    assert outcome.ranked_differences[0].is_potential_contributor is True
    assert outcome.ranked_differences[0].rank == 1


def test_partially_reproducible_triggers_ranking():
    result = _result([_diff()])
    outcome = rank_contributors(result, PARTIALLY_REPRODUCIBLE)
    assert outcome.triggered is True
    assert outcome.ranked_differences[0].is_potential_contributor is True


def test_metrics_category_difference_is_never_a_contributor():
    metrics_diff = _diff(category=DifferenceCategory.METRICS, field="metrics.accuracy")
    env_diff = _diff(category=DifferenceCategory.ENVIRONMENT, field="dependencies.torch")
    result = _result([metrics_diff, env_diff])

    outcome = rank_contributors(result, NOT_REPRODUCIBLE)

    metrics_ranked, env_ranked = outcome.ranked_differences
    assert metrics_ranked.is_potential_contributor is False
    assert metrics_ranked.rank is None
    assert env_ranked.is_potential_contributor is True
    assert env_ranked.rank == 1


def test_evidence_strength_lattice_matches_spec_example():
    # PyTorch version: HIGH severity, MEDIUM confidence -> HIGH evidence strength.
    pytorch = _diff(field="dependencies.torch", severity=Severity.HIGH, confidence=Confidence.MEDIUM)
    # CUDA version: MEDIUM severity, HIGH confidence -> MODERATE evidence strength.
    cuda = _diff(field="dependencies.cuda", severity=Severity.MEDIUM, confidence=Confidence.HIGH)
    # GPU driver: LOW severity -> LOW evidence strength regardless of confidence.
    gpu_driver = _diff(field="gpu_model", severity=Severity.LOW, confidence=Confidence.HIGH)

    result = _result([pytorch, cuda, gpu_driver])
    outcome = rank_contributors(result, NOT_REPRODUCIBLE)

    by_field = {r.difference.field: r for r in outcome.ranked_differences}
    assert by_field["dependencies.torch"].evidence_strength == EvidenceStrength.HIGH
    assert by_field["dependencies.cuda"].evidence_strength == EvidenceStrength.MODERATE
    assert by_field["gpu_model"].evidence_strength == EvidenceStrength.LOW

    assert by_field["dependencies.torch"].rank == 1
    assert by_field["dependencies.cuda"].rank == 2
    assert by_field["gpu_model"].rank == 3


def test_full_severity_confidence_lattice():
    expected = {
        (Severity.LOW, Confidence.LOW): EvidenceStrength.LOW,
        (Severity.LOW, Confidence.MEDIUM): EvidenceStrength.LOW,
        (Severity.LOW, Confidence.HIGH): EvidenceStrength.LOW,
        (Severity.MEDIUM, Confidence.LOW): EvidenceStrength.MODERATE,
        (Severity.MEDIUM, Confidence.MEDIUM): EvidenceStrength.MODERATE,
        (Severity.MEDIUM, Confidence.HIGH): EvidenceStrength.MODERATE,
        (Severity.HIGH, Confidence.LOW): EvidenceStrength.MODERATE,
        (Severity.HIGH, Confidence.MEDIUM): EvidenceStrength.HIGH,
        (Severity.HIGH, Confidence.HIGH): EvidenceStrength.HIGH,
        (Severity.CRITICAL, Confidence.LOW): EvidenceStrength.MODERATE,
        (Severity.CRITICAL, Confidence.MEDIUM): EvidenceStrength.HIGH,
        (Severity.CRITICAL, Confidence.HIGH): EvidenceStrength.HIGH,
    }

    for (severity, confidence), strength in expected.items():
        diff = _diff(field=f"case.{severity.value}.{confidence.value}", severity=severity, confidence=confidence)
        outcome = rank_contributors(_result([diff]), NOT_REPRODUCIBLE)
        assert outcome.ranked_differences[0].evidence_strength == strength, (severity, confidence)


def test_tie_break_is_deterministic_by_category_then_field():
    a = _diff(category=DifferenceCategory.CONFIGURATION, field="model.C", severity=Severity.MEDIUM, confidence=Confidence.MEDIUM)
    b = _diff(category=DifferenceCategory.CODE, field="files.train.py", severity=Severity.MEDIUM, confidence=Confidence.MEDIUM)
    result = _result([a, b])

    outcome = rank_contributors(result, NOT_REPRODUCIBLE)

    by_field = {r.difference.field: r.rank for r in outcome.ranked_differences}
    assert by_field["files.train.py"] == 1
    assert by_field["model.C"] == 2


def test_ranks_are_contiguous_among_eligible_differences_only():
    metrics_diff = _diff(category=DifferenceCategory.METRICS, field="metrics.accuracy")
    a = _diff(category=DifferenceCategory.CODE, field="files.a.py", severity=Severity.HIGH, confidence=Confidence.HIGH)
    b = _diff(category=DifferenceCategory.DATASET, field="schema.x", severity=Severity.LOW, confidence=Confidence.LOW)

    outcome = rank_contributors(_result([metrics_diff, a, b]), NOT_REPRODUCIBLE)

    ranks = sorted(r.rank for r in outcome.ranked_differences if r.rank is not None)
    assert ranks == [1, 2]
