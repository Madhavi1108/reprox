from app.db.models.enums import DeterminismClassification, DeterminismIntent
from app.provenance.randomness import capture_randomness_provenance


def test_no_seeds_at_all_is_unknown_not_requested():
    prov = capture_randomness_provenance()
    assert prov.determinism_intent == DeterminismIntent.NOT_REQUESTED
    assert prov.determinism_classification == DeterminismClassification.UNKNOWN


def test_python_and_numpy_seed_bound_is_conditionally_deterministic():
    prov = capture_randomness_provenance(python_seed=42, numpy_seed=42)
    assert prov.determinism_intent == DeterminismIntent.REQUESTED
    assert prov.determinism_classification == DeterminismClassification.CONDITIONALLY_DETERMINISTIC


def test_never_claims_outright_deterministic():
    # Sweep a range of "everything seeded" inputs and confirm the
    # classifier never reaches DETERMINISTIC under any of them - only
    # CONDITIONALLY_DETERMINISTIC at best, per the spec's non-determinism
    # model (section 21).
    cases = [
        capture_randomness_provenance(python_seed=1),
        capture_randomness_provenance(numpy_seed=1),
        capture_randomness_provenance(python_seed=1, numpy_seed=1),
        capture_randomness_provenance(python_seed=1, numpy_seed=1, other_seeds={"sklearn_random_state": 7}),
    ]
    for prov in cases:
        assert prov.determinism_classification != DeterminismClassification.DETERMINISTIC


def test_declared_but_unbound_stochastic_source_forces_non_deterministic():
    # random_state is a known stochastic parameter of the workload, but it
    # was left unbound (None) - this must downgrade the classification
    # even though python_seed/numpy_seed are both set.
    prov = capture_randomness_provenance(
        python_seed=42, numpy_seed=42, other_seeds={"sklearn_random_state": None}
    )
    assert prov.determinism_classification == DeterminismClassification.NON_DETERMINISTIC
    assert prov.determinism_intent == DeterminismIntent.REQUESTED


def test_only_unbound_declared_source_with_no_other_seed():
    prov = capture_randomness_provenance(other_seeds={"sklearn_random_state": None})
    assert prov.determinism_intent == DeterminismIntent.NOT_REQUESTED
    assert prov.determinism_classification == DeterminismClassification.NON_DETERMINISTIC


def test_other_seeds_bound_counts_as_seed_present():
    prov = capture_randomness_provenance(other_seeds={"sklearn_random_state": 7})
    assert prov.determinism_intent == DeterminismIntent.REQUESTED
    assert prov.determinism_classification == DeterminismClassification.CONDITIONALLY_DETERMINISTIC


def test_hash_deterministic_for_identical_inputs():
    a = capture_randomness_provenance(python_seed=42, numpy_seed=42, other_seeds={"x": 1})
    b = capture_randomness_provenance(python_seed=42, numpy_seed=42, other_seeds={"x": 1})
    assert a.randomness_fingerprint_hash == b.randomness_fingerprint_hash


def test_hash_changes_with_seed_value():
    a = capture_randomness_provenance(python_seed=42)
    b = capture_randomness_provenance(python_seed=43)
    assert a.randomness_fingerprint_hash != b.randomness_fingerprint_hash


def test_hash_unaffected_by_other_seeds_key_order():
    a = capture_randomness_provenance(other_seeds={"a": 1, "b": 2})
    b = capture_randomness_provenance(other_seeds={"b": 2, "a": 1})
    assert a.randomness_fingerprint_hash == b.randomness_fingerprint_hash


def test_hash_reflects_classification_change():
    # Same seeds, but one run declares an unbound stochastic source -
    # different classification must produce a different hash even though
    # python_seed/numpy_seed match.
    a = capture_randomness_provenance(python_seed=42, numpy_seed=42)
    b = capture_randomness_provenance(python_seed=42, numpy_seed=42, other_seeds={"random_state": None})
    assert a.randomness_fingerprint_hash != b.randomness_fingerprint_hash
    assert a.determinism_classification != b.determinism_classification
