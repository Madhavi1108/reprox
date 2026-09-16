"""Environment category comparator (Phase 11).

Fast path is `environment_fingerprint_hash` equality. `hostname`,
`cpu_model`, `cpu_count`, `ram_total_mb` are informative-only - recorded
when they differ but never affect `status` - because
`app/provenance/environment.py` deliberately excludes them from the hash
so two runs on different machines don't appear "different" over
descriptive-only metadata. The same exclusion is enforced here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.comparison.difference import RawDifference, resolve_missing_or_version_mismatch
from app.db.models.enums import ComparisonStatus, Confidence, DifferenceCategory, DifferenceType, Severity
from app.provenance.environment import DependencyEntry, EnvironmentProvenance

COMPARE_ENVIRONMENT_VERSION = "1.0.0"

_HASH_RELEVANT_SCALAR_FIELDS = ("os_name", "os_version", "architecture", "python_version")
_INFORMATIONAL_FIELDS = ("hostname", "cpu_model", "cpu_count", "ram_total_mb")


@dataclass(frozen=True)
class EnvironmentComparisonResult:
    status: ComparisonStatus
    differences: list[RawDifference] = field(default_factory=list)


def _diff_informational_fields(base: EnvironmentProvenance, compare: EnvironmentProvenance) -> list[RawDifference]:
    differences: list[RawDifference] = []
    for name in _INFORMATIONAL_FIELDS:
        old, new = getattr(base, name), getattr(compare, name)
        if old != new:
            differences.append(
                RawDifference(
                    category=DifferenceCategory.ENVIRONMENT,
                    field=name,
                    old_value=str(old) if old is not None else None,
                    new_value=str(new) if new is not None else None,
                    difference_type=DifferenceType.VALUE_CHANGED,
                    evidence_source=f"environment.{name}",
                    severity=Severity.LOW,
                    confidence=Confidence.MEDIUM,
                )
            )
    return differences


def _diff_hash_relevant_scalars(base: EnvironmentProvenance, compare: EnvironmentProvenance) -> list[RawDifference]:
    differences: list[RawDifference] = []
    for name in _HASH_RELEVANT_SCALAR_FIELDS:
        old, new = getattr(base, name), getattr(compare, name)
        if old != new:
            differences.append(
                RawDifference(
                    category=DifferenceCategory.ENVIRONMENT,
                    field=name,
                    old_value=str(old),
                    new_value=str(new),
                    difference_type=DifferenceType.VALUE_CHANGED,
                    evidence_source=f"environment.{name}",
                    severity=Severity.HIGH,
                    confidence=Confidence.HIGH,
                )
            )

    if base.gpu_present != compare.gpu_present:
        differences.append(
            RawDifference(
                category=DifferenceCategory.ENVIRONMENT,
                field="gpu_present",
                old_value=str(base.gpu_present),
                new_value=str(compare.gpu_present),
                difference_type=DifferenceType.VALUE_CHANGED,
                evidence_source="environment.gpu_present",
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
            )
        )
    for name in ("gpu_model", "cuda_version"):
        old, new = getattr(base, name), getattr(compare, name)
        if old != new:
            differences.append(
                RawDifference(
                    category=DifferenceCategory.ENVIRONMENT,
                    field=name,
                    old_value=old,
                    new_value=new,
                    difference_type=DifferenceType.VALUE_CHANGED,
                    evidence_source=f"environment.{name}",
                    severity=Severity.MEDIUM,
                    confidence=Confidence.HIGH,
                )
            )
    return differences


def _diff_dependencies(base: EnvironmentProvenance, compare: EnvironmentProvenance) -> list[RawDifference]:
    base_deps: dict[str, DependencyEntry] = {d.package_name: d for d in base.dependencies}
    compare_deps: dict[str, DependencyEntry] = {d.package_name: d for d in compare.dependencies}
    differences: list[RawDifference] = []

    for package in sorted(compare_deps.keys() - base_deps.keys()):
        differences.append(
            RawDifference(
                category=DifferenceCategory.ENVIRONMENT,
                field=f"dependencies.{package}",
                old_value=None,
                new_value=compare_deps[package].version,
                difference_type=DifferenceType.ADDED,
                evidence_source="environment.dependencies",
                severity=Severity.MEDIUM,
                confidence=Confidence.HIGH,
            )
        )
    for package in sorted(base_deps.keys() - compare_deps.keys()):
        differences.append(
            RawDifference(
                category=DifferenceCategory.ENVIRONMENT,
                field=f"dependencies.{package}",
                old_value=base_deps[package].version,
                new_value=None,
                difference_type=DifferenceType.REMOVED,
                evidence_source="environment.dependencies",
                severity=Severity.MEDIUM,
                confidence=Confidence.HIGH,
            )
        )
    for package in sorted(base_deps.keys() & compare_deps.keys()):
        old_version, new_version = base_deps[package].version, compare_deps[package].version
        if old_version != new_version:
            differences.append(
                RawDifference(
                    category=DifferenceCategory.ENVIRONMENT,
                    field=f"dependencies.{package}",
                    old_value=old_version,
                    new_value=new_version,
                    difference_type=DifferenceType.VALUE_CHANGED,
                    evidence_source="environment.dependencies",
                    severity=Severity.MEDIUM,
                    confidence=Confidence.HIGH,
                )
            )
    return differences


def compare_environment(
    base: EnvironmentProvenance | None, compare: EnvironmentProvenance | None
) -> EnvironmentComparisonResult:
    guard = resolve_missing_or_version_mismatch(base, compare, category=DifferenceCategory.ENVIRONMENT)
    if guard is not None:
        status, differences = guard
        return EnvironmentComparisonResult(status=status, differences=differences)

    informational = _diff_informational_fields(base, compare)

    if base.environment_fingerprint_hash == compare.environment_fingerprint_hash:
        return EnvironmentComparisonResult(status=ComparisonStatus.SAME, differences=informational)

    differences = _diff_hash_relevant_scalars(base, compare) + _diff_dependencies(base, compare) + informational
    return EnvironmentComparisonResult(status=ComparisonStatus.DIFFERENT, differences=differences)
