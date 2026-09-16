"""Experiment comparison orchestrator (Phase 11, spec section 22-23).

Runs each of the 6 per-category comparators and assembles their results
into a single `ComparisonResult`, then - separately - into unattached
`ExperimentComparison`/`Difference` ORM instances. No DB session is
touched here (no `session.add`/`commit`): wiring persistence to an actual
request is Phase 19's job (FastAPI), not this phase's.

`metrics_status` comes from the Phase 13 tolerance comparator
(`category_comparators/metrics.py`). No `ExperimentRun` column captures
metric values yet, so `base_metrics`/`compare_metrics` default to `None`
- callers without real metrics get `NOT_COMPARABLE`, same as any other
category with no evidence on either side, until a later phase wires in
real captured metrics.

`Difference.is_potential_contributor` is always `False` here; ranking
which differences actually explain a reproducibility failure is Phase 14
(REDUCED SCOPE, deferred) - `False` reads as "not yet assessed," not "not
a contributor."
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from app.comparison.category_comparators.code import compare_code as _compare_code
from app.comparison.category_comparators.configuration import compare_configuration as _compare_configuration
from app.comparison.category_comparators.dataset import compare_dataset as _compare_dataset
from app.comparison.category_comparators.environment import compare_environment as _compare_environment
from app.comparison.category_comparators.metrics import ToleranceConfig, compare_metrics as _compare_metrics
from app.comparison.category_comparators.randomness import compare_randomness as _compare_randomness
from app.comparison.difference import RawDifference
from app.db.models.comparison import Difference, ExperimentComparison
from app.db.models.enums import ComparisonStatus
from app.provenance.code import CodeProvenance
from app.provenance.configuration import ConfigurationProvenance
from app.provenance.dataset import DatasetProvenance
from app.provenance.environment import EnvironmentProvenance
from app.provenance.randomness import RandomnessProvenance

COMPARISON_ALGORITHM_VERSION = "1.0.0"


@dataclass(frozen=True)
class ComparisonResult:
    base_run_id: uuid.UUID | None
    compare_run_id: uuid.UUID | None
    code_status: ComparisonStatus
    dataset_status: ComparisonStatus
    environment_status: ComparisonStatus
    configuration_status: ComparisonStatus
    randomness_status: ComparisonStatus
    metrics_status: ComparisonStatus
    comparison_algorithm_version: str
    differences: list[RawDifference] = field(default_factory=list)


def compare_experiments(
    *,
    base_code: CodeProvenance | None,
    compare_code: CodeProvenance | None,
    base_dataset: DatasetProvenance | None,
    compare_dataset: DatasetProvenance | None,
    base_environment: EnvironmentProvenance | None,
    compare_environment: EnvironmentProvenance | None,
    base_configuration: ConfigurationProvenance | None,
    compare_configuration: ConfigurationProvenance | None,
    base_randomness: RandomnessProvenance | None,
    compare_randomness: RandomnessProvenance | None,
    base_metrics: dict[str, float] | None = None,
    compare_metrics: dict[str, float] | None = None,
    metrics_tolerance: ToleranceConfig = ToleranceConfig(),
    base_run_id: uuid.UUID | None = None,
    compare_run_id: uuid.UUID | None = None,
    comparison_algorithm_version: str = COMPARISON_ALGORITHM_VERSION,
) -> ComparisonResult:
    code_result = _compare_code(base_code, compare_code)
    dataset_result = _compare_dataset(base_dataset, compare_dataset)
    environment_result = _compare_environment(base_environment, compare_environment)
    configuration_result = _compare_configuration(base_configuration, compare_configuration)
    randomness_result = _compare_randomness(base_randomness, compare_randomness)
    metrics_result = _compare_metrics(base_metrics, compare_metrics, metrics_tolerance)

    differences = (
        code_result.differences
        + dataset_result.differences
        + environment_result.differences
        + configuration_result.differences
        + randomness_result.differences
        + metrics_result.differences
    )

    return ComparisonResult(
        base_run_id=base_run_id,
        compare_run_id=compare_run_id,
        code_status=code_result.status,
        dataset_status=dataset_result.status,
        environment_status=environment_result.status,
        configuration_status=configuration_result.status,
        randomness_status=randomness_result.status,
        metrics_status=metrics_result.status,
        comparison_algorithm_version=comparison_algorithm_version,
        differences=differences,
    )


def assemble_comparison(result: ComparisonResult) -> tuple[ExperimentComparison, list[Difference]]:
    """Build unattached ORM instances from a `ComparisonResult`. The caller
    is responsible for `session.add()`/`commit()` once a DB session exists
    (Phase 19). `comparison.id` is generated eagerly here (rather than
    relying on the column's `default=uuid.uuid4`, which only runs at flush
    time) so the `Difference` rows below can reference it as their FK
    before anything is ever flushed."""
    comparison = ExperimentComparison(
        id=uuid.uuid4(),
        base_run_id=result.base_run_id,
        compare_run_id=result.compare_run_id,
        code_status=result.code_status,
        dataset_status=result.dataset_status,
        environment_status=result.environment_status,
        configuration_status=result.configuration_status,
        randomness_status=result.randomness_status,
        metrics_status=result.metrics_status,
        comparison_algorithm_version=result.comparison_algorithm_version,
    )

    differences = [
        Difference(
            id=uuid.uuid4(),
            comparison_id=comparison.id,
            category=raw.category,
            field=raw.field,
            old_value=raw.old_value,
            new_value=raw.new_value,
            difference_type=raw.difference_type,
            evidence_source=raw.evidence_source,
            severity=raw.severity,
            confidence=raw.confidence,
            is_potential_contributor=False,
        )
        for raw in result.differences
    ]

    return comparison, differences
