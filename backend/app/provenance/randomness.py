"""Randomness provenance capture (spec sections 20-21).

A fixed seed is never treated as a guarantee of reproducibility. This
module models nondeterminism explicitly via `DeterminismClassification`
rather than emitting a binary "deterministic: yes/no" flag, and the
classifier deliberately has no path that reaches `DETERMINISTIC` - only
`CONDITIONALLY_DETERMINISTIC` at best, because sources like BLAS thread
scheduling, floating-point summation order, and library-version drift can
still cause divergence even with every known seed bound.

`other_seeds` represents named, workload-specific stochastic parameters
(e.g. a scikit-learn estimator's `random_state`). A key present with a
`None` value means "this workload has a known stochastic source that was
NOT bound to a seed" - this is what correctly downgrades the
classification to NON_DETERMINISTIC instead of silently ignoring it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.db.models.enums import DeterminismClassification, DeterminismIntent
from app.provenance.canonicalize import canonical_hash

RANDOMNESS_FINGERPRINT_VERSION = "1.0.0"


@dataclass(frozen=True)
class RandomnessProvenance:
    python_seed: int | None
    numpy_seed: int | None
    other_seeds: dict[str, int | None]
    determinism_intent: DeterminismIntent
    determinism_classification: DeterminismClassification
    randomness_fingerprint_hash: str
    fingerprint_version: str = RANDOMNESS_FINGERPRINT_VERSION


def _classify_determinism(
    python_seed: int | None,
    numpy_seed: int | None,
    other_seeds: dict[str, int | None],
) -> tuple[DeterminismIntent, DeterminismClassification]:
    any_seed_bound = (
        python_seed is not None
        or numpy_seed is not None
        or any(v is not None for v in other_seeds.values())
    )
    any_declared_but_unbound = any(v is None for v in other_seeds.values())

    if not other_seeds and python_seed is None and numpy_seed is None:
        # Nothing was said about randomness at all - conservative default,
        # never assume determinism from silence.
        return DeterminismIntent.NOT_REQUESTED, DeterminismClassification.UNKNOWN

    intent = DeterminismIntent.REQUESTED if any_seed_bound else DeterminismIntent.NOT_REQUESTED

    if any_declared_but_unbound:
        # A known stochastic source exists and was not seeded - the run is
        # nondeterministic regardless of what else was seeded.
        classification = DeterminismClassification.NON_DETERMINISTIC
    elif any_seed_bound:
        # Every known source is seeded, but this NEVER upgrades to a bare
        # DETERMINISTIC claim - see module docstring.
        classification = DeterminismClassification.CONDITIONALLY_DETERMINISTIC
    else:
        classification = DeterminismClassification.UNKNOWN

    return intent, classification


def compute_randomness_fingerprint(
    *,
    python_seed: int | None,
    numpy_seed: int | None,
    other_seeds: dict[str, int | None],
    determinism_classification: DeterminismClassification,
) -> str:
    payload = {
        "python_seed": python_seed,
        "numpy_seed": numpy_seed,
        "other_seeds": dict(sorted(other_seeds.items())),
        "determinism_classification": determinism_classification.value,
    }
    return canonical_hash(payload)


def capture_randomness_provenance(
    python_seed: int | None = None,
    numpy_seed: int | None = None,
    other_seeds: dict[str, int | None] | None = None,
) -> RandomnessProvenance:
    other_seeds = other_seeds or {}
    intent, classification = _classify_determinism(python_seed, numpy_seed, other_seeds)
    fingerprint = compute_randomness_fingerprint(
        python_seed=python_seed,
        numpy_seed=numpy_seed,
        other_seeds=other_seeds,
        determinism_classification=classification,
    )
    return RandomnessProvenance(
        python_seed=python_seed,
        numpy_seed=numpy_seed,
        other_seeds=other_seeds,
        determinism_intent=intent,
        determinism_classification=classification,
        randomness_fingerprint_hash=fingerprint,
    )
