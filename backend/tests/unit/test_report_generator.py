import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.contributor.ranking import evidence_strength
from app.db.models.enums import (
    ComparisonStatus,
    Confidence,
    DifferenceCategory,
    DifferenceType,
    ReproducibilityClassification,
    RunStatus,
    RunType,
    Severity,
)
from app.investigation.counterfactual import CounterfactualOutcome
from app.reporting.generator import REPORT_LIMITATIONS, generate_report


def _difference(
    category=DifferenceCategory.ENVIRONMENT,
    field="dependencies.torch",
    severity=Severity.HIGH,
    confidence=Confidence.MEDIUM,
    is_potential_contributor=True,
):
    diff = MagicMock()
    diff.id = uuid.uuid4()
    diff.category = category
    diff.field = field
    diff.old_value = "2.5"
    diff.new_value = "2.6"
    diff.difference_type = DifferenceType.VALUE_CHANGED
    diff.severity = severity
    diff.confidence = confidence
    diff.evidence_source = "provenance:environment"
    diff.is_potential_contributor = is_potential_contributor
    return diff


def _comparison(differences=None, metrics_status=ComparisonStatus.NOT_COMPARABLE):
    comparison = MagicMock()
    comparison.id = uuid.uuid4()
    comparison.differences = differences or []
    comparison.code_status = ComparisonStatus.SAME
    comparison.dataset_status = ComparisonStatus.SAME
    comparison.environment_status = ComparisonStatus.DIFFERENT
    comparison.configuration_status = ComparisonStatus.SAME
    comparison.randomness_status = ComparisonStatus.UNKNOWN
    comparison.metrics_status = metrics_status
    return comparison


def _experiment():
    experiment = MagicMock()
    experiment.id = uuid.uuid4()
    experiment.name = "sklearn_tabular"
    experiment.description = "A tabular sklearn experiment"
    experiment.workload_type = "sklearn_tabular"
    return experiment


def _run(run_type=RunType.ORIGINAL):
    run = MagicMock()
    run.id = uuid.uuid4()
    run.run_type = run_type
    run.status = RunStatus.COMPLETED
    run.exit_code = 0
    run.started_at = datetime.now(timezone.utc)
    run.finished_at = datetime.now(timezone.utc)
    return run


def _reproducibility():
    assessment = MagicMock()
    assessment.classification = ReproducibilityClassification.NOT_REPRODUCIBLE
    assessment.rationale_json = {"outcome": "DIFFERENT", "setup": "DIFFERS"}
    return assessment


def _investigation_plan():
    plan = MagicMock()
    plan.id = uuid.uuid4()
    plan.changed_category = DifferenceCategory.ENVIRONMENT
    plan.changed_field = "dependencies.torch"
    plan.evidence_strength = evidence_strength(Severity.HIGH, Confidence.MEDIUM)
    return plan


def _counterfactual_plan(outcome=CounterfactualOutcome.SUPPORTS_CONTRIBUTION):
    plan = MagicMock()
    plan.id = uuid.uuid4()
    plan.restored_category = DifferenceCategory.ENVIRONMENT
    plan.restored_field = "dependencies.torch"
    plan.outcome = outcome
    return plan


def test_all_seventeen_fields_populate_on_happy_path():
    diff = _difference()
    comparison = _comparison([diff])
    original_run = _run(RunType.ORIGINAL)
    reproduction_run = _run(RunType.REPRODUCTION)

    report = generate_report(
        comparison=comparison,
        experiment=_experiment(),
        original_run=original_run,
        reproduction_run=reproduction_run,
        reproducibility=_reproducibility(),
        investigation_plan=_investigation_plan(),
        counterfactual_plan=_counterfactual_plan(),
    )

    assert report.comparison_id == comparison.id  # 1 (comparison itself)
    assert report.experiment["name"] == "sklearn_tabular"  # 1. Experiment
    assert report.original_run["id"] == original_run.id  # 2. Original run
    assert report.reproduction_run["id"] == reproduction_run.id  # 3. Reproduction run
    categories = {p.category for p in report.provenance}
    assert categories == {"code", "dataset", "environment", "configuration", "randomness", "pipeline", "artifact"}
    assert report.metric_comparison.status == ComparisonStatus.NOT_COMPARABLE.value  # 11
    assert len(report.differences) == 1  # 12
    assert report.reproducibility.available is True  # 13
    assert len(report.potential_contributors) == 1  # 14
    assert report.investigation.available is True  # 15
    assert report.counterfactual.available is True  # 15
    assert report.limitations == list(REPORT_LIMITATIONS)  # 16
    assert any(ref.startswith("comparison:") for ref in report.evidence_references)  # 17


def test_pipeline_and_artifact_provenance_are_always_not_available():
    report = generate_report(
        comparison=_comparison(),
        experiment=_experiment(),
        original_run=_run(RunType.ORIGINAL),
        reproduction_run=_run(RunType.REPRODUCTION),
        reproducibility=None,
    )
    by_category = {p.category: p for p in report.provenance}
    for category in ("pipeline", "artifact"):
        assert by_category[category].availability.value == "NOT_AVAILABLE"
        assert by_category[category].reason is not None
        assert by_category[category].status is None


def test_metrics_not_comparable_has_a_reason_others_do_not():
    not_comparable = generate_report(
        comparison=_comparison(metrics_status=ComparisonStatus.NOT_COMPARABLE),
        experiment=_experiment(),
        original_run=_run(RunType.ORIGINAL),
        reproduction_run=_run(RunType.REPRODUCTION),
        reproducibility=None,
    )
    assert not_comparable.metric_comparison.reason is not None

    comparable = generate_report(
        comparison=_comparison(metrics_status=ComparisonStatus.SAME),
        experiment=_experiment(),
        original_run=_run(RunType.ORIGINAL),
        reproduction_run=_run(RunType.REPRODUCTION),
        reproducibility=None,
    )
    assert comparable.metric_comparison.reason is None


def test_missing_reproducibility_assessment_is_not_fabricated():
    report = generate_report(
        comparison=_comparison(),
        experiment=_experiment(),
        original_run=_run(RunType.ORIGINAL),
        reproduction_run=_run(RunType.REPRODUCTION),
        reproducibility=None,
    )
    assert report.reproducibility.available is False
    assert report.reproducibility.classification is None


def test_no_potential_contributors_yields_empty_list():
    diff = _difference(is_potential_contributor=False)
    report = generate_report(
        comparison=_comparison([diff]),
        experiment=_experiment(),
        original_run=_run(RunType.ORIGINAL),
        reproduction_run=_run(RunType.REPRODUCTION),
        reproducibility=None,
    )
    assert report.potential_contributors == []


def test_potential_contributor_evidence_strength_matches_phase_14_function():
    diff = _difference(severity=Severity.CRITICAL, confidence=Confidence.HIGH)
    report = generate_report(
        comparison=_comparison([diff]),
        experiment=_experiment(),
        original_run=_run(RunType.ORIGINAL),
        reproduction_run=_run(RunType.REPRODUCTION),
        reproducibility=None,
    )
    expected = evidence_strength(Severity.CRITICAL, Confidence.HIGH).value
    assert report.potential_contributors[0].evidence_strength == expected


def test_investigation_and_counterfactual_default_to_unavailable_with_a_reason():
    report = generate_report(
        comparison=_comparison(),
        experiment=_experiment(),
        original_run=_run(RunType.ORIGINAL),
        reproduction_run=_run(RunType.REPRODUCTION),
        reproducibility=None,
    )
    assert report.investigation.available is False
    assert report.investigation.reason is not None
    assert report.counterfactual.available is False
    assert report.counterfactual.reason is not None


def test_supplied_investigation_and_counterfactual_plans_populate_from_the_plan():
    plan = _investigation_plan()
    counterfactual = _counterfactual_plan(outcome=CounterfactualOutcome.DOES_NOT_SUPPORT)
    report = generate_report(
        comparison=_comparison(),
        experiment=_experiment(),
        original_run=_run(RunType.ORIGINAL),
        reproduction_run=_run(RunType.REPRODUCTION),
        reproducibility=None,
        investigation_plan=plan,
        counterfactual_plan=counterfactual,
    )
    assert report.investigation.investigation_id == str(plan.id)
    assert report.investigation.changed_field == "dependencies.torch"
    assert report.counterfactual.counterfactual_id == str(counterfactual.id)
    assert report.counterfactual.outcome == CounterfactualOutcome.DOES_NOT_SUPPORT.value


def test_limitations_are_always_present_and_identical():
    report_a = generate_report(
        comparison=_comparison(),
        experiment=_experiment(),
        original_run=_run(RunType.ORIGINAL),
        reproduction_run=_run(RunType.REPRODUCTION),
        reproducibility=None,
    )
    report_b = generate_report(
        comparison=_comparison([_difference()]),
        experiment=_experiment(),
        original_run=_run(RunType.ORIGINAL),
        reproduction_run=_run(RunType.REPRODUCTION),
        reproducibility=_reproducibility(),
    )
    assert report_a.limitations == report_b.limitations == list(REPORT_LIMITATIONS)
    assert len(report_a.limitations) > 0


def test_evidence_references_include_difference_sources_and_identifiers():
    diff = _difference()
    comparison = _comparison([diff])
    original_run = _run(RunType.ORIGINAL)
    reproduction_run = _run(RunType.REPRODUCTION)

    report = generate_report(
        comparison=comparison,
        experiment=_experiment(),
        original_run=original_run,
        reproduction_run=reproduction_run,
        reproducibility=None,
    )

    assert diff.evidence_source in report.evidence_references
    assert f"comparison:{comparison.id}" in report.evidence_references
    assert f"run:{original_run.id}" in report.evidence_references
    assert f"run:{reproduction_run.id}" in report.evidence_references
