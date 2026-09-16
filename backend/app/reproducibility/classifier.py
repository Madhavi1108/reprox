"""Reproducibility classification (Phase 12, spec section 28).

Classifies a `ComparisonResult` (Phase 11) into one of the 7
`ReproducibilityClassification` states using two purely categorical axes -
no numeric thresholds, per the spec's explicit "do not use arbitrary
thresholds" requirement (section 28) and RULE 11 ("every major
scoring/classification algorithm must be documented" - see
docs/REPRODUCIBILITY_CLASSIFICATION.md for the full decision table and its
rationale).

Outcome axis (`metrics_status` - did the measured result match?):
    SAME                -> exact match
    PARTIALLY_MATCHING  -> matched within tolerance, not exact (Phase 13)
    DIFFERENT           -> mismatch outside tolerance
    UNKNOWN/NOT_COMPARABLE -> no outcome evidence at all

Setup axis (aggregate over code/dataset/environment/configuration/
randomness - was the causal setup identical?):
    FULL                 -> all 5 are SAME
    CHANGED_OR_DEGRADED  -> anything else

`metrics_status` is currently always UNKNOWN (Phase 13 hasn't been built),
so most real classifications today correctly land in NOT_COMPARABLE or
INSUFFICIENT_EVIDENCE - that's an honest reflection of what the system can
actually verify right now, not a bug. This module is written generically
against the full ComparisonStatus range so it keeps working unchanged once
Phase 13 starts producing real SAME/PARTIALLY_MATCHING/DIFFERENT metrics
statuses.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.comparison.engine import ComparisonResult
from app.db.models.comparison import ReproducibilityAssessment
from app.db.models.enums import ComparisonStatus, ReproducibilityClassification

REPRODUCIBILITY_ALGORITHM_VERSION = "1.0.0"

_SETUP_CATEGORIES = ("code_status", "dataset_status", "environment_status", "configuration_status", "randomness_status")
_ALL_CATEGORIES = _SETUP_CATEGORIES + ("metrics_status",)


@dataclass(frozen=True)
class ClassificationResult:
    classification: ReproducibilityClassification
    rationale: dict
    algorithm_version: str = REPRODUCIBILITY_ALGORITHM_VERSION


def _setup_axis(result: ComparisonResult) -> str:
    statuses = [getattr(result, name) for name in _SETUP_CATEGORIES]
    if all(status == ComparisonStatus.SAME for status in statuses):
        return "FULL"
    return "CHANGED_OR_DEGRADED"


def _category_statuses(result: ComparisonResult) -> dict[str, str]:
    return {name: getattr(result, name).value for name in _ALL_CATEGORIES}


def _result(
    classification: ReproducibilityClassification,
    *,
    rule: str,
    outcome: str,
    setup: str | None,
    result: ComparisonResult,
) -> ClassificationResult:
    return ClassificationResult(
        classification=classification,
        rationale={
            "rule": rule,
            "outcome": outcome,
            "setup": setup,
            "category_statuses": _category_statuses(result),
        },
    )


def classify_reproducibility(result: ComparisonResult) -> ClassificationResult:
    all_statuses = [getattr(result, name) for name in _ALL_CATEGORIES]
    outcome = result.metrics_status

    if all(status == ComparisonStatus.NOT_COMPARABLE for status in all_statuses):
        return _result(
            ReproducibilityClassification.NOT_COMPARABLE,
            rule="all_categories_not_comparable",
            outcome=outcome.value,
            setup=None,
            result=result,
        )

    if outcome in (ComparisonStatus.UNKNOWN, ComparisonStatus.NOT_COMPARABLE):
        return _result(
            ReproducibilityClassification.INSUFFICIENT_EVIDENCE,
            rule="no_outcome_evidence",
            outcome=outcome.value,
            setup=None,
            result=result,
        )

    if outcome == ComparisonStatus.DIFFERENT:
        return _result(
            ReproducibilityClassification.NOT_REPRODUCIBLE,
            rule="outcome_mismatch",
            outcome=outcome.value,
            setup=_setup_axis(result),
            result=result,
        )

    setup = _setup_axis(result)

    if outcome == ComparisonStatus.SAME:
        if setup == "FULL":
            return _result(
                ReproducibilityClassification.EXACTLY_REPRODUCIBLE,
                rule="exact_outcome_full_setup",
                outcome=outcome.value,
                setup=setup,
                result=result,
            )
        return _result(
            ReproducibilityClassification.CONDITIONALLY_REPRODUCIBLE,
            rule="exact_outcome_degraded_setup",
            outcome=outcome.value,
            setup=setup,
            result=result,
        )

    # outcome == ComparisonStatus.PARTIALLY_MATCHING
    if setup == "FULL":
        return _result(
            ReproducibilityClassification.REPRODUCIBLE_WITHIN_TOLERANCE,
            rule="tolerance_outcome_full_setup",
            outcome=outcome.value,
            setup=setup,
            result=result,
        )
    return _result(
        ReproducibilityClassification.PARTIALLY_REPRODUCIBLE,
        rule="tolerance_outcome_degraded_setup",
        outcome=outcome.value,
        setup=setup,
        result=result,
    )


def assemble_reproducibility_assessment(
    comparison_id: uuid.UUID, classification_result: ClassificationResult
) -> ReproducibilityAssessment:
    """Build an unattached `ReproducibilityAssessment` ORM instance. The
    caller is responsible for `session.add()`/`commit()` once a DB session
    exists (Phase 19), mirroring `app.comparison.engine.assemble_comparison`."""
    return ReproducibilityAssessment(
        id=uuid.uuid4(),
        comparison_id=comparison_id,
        classification=classification_result.classification,
        rationale_json=classification_result.rationale,
        algorithm_version=classification_result.algorithm_version,
    )
