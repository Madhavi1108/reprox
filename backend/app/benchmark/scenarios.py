"""Benchmarking (Phase 28, spec sections 63-64).

"63. RESEARCH BENCHMARK - Create a controlled benchmark dataset. Include
experiments with: same/different code, same/different dataset,
same/different environment, same/different configuration, same/different
seed, dependency drift, dataset drift, schema drift, data split drift,
hardware drift, multiple simultaneous changes, missing provenance,
incomplete provenance, nondeterministic execution. The benchmark must be
synthetic or openly reproducible. Do not fabricate benchmark results."

"64. CONTROLLED EXPERIMENT SUITE - Build an experiment suite specifically
for evaluating REPROX. Minimum: Experiment A (identical environment) ->
Reproducible; Experiment B (dataset modified) -> Dataset difference
detected; ...; Experiment H (provenance intentionally incomplete) ->
Insufficient evidence."

Per the tracker's own pre-recorded scoping decision (docs/PHASE_TRACKER.md
row 28), this phase covers 4 of the spec's 8 named experiments rather than
the full suite or the full 19-dimension synthetic dataset generator:

- identical rerun       (spec Experiment A)
- dataset-only change   (spec Experiment B)
- config-only change    (spec Experiment D)
- missing provenance    (spec Experiment H)

Experiments C (dependency drift), E (randomness), F (code), and G
(multiple simultaneous changes) are the same pattern, just not built yet -
see docs/BENCHMARKING.md.

"Do not fabricate benchmark results" is satisfied structurally: every
scenario below builds real synthetic fixtures on disk using Phases 4-8's
actual capture functions (the same pattern
`tests/unit/test_comparison_engine.py`'s `_capture_all()` helper already
uses), runs them through Phase 11's real `compare_experiments()` and
Phase 12's real `classify_reproducibility()`, and reports whatever those
functions actually compute - `actual` is never hand-written.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.comparison.engine import ComparisonResult, compare_experiments
from app.db.models.enums import DifferenceCategory, ReproducibilityClassification
from app.provenance.code import capture_code_provenance
from app.provenance.configuration import capture_configuration_provenance
from app.provenance.dataset import capture_dataset_provenance
from app.provenance.environment import capture_environment_provenance
from app.provenance.randomness import capture_randomness_provenance
from app.reproducibility.classifier import classify_reproducibility


@dataclass(frozen=True)
class BenchmarkScenarioResult:
    name: str
    description: str
    expected: str
    actual: str
    passed: bool
    comparison: ComparisonResult


def _capture_side(root: Path, csv_text: str, config: dict, seed: int, include_dataset: bool, include_environment: bool):
    code_dir = root / "code"
    code_dir.mkdir(parents=True)
    (code_dir / "train.py").write_text("x = 1\n")

    dataset = None
    if include_dataset:
        csv_path = root / "data.csv"
        csv_path.write_text(csv_text)
        dataset = capture_dataset_provenance(csv_path)

    return dict(
        code=capture_code_provenance(code_dir),
        dataset=dataset,
        environment=capture_environment_provenance() if include_environment else None,
        configuration=capture_configuration_provenance(config),
        randomness=capture_randomness_provenance(python_seed=seed, numpy_seed=seed),
    )


def _compare(base: dict, compare: dict, **kwargs) -> ComparisonResult:
    return compare_experiments(
        base_code=base["code"],
        compare_code=compare["code"],
        base_dataset=base["dataset"],
        compare_dataset=compare["dataset"],
        base_environment=base["environment"],
        compare_environment=compare["environment"],
        base_configuration=base["configuration"],
        compare_configuration=compare["configuration"],
        base_randomness=base["randomness"],
        compare_randomness=compare["randomness"],
        **kwargs,
    )


def run_identical_rerun_scenario(root: Path) -> BenchmarkScenarioResult:
    """Spec Experiment A: identical environment. Expected: Reproducible."""
    csv = "x,y\n1,2\n3,4\n"
    config = {"model": "logreg", "C": 1.0}
    base = _capture_side(root / "base", csv, config, seed=42, include_dataset=True, include_environment=True)
    compare = _capture_side(root / "compare", csv, config, seed=42, include_dataset=True, include_environment=True)

    metrics = {"accuracy": 0.9427}
    result = _compare(base, compare, base_metrics=metrics, compare_metrics=dict(metrics))
    classification = classify_reproducibility(result).classification

    expected = ReproducibilityClassification.EXACTLY_REPRODUCIBLE
    return BenchmarkScenarioResult(
        name="identical_rerun",
        description="Spec Experiment A: identical code/dataset/environment/configuration/seed/metrics.",
        expected=expected.value,
        actual=classification.value,
        passed=classification == expected,
        comparison=result,
    )


def run_dataset_change_scenario(root: Path) -> BenchmarkScenarioResult:
    """Spec Experiment B: dataset modified. Expected: Dataset difference detected."""
    config = {"model": "logreg", "C": 1.0}
    base = _capture_side(
        root / "base", "x,y\n1,2\n3,4\n", config, seed=42, include_dataset=True, include_environment=True
    )
    compare = _capture_side(
        root / "compare", "x,y\n1,2\n3,5\n", config, seed=42, include_dataset=True, include_environment=True
    )

    result = _compare(base, compare)
    dataset_only = (
        result.dataset_status.value == "DIFFERENT"
        and result.code_status.value == "SAME"
        and result.environment_status.value == "SAME"
        and result.configuration_status.value == "SAME"
        and result.randomness_status.value == "SAME"
        and all(d.category == DifferenceCategory.DATASET for d in result.differences)
    )

    return BenchmarkScenarioResult(
        name="dataset_only_change",
        description="Spec Experiment B: only the dataset content differs.",
        expected="DATASET difference detected, all other categories SAME",
        actual=f"dataset_status={result.dataset_status.value}, other_categories_same={dataset_only}",
        passed=dataset_only,
        comparison=result,
    )


def run_configuration_change_scenario(root: Path) -> BenchmarkScenarioResult:
    """Spec Experiment D: learning rate changed. Expected: Configuration difference detected."""
    csv = "x,y\n1,2\n3,4\n"
    base = _capture_side(
        root / "base", csv, {"model": "logreg", "C": 1.0}, seed=42, include_dataset=True, include_environment=True
    )
    compare = _capture_side(
        root / "compare", csv, {"model": "logreg", "C": 2.0}, seed=42, include_dataset=True, include_environment=True
    )

    result = _compare(base, compare)
    configuration_only = (
        result.configuration_status.value == "DIFFERENT"
        and result.code_status.value == "SAME"
        and result.dataset_status.value == "SAME"
        and result.environment_status.value == "SAME"
        and result.randomness_status.value == "SAME"
        and all(d.category == DifferenceCategory.CONFIGURATION for d in result.differences)
    )

    return BenchmarkScenarioResult(
        name="configuration_only_change",
        description="Spec Experiment D: only the configuration differs.",
        expected="CONFIGURATION difference detected, all other categories SAME",
        actual=f"configuration_status={result.configuration_status.value}, other_categories_same={configuration_only}",
        passed=configuration_only,
        comparison=result,
    )


def run_missing_provenance_scenario(root: Path) -> BenchmarkScenarioResult:
    """Spec Experiment H: provenance intentionally incomplete. Expected: Insufficient evidence."""
    csv = "x,y\n1,2\n3,4\n"
    config = {"model": "logreg", "C": 1.0}
    base = _capture_side(root / "base", csv, config, seed=42, include_dataset=True, include_environment=True)
    compare = _capture_side(
        root / "compare", csv, config, seed=42, include_dataset=False, include_environment=False
    )

    result = _compare(base, compare)
    classification = classify_reproducibility(result).classification

    expected = ReproducibilityClassification.INSUFFICIENT_EVIDENCE
    return BenchmarkScenarioResult(
        name="missing_provenance",
        description="Spec Experiment H: dataset and environment provenance missing on the reproduction side.",
        expected=expected.value,
        actual=classification.value,
        passed=classification == expected,
        comparison=result,
    )


def run_all_scenarios(root: Path) -> list[BenchmarkScenarioResult]:
    return [
        run_identical_rerun_scenario(root / "identical_rerun"),
        run_dataset_change_scenario(root / "dataset_only_change"),
        run_configuration_change_scenario(root / "configuration_only_change"),
        run_missing_provenance_scenario(root / "missing_provenance"),
    ]
