"""Reproducibility report generation (Phase 26, spec section 61).

"Generate reproducibility reports. Include: 1. Experiment 2. Original run
3. Reproduction run 4. Code provenance 5. Dataset provenance 6. Pipeline
provenance 7. Environment provenance 8. Configuration provenance
9. Randomness provenance 10. Artifact provenance 11. Metric comparison
12. Detected differences 13. Reproducibility classification
14. Potential contributors 15. Investigation results 16. Limitations
17. Evidence references. Never fabricate findings."

This module computes nothing new - it assembles a single report view over
data every prior phase already produced, reusing their pure functions
directly (Phase 14's `evidence_strength`) rather than re-deriving
anything. "Never fabricate findings" cuts both ways here: known gaps are
reported explicitly via `reason` fields and the always-populated
`limitations` list, never silently dropped.

Known gaps, each documented at the point they're surfaced below:
- No phase persists a full per-run provenance snapshot (Phase 19: only
  inline provenance-at-compare-time exists), so code/dataset/environment/
  configuration/randomness provenance (items 4/5/7/8/9) are reported at
  comparison-status granularity, not as standalone snapshots.
- Pipeline and artifact provenance (items 6/10) have no comparator at all
  - `DifferenceCategory` has no PIPELINE or ARTIFACT value (Phase 21's
  scoping note) - so these are always reported `NOT_AVAILABLE`.
- Metric comparison (item 11) is usually `NOT_COMPARABLE` - no
  `ExperimentRun` metrics-storage column exists yet (Phase 13).
- Investigation/counterfactual results (item 15) live only in Phase
  22/23's in-process stores, keyed by their own id with no index by
  comparison_id. This module cannot look them up itself, so it accepts
  an already-resolved `InvestigationPlan`/`CounterfactualPlan` as an
  optional parameter - the caller (the router) resolves the id against
  the store, mirroring Phase 24's `explain_comparison(comparison,
  reproducibility, provider)` dependency-injection style.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from app.contributor.ranking import evidence_strength
from app.db.models.comparison import Difference, ExperimentComparison, ReproducibilityAssessment
from app.db.models.core import Experiment, ExperimentRun
from app.db.models.enums import ComparisonStatus
from app.investigation.counterfactual import CounterfactualPlan
from app.investigation.planner import InvestigationPlan

REPORT_GENERATOR_VERSION = "1.0.0"

_NOT_COMPARABLE_METRIC_STATUSES = frozenset({ComparisonStatus.NOT_COMPARABLE, ComparisonStatus.UNKNOWN})

REPORT_LIMITATIONS: tuple[str, ...] = (
    "Code, dataset, environment, configuration, and randomness provenance "
    "reflect comparison status only - no full per-run provenance snapshot "
    "is persisted yet (Phase 19 scoping note).",
    "Pipeline and artifact provenance are not computed - no comparator "
    "exists for either category (Phase 21 scoping note).",
    "Metric comparison is frequently NOT_COMPARABLE - no ExperimentRun "
    "metrics-storage column exists yet (Phase 13 scoping note).",
    "Investigation and counterfactual results, when present, describe a "
    "generated plan or a user-supplied counterfactual measurement "
    "evaluation - not an executed controlled rerun (Phase 22/23 scoping "
    "note).",
    "This report was generated without a live, reachable Postgres "
    "database verifying persisted data end-to-end in this dev "
    "environment.",
)

_PIPELINE_ARTIFACT_REASON = (
    "No comparator exists for this category - DifferenceCategory has no "
    "corresponding value (Phase 21 scoping note)."
)

_METRIC_NOT_COMPARABLE_REASON = (
    "No ExperimentRun metrics-storage column exists yet, so metrics "
    "usually cannot be compared (Phase 13 scoping note)."
)


class ProvenanceAvailability(str, Enum):
    COMPARED = "COMPARED"
    NOT_AVAILABLE = "NOT_AVAILABLE"


@dataclass(frozen=True)
class CategoryProvenance:
    category: str
    availability: ProvenanceAvailability
    status: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class MetricComparisonSummary:
    status: str
    reason: str | None = None


@dataclass(frozen=True)
class DifferenceEntry:
    id: str
    category: str
    field: str
    old_value: str | None
    new_value: str | None
    difference_type: str
    severity: str
    confidence: str
    evidence_source: str
    is_potential_contributor: bool


@dataclass(frozen=True)
class ContributorEntry:
    difference_id: str
    category: str
    field: str
    evidence_strength: str


@dataclass(frozen=True)
class ReproducibilitySummary:
    available: bool
    classification: str | None = None
    rationale: dict | None = None


@dataclass(frozen=True)
class InvestigationSummary:
    available: bool
    investigation_id: str | None = None
    changed_category: str | None = None
    changed_field: str | None = None
    evidence_strength: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class CounterfactualSummary:
    available: bool
    counterfactual_id: str | None = None
    restored_category: str | None = None
    restored_field: str | None = None
    outcome: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class ReproducibilityReport:
    report_version: str
    comparison_id: uuid.UUID
    experiment: dict
    original_run: dict
    reproduction_run: dict
    provenance: list[CategoryProvenance]
    metric_comparison: MetricComparisonSummary
    differences: list[DifferenceEntry]
    reproducibility: ReproducibilitySummary
    potential_contributors: list[ContributorEntry]
    investigation: InvestigationSummary
    counterfactual: CounterfactualSummary
    limitations: list[str] = field(default_factory=lambda: list(REPORT_LIMITATIONS))
    evidence_references: list[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def _run_summary(run: ExperimentRun) -> dict:
    return {
        "id": run.id,
        "run_type": run.run_type.value,
        "status": run.status.value,
        "exit_code": run.exit_code,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
    }


def _experiment_summary(experiment: Experiment) -> dict:
    return {
        "id": experiment.id,
        "name": experiment.name,
        "description": experiment.description,
        "workload_type": experiment.workload_type,
    }


def _category_provenance(comparison: ExperimentComparison) -> list[CategoryProvenance]:
    compared = [
        CategoryProvenance(
            category="code",
            availability=ProvenanceAvailability.COMPARED,
            status=comparison.code_status.value,
        ),
        CategoryProvenance(
            category="dataset",
            availability=ProvenanceAvailability.COMPARED,
            status=comparison.dataset_status.value,
        ),
        CategoryProvenance(
            category="environment",
            availability=ProvenanceAvailability.COMPARED,
            status=comparison.environment_status.value,
        ),
        CategoryProvenance(
            category="configuration",
            availability=ProvenanceAvailability.COMPARED,
            status=comparison.configuration_status.value,
        ),
        CategoryProvenance(
            category="randomness",
            availability=ProvenanceAvailability.COMPARED,
            status=comparison.randomness_status.value,
        ),
    ]
    not_available = [
        CategoryProvenance(
            category="pipeline",
            availability=ProvenanceAvailability.NOT_AVAILABLE,
            reason=_PIPELINE_ARTIFACT_REASON,
        ),
        CategoryProvenance(
            category="artifact",
            availability=ProvenanceAvailability.NOT_AVAILABLE,
            reason=_PIPELINE_ARTIFACT_REASON,
        ),
    ]
    return compared + not_available


def _metric_comparison(comparison: ExperimentComparison) -> MetricComparisonSummary:
    status = comparison.metrics_status
    reason = _METRIC_NOT_COMPARABLE_REASON if status in _NOT_COMPARABLE_METRIC_STATUSES else None
    return MetricComparisonSummary(status=status.value, reason=reason)


def _difference_entries(differences: list[Difference]) -> list[DifferenceEntry]:
    return [
        DifferenceEntry(
            id=str(d.id),
            category=d.category.value,
            field=d.field,
            old_value=d.old_value,
            new_value=d.new_value,
            difference_type=d.difference_type.value,
            severity=d.severity.value,
            confidence=d.confidence.value,
            evidence_source=d.evidence_source,
            is_potential_contributor=d.is_potential_contributor,
        )
        for d in differences
    ]


def _reproducibility_summary(reproducibility: ReproducibilityAssessment | None) -> ReproducibilitySummary:
    if reproducibility is None:
        return ReproducibilitySummary(available=False)
    return ReproducibilitySummary(
        available=True,
        classification=reproducibility.classification.value,
        rationale=reproducibility.rationale_json,
    )


def _potential_contributors(differences: list[Difference]) -> list[ContributorEntry]:
    return [
        ContributorEntry(
            difference_id=str(d.id),
            category=d.category.value,
            field=d.field,
            evidence_strength=evidence_strength(d.severity, d.confidence).value,
        )
        for d in differences
        if d.is_potential_contributor
    ]


def _investigation_summary(plan: InvestigationPlan | None) -> InvestigationSummary:
    if plan is None:
        return InvestigationSummary(available=False, reason="No matching investigation plan was supplied.")
    return InvestigationSummary(
        available=True,
        investigation_id=str(plan.id),
        changed_category=plan.changed_category.value,
        changed_field=plan.changed_field,
        evidence_strength=plan.evidence_strength.value,
    )


def _counterfactual_summary(plan: CounterfactualPlan | None) -> CounterfactualSummary:
    if plan is None:
        return CounterfactualSummary(available=False, reason="No matching counterfactual plan was supplied.")
    return CounterfactualSummary(
        available=True,
        counterfactual_id=str(plan.id),
        restored_category=plan.restored_category.value,
        restored_field=plan.restored_field,
        outcome=plan.outcome.value if plan.outcome is not None else None,
    )


def _evidence_references(
    comparison: ExperimentComparison,
    differences: list[Difference],
    original_run: ExperimentRun,
    reproduction_run: ExperimentRun,
) -> list[str]:
    return [
        *(d.evidence_source for d in differences),
        f"comparison:{comparison.id}",
        f"run:{original_run.id}",
        f"run:{reproduction_run.id}",
    ]


def generate_report(
    comparison: ExperimentComparison,
    experiment: Experiment,
    original_run: ExperimentRun,
    reproduction_run: ExperimentRun,
    reproducibility: ReproducibilityAssessment | None,
    investigation_plan: InvestigationPlan | None = None,
    counterfactual_plan: CounterfactualPlan | None = None,
) -> ReproducibilityReport:
    differences = list(comparison.differences)

    return ReproducibilityReport(
        report_version=REPORT_GENERATOR_VERSION,
        comparison_id=comparison.id,
        experiment=_experiment_summary(experiment),
        original_run=_run_summary(original_run),
        reproduction_run=_run_summary(reproduction_run),
        provenance=_category_provenance(comparison),
        metric_comparison=_metric_comparison(comparison),
        differences=_difference_entries(differences),
        reproducibility=_reproducibility_summary(reproducibility),
        potential_contributors=_potential_contributors(differences),
        investigation=_investigation_summary(investigation_plan),
        counterfactual=_counterfactual_summary(counterfactual_plan),
        evidence_references=_evidence_references(comparison, differences, original_run, reproduction_run),
    )
