"""Contributor ranking (Phase 14, spec sections 31-32).

When a comparison's outcome actually differs, REPROX must identify which
of the detected differences are *potential contributors* to that
difference, and rank them. Per spec: "Do not use an LLM-generated
arbitrary ranking. The algorithm must be deterministic where possible."

Spec section 32 lists 7 potential ranking inputs: difference magnitude,
historical evidence, known sensitivity, experiment context, dependency
relationship, correlation, controlled rerun evidence. Only **difference
magnitude** is available today - it's already captured as `severity`/
`confidence` on every `RawDifference` (Phases 11/13). The other 6 require
infrastructure that doesn't exist yet (a historical run store, a
sensitivity registry, Phase 22/23's controlled-investigation/
counterfactual engines - both already `OUT OF SCOPE for MVP`). This is a
documented scoping boundary - see docs/CONTRIBUTOR_ANALYSIS.md.

Spec section 31 requires distinguishing 4 states: Observed difference /
Potential contributor / Validated contributor / Confirmed cause, and
"only the strongest state may be used when controlled evidence actually
establishes it." Without controlled reruns (Phase 22/23), REPROX can
only ever produce **Potential contributor** - the weaker, honest state -
never Validated or Confirmed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.comparison.difference import RawDifference
from app.comparison.engine import ComparisonResult
from app.db.models.enums import Confidence, DifferenceCategory, ReproducibilityClassification, Severity

CONTRIBUTOR_RANKING_VERSION = "1.0.0"

_TRIGGER_CLASSIFICATIONS = frozenset(
    {
        ReproducibilityClassification.NOT_REPRODUCIBLE,
        ReproducibilityClassification.PARTIALLY_REPRODUCIBLE,
    }
)

_SEVERITY_ORDER = {Severity.LOW: 0, Severity.MEDIUM: 1, Severity.HIGH: 2, Severity.CRITICAL: 3}
_CONFIDENCE_ORDER = {Confidence.LOW: 0, Confidence.MEDIUM: 1, Confidence.HIGH: 2}


class EvidenceStrength(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"


_TIER_ORDER = {EvidenceStrength.LOW: 0, EvidenceStrength.MODERATE: 1, EvidenceStrength.HIGH: 2}

_SEVERITY_TIER = {
    Severity.LOW: EvidenceStrength.LOW,
    Severity.MEDIUM: EvidenceStrength.MODERATE,
    Severity.HIGH: EvidenceStrength.HIGH,
    Severity.CRITICAL: EvidenceStrength.HIGH,
}

_CONFIDENCE_GATE = {
    Confidence.LOW: EvidenceStrength.MODERATE,
    Confidence.MEDIUM: EvidenceStrength.HIGH,
    Confidence.HIGH: EvidenceStrength.HIGH,
}


def evidence_strength(severity: Severity, confidence: Confidence) -> EvidenceStrength:
    severity_tier = _SEVERITY_TIER[severity]
    confidence_gate = _CONFIDENCE_GATE[confidence]
    return min(severity_tier, confidence_gate, key=lambda tier: _TIER_ORDER[tier])


@dataclass(frozen=True)
class RankedDifference:
    difference: RawDifference
    is_potential_contributor: bool
    evidence_strength: EvidenceStrength | None = None
    rank: int | None = None


@dataclass(frozen=True)
class ContributorRankingResult:
    triggered: bool
    ranked_differences: list[RankedDifference] = field(default_factory=list)
    algorithm_version: str = CONTRIBUTOR_RANKING_VERSION


def _tie_break_key(entry: tuple[int, RawDifference]) -> tuple:
    index, diff = entry
    return (
        -_SEVERITY_ORDER[diff.severity],
        -_CONFIDENCE_ORDER[diff.confidence],
        diff.category.value,
        diff.field,
    )


def rank_contributors(
    comparison: ComparisonResult, classification: ReproducibilityClassification
) -> ContributorRankingResult:
    if classification not in _TRIGGER_CLASSIFICATIONS:
        return ContributorRankingResult(
            triggered=False,
            ranked_differences=[RankedDifference(difference=d, is_potential_contributor=False) for d in comparison.differences],
        )

    eligible_indices = [
        i for i, d in enumerate(comparison.differences) if d.category != DifferenceCategory.METRICS
    ]
    ordered = sorted(((i, comparison.differences[i]) for i in eligible_indices), key=_tie_break_key)

    ranks: dict[int, int] = {index: rank for rank, (index, _) in enumerate(ordered, start=1)}

    ranked_differences: list[RankedDifference] = []
    for i, diff in enumerate(comparison.differences):
        if i in ranks:
            ranked_differences.append(
                RankedDifference(
                    difference=diff,
                    is_potential_contributor=True,
                    evidence_strength=evidence_strength(diff.severity, diff.confidence),
                    rank=ranks[i],
                )
            )
        else:
            ranked_differences.append(RankedDifference(difference=diff, is_potential_contributor=False))

    return ContributorRankingResult(triggered=True, ranked_differences=ranked_differences)
