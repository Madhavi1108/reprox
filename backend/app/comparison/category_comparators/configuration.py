"""Configuration category comparator (Phase 11).

Fast path is `configuration_fingerprint_hash` equality (already
key-order-independent, since `app/provenance/canonicalize.py` sorts keys
before hashing). On mismatch, a recursive key-path diff walks the two
`raw` dicts and emits one difference per changed leaf, using dot-joined
paths (e.g. "model.C") so a nested hyperparameter change is traceable.
Lists are treated as atomic leaves - not recursed element-by-element -
consistent with the canonicalization module's own "lists are ordered
sequences, not sets" stance; this is a documented limitation, not an
oversight.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.comparison.difference import RawDifference, resolve_missing_or_version_mismatch
from app.db.models.enums import ComparisonStatus, Confidence, DifferenceCategory, DifferenceType, Severity
from app.provenance.canonicalize import canonicalize_json
from app.provenance.configuration import ConfigurationProvenance

COMPARE_CONFIGURATION_VERSION = "1.0.0"


@dataclass(frozen=True)
class ConfigurationComparisonResult:
    status: ComparisonStatus
    differences: list[RawDifference] = field(default_factory=list)


def _stringify_leaf(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return canonicalize_json(list(value))
    return str(value)


def _diff_dict(base_d: dict[str, Any], compare_d: dict[str, Any], prefix: str) -> list[RawDifference]:
    differences: list[RawDifference] = []

    for key in sorted(compare_d.keys() - base_d.keys()):
        differences.append(
            RawDifference(
                category=DifferenceCategory.CONFIGURATION,
                field=f"{prefix}{key}",
                old_value=None,
                new_value=_stringify_leaf(compare_d[key]),
                difference_type=DifferenceType.ADDED,
                evidence_source="configuration.raw",
                severity=Severity.MEDIUM,
                confidence=Confidence.HIGH,
            )
        )

    for key in sorted(base_d.keys() - compare_d.keys()):
        differences.append(
            RawDifference(
                category=DifferenceCategory.CONFIGURATION,
                field=f"{prefix}{key}",
                old_value=_stringify_leaf(base_d[key]),
                new_value=None,
                difference_type=DifferenceType.REMOVED,
                evidence_source="configuration.raw",
                severity=Severity.MEDIUM,
                confidence=Confidence.HIGH,
            )
        )

    for key in sorted(base_d.keys() & compare_d.keys()):
        old_value, new_value = base_d[key], compare_d[key]
        if isinstance(old_value, dict) and isinstance(new_value, dict):
            differences.extend(_diff_dict(old_value, new_value, prefix=f"{prefix}{key}."))
            continue
        if old_value == new_value:
            continue
        difference_type = (
            DifferenceType.TYPE_CHANGED if type(old_value) is not type(new_value) else DifferenceType.VALUE_CHANGED
        )
        differences.append(
            RawDifference(
                category=DifferenceCategory.CONFIGURATION,
                field=f"{prefix}{key}",
                old_value=_stringify_leaf(old_value),
                new_value=_stringify_leaf(new_value),
                difference_type=difference_type,
                evidence_source="configuration.raw",
                severity=Severity.MEDIUM,
                confidence=Confidence.HIGH,
            )
        )

    return differences


def compare_configuration(
    base: ConfigurationProvenance | None, compare: ConfigurationProvenance | None
) -> ConfigurationComparisonResult:
    guard = resolve_missing_or_version_mismatch(base, compare, category=DifferenceCategory.CONFIGURATION)
    if guard is not None:
        status, differences = guard
        return ConfigurationComparisonResult(status=status, differences=differences)

    if base.configuration_fingerprint_hash == compare.configuration_fingerprint_hash:
        return ConfigurationComparisonResult(status=ComparisonStatus.SAME, differences=[])

    differences = _diff_dict(base.raw, compare.raw, prefix="")
    return ConfigurationComparisonResult(status=ComparisonStatus.DIFFERENT, differences=differences)
