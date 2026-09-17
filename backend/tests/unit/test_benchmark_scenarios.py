from pathlib import Path

from app.benchmark.scenarios import (
    run_all_scenarios,
    run_configuration_change_scenario,
    run_dataset_change_scenario,
    run_identical_rerun_scenario,
    run_missing_provenance_scenario,
)
from app.db.models.enums import ComparisonStatus, DifferenceCategory, ReproducibilityClassification


def test_identical_rerun_is_exactly_reproducible(tmp_path: Path):
    result = run_identical_rerun_scenario(tmp_path)
    assert result.passed is True
    assert result.actual == ReproducibilityClassification.EXACTLY_REPRODUCIBLE.value


def test_dataset_only_change_detected_and_isolated(tmp_path: Path):
    result = run_dataset_change_scenario(tmp_path)
    assert result.passed is True
    assert result.comparison.dataset_status == ComparisonStatus.DIFFERENT
    assert result.comparison.code_status == ComparisonStatus.SAME
    assert result.comparison.environment_status == ComparisonStatus.SAME
    assert result.comparison.configuration_status == ComparisonStatus.SAME
    assert result.comparison.randomness_status == ComparisonStatus.SAME
    assert result.comparison.differences
    assert all(d.category == DifferenceCategory.DATASET for d in result.comparison.differences)


def test_configuration_only_change_detected_and_isolated(tmp_path: Path):
    result = run_configuration_change_scenario(tmp_path)
    assert result.passed is True
    assert result.comparison.configuration_status == ComparisonStatus.DIFFERENT
    assert result.comparison.code_status == ComparisonStatus.SAME
    assert result.comparison.dataset_status == ComparisonStatus.SAME
    assert result.comparison.environment_status == ComparisonStatus.SAME
    assert result.comparison.randomness_status == ComparisonStatus.SAME
    assert result.comparison.differences
    assert all(d.category == DifferenceCategory.CONFIGURATION for d in result.comparison.differences)


def test_missing_provenance_is_insufficient_evidence(tmp_path: Path):
    result = run_missing_provenance_scenario(tmp_path)
    assert result.passed is True
    assert result.actual == ReproducibilityClassification.INSUFFICIENT_EVIDENCE.value
    assert result.comparison.dataset_status == ComparisonStatus.UNKNOWN
    assert result.comparison.environment_status == ComparisonStatus.UNKNOWN


def test_run_all_scenarios_returns_four_passing_results(tmp_path: Path):
    results = run_all_scenarios(tmp_path)
    assert len(results) == 4
    assert all(r.passed for r in results)
    assert {r.name for r in results} == {
        "identical_rerun",
        "dataset_only_change",
        "configuration_only_change",
        "missing_provenance",
    }
