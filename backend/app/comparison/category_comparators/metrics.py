"""Metrics category comparator (Phase 13, spec section 29).

Exact numerical equality is often inappropriate for ML metrics (a rerun's
94.27% vs 94.25% should be "equivalent under a configured tolerance,"
while 94.27% vs 81.43% must not be). This module implements the
absolute/relative tolerance model the spec requires, with the formula and
its defaults documented in docs/METRIC_TOLERANCE.md (RULE 11: every major
scoring/classification algorithm must be documented and versioned).

A metric pair `(old, new)` is within tolerance iff

    abs(old - new) <= max(abs_tolerance, rel_tolerance * max(abs(old), abs(new)))

Both tolerances default to 0.0 - exact equality is required unless a
caller explicitly configures a tolerance, so no arbitrary "reasonable"
threshold is silently embedded here (per spec: "Support configurable
tolerances" / "must be documented and versioned").

Unlike the other 5 comparators, inputs are plain `dict[str, float]`
snapshots, not a versioned provenance dataclass - no `ExperimentRun`
column captures metric values yet, so this module doesn't reuse
`resolve_missing_or_version_mismatch` (which expects a
`fingerprint_version` attribute) and instead applies its own two-case
presence guard.

Statistical tolerance / confidence intervals (also named in spec section
29) are out of scope here: they require distributional/sample data (e.g.
repeated runs or a variance estimate) that a single scalar metric
snapshot does not carry - a documented scoping decision, not an
oversight.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.comparison.difference import RawDifference
from app.db.models.enums import ComparisonStatus, Confidence, DifferenceCategory, DifferenceType, Severity

METRIC_TOLERANCE_VERSION = "1.0.0"


@dataclass(frozen=True)
class ToleranceConfig:
    default_abs_tolerance: float = 0.0
    default_rel_tolerance: float = 0.0
    per_metric: dict[str, tuple[float, float]] = field(default_factory=dict)

    def tolerance_for(self, name: str) -> tuple[float, float]:
        return self.per_metric.get(name, (self.default_abs_tolerance, self.default_rel_tolerance))


@dataclass(frozen=True)
class MetricsComparisonResult:
    status: ComparisonStatus
    differences: list[RawDifference] = field(default_factory=list)


def within_tolerance(old: float, new: float, abs_tolerance: float, rel_tolerance: float) -> bool:
    return abs(old - new) <= max(abs_tolerance, rel_tolerance * max(abs(old), abs(new)))


def compare_metrics(
    base: dict[str, float] | None,
    compare: dict[str, float] | None,
    tolerance: ToleranceConfig = ToleranceConfig(),
) -> MetricsComparisonResult:
    if base is None and compare is None:
        return MetricsComparisonResult(status=ComparisonStatus.NOT_COMPARABLE, differences=[])

    if base is None or compare is None:
        difference_type = DifferenceType.MISSING_IN_BASE if base is None else DifferenceType.MISSING_IN_COMPARE
        return MetricsComparisonResult(
            status=ComparisonStatus.UNKNOWN,
            differences=[
                RawDifference(
                    category=DifferenceCategory.METRICS,
                    field="metrics",
                    old_value=None if base is None else "present",
                    new_value=None if compare is None else "present",
                    difference_type=difference_type,
                    evidence_source="metrics.presence",
                    severity=Severity.MEDIUM,
                    confidence=Confidence.HIGH,
                )
            ],
        )

    differences: list[RawDifference] = []
    has_mismatch = False
    has_within_tolerance = False

    for name in sorted(compare.keys() - base.keys()):
        differences.append(
            RawDifference(
                category=DifferenceCategory.METRICS,
                field=f"metrics.{name}",
                old_value=None,
                new_value=str(compare[name]),
                difference_type=DifferenceType.ADDED,
                evidence_source="metrics.presence",
                severity=Severity.MEDIUM,
                confidence=Confidence.HIGH,
            )
        )
        has_mismatch = True

    for name in sorted(base.keys() - compare.keys()):
        differences.append(
            RawDifference(
                category=DifferenceCategory.METRICS,
                field=f"metrics.{name}",
                old_value=str(base[name]),
                new_value=None,
                difference_type=DifferenceType.REMOVED,
                evidence_source="metrics.presence",
                severity=Severity.MEDIUM,
                confidence=Confidence.HIGH,
            )
        )
        has_mismatch = True

    for name in sorted(base.keys() & compare.keys()):
        old_value, new_value = base[name], compare[name]
        if old_value == new_value:
            continue

        abs_tolerance, rel_tolerance = tolerance.tolerance_for(name)
        if within_tolerance(old_value, new_value, abs_tolerance, rel_tolerance):
            has_within_tolerance = True
            severity = Severity.LOW
        else:
            has_mismatch = True
            severity = Severity.HIGH

        differences.append(
            RawDifference(
                category=DifferenceCategory.METRICS,
                field=f"metrics.{name}",
                old_value=str(old_value),
                new_value=str(new_value),
                difference_type=DifferenceType.VALUE_CHANGED,
                evidence_source="metrics.tolerance",
                severity=severity,
                confidence=Confidence.HIGH,
            )
        )

    if has_mismatch:
        status = ComparisonStatus.DIFFERENT
    elif has_within_tolerance:
        status = ComparisonStatus.PARTIALLY_MATCHING
    else:
        status = ComparisonStatus.SAME

    return MetricsComparisonResult(status=status, differences=differences)
