"""Composite experiment fingerprint (spec sections 24-25).

The experiment fingerprint is a hash over the canonicalized *category
hashes* from Phases 4-8 (code, dataset, environment, configuration,
randomness) - never a raw string concatenation, and never computed
directly over the underlying provenance data (that's what each category's
own fingerprint function already does).

Missing categories are kept as explicit `null` in the hashed payload
(never omitted) so "provenance missing" produces a distinguishable,
recorded outcome (`missing_components`) rather than silently changing
which fields are hashed. This is what lets the reproducibility classifier
(Phase 12) tell "the fingerprints differ because a category is missing"
apart from "the fingerprints differ because the category actually
changed."

`fingerprint_version` must be bumped whenever the algorithm changes;
historical composite hashes computed under an old version must never be
silently reinterpreted as if computed under a new one - see
docs/FINGERPRINT_ALGORITHM.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.provenance.canonicalize import canonical_hash
from app.provenance.code import CodeProvenance
from app.provenance.configuration import ConfigurationProvenance
from app.provenance.dataset import DatasetProvenance
from app.provenance.environment import EnvironmentProvenance
from app.provenance.randomness import RandomnessProvenance

COMPOSITE_FINGERPRINT_VERSION = "1.0.0"

_CATEGORY_ORDER = ("code_hash", "dataset_hash", "environment_hash", "configuration_hash", "randomness_hash")


@dataclass(frozen=True)
class CompositeFingerprint:
    code_hash: str | None
    dataset_hash: str | None
    environment_hash: str | None
    configuration_hash: str | None
    randomness_hash: str | None
    composite_hash: str
    fingerprint_version: str
    missing_components: list[str] = field(default_factory=list)


def compute_composite_fingerprint(
    *,
    code_hash: str | None,
    dataset_hash: str | None,
    environment_hash: str | None,
    configuration_hash: str | None,
    randomness_hash: str | None,
    fingerprint_version: str = COMPOSITE_FINGERPRINT_VERSION,
) -> CompositeFingerprint:
    category_hashes = {
        "code_hash": code_hash,
        "dataset_hash": dataset_hash,
        "environment_hash": environment_hash,
        "configuration_hash": configuration_hash,
        "randomness_hash": randomness_hash,
    }
    payload = {"fingerprint_version": fingerprint_version, **category_hashes}
    composite_hash = canonical_hash(payload)
    missing_components = [name for name in _CATEGORY_ORDER if category_hashes[name] is None]

    return CompositeFingerprint(
        code_hash=code_hash,
        dataset_hash=dataset_hash,
        environment_hash=environment_hash,
        configuration_hash=configuration_hash,
        randomness_hash=randomness_hash,
        composite_hash=composite_hash,
        fingerprint_version=fingerprint_version,
        missing_components=missing_components,
    )


def assemble_experiment_fingerprint(
    *,
    code: CodeProvenance | None,
    dataset: DatasetProvenance | None,
    environment: EnvironmentProvenance | None,
    configuration: ConfigurationProvenance | None,
    randomness: RandomnessProvenance | None,
    fingerprint_version: str = COMPOSITE_FINGERPRINT_VERSION,
) -> CompositeFingerprint:
    """Build the composite fingerprint directly from the Phase 4-8
    provenance objects, extracting each category's own hash field. A
    `None` provenance object (that category could not be captured for
    this run) becomes an explicit `None` hash, not an omitted field."""
    return compute_composite_fingerprint(
        code_hash=code.tree_fingerprint_hash if code else None,
        dataset_hash=dataset.content_hash if dataset else None,
        environment_hash=environment.environment_fingerprint_hash if environment else None,
        configuration_hash=configuration.configuration_fingerprint_hash if configuration else None,
        randomness_hash=randomness.randomness_fingerprint_hash if randomness else None,
        fingerprint_version=fingerprint_version,
    )
