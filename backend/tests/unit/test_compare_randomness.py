from app.comparison.category_comparators.randomness import compare_randomness
from app.db.models.enums import ComparisonStatus, DifferenceType
from app.provenance.randomness import RandomnessProvenance, capture_randomness_provenance


def _randomness(python_seed=None, numpy_seed=None, other_seeds=None) -> RandomnessProvenance:
    return capture_randomness_provenance(python_seed=python_seed, numpy_seed=numpy_seed, other_seeds=other_seeds)


def test_identical_inputs_are_same():
    base = _randomness(python_seed=42, numpy_seed=42)
    compare = _randomness(python_seed=42, numpy_seed=42)
    result = compare_randomness(base, compare)
    assert result.status == ComparisonStatus.SAME
    assert result.differences == []


def test_python_seed_change_is_value_changed():
    base = _randomness(python_seed=42)
    compare = _randomness(python_seed=99)
    result = compare_randomness(base, compare)
    assert result.status == ComparisonStatus.DIFFERENT
    diffs = [d for d in result.differences if d.field == "python_seed"]
    assert len(diffs) == 1
    assert diffs[0].difference_type == DifferenceType.VALUE_CHANGED


def test_other_seed_bound_to_unbound_is_high_severity():
    from app.db.models.enums import Severity

    base = _randomness(other_seeds={"random_state": 5})
    compare = _randomness(other_seeds={"random_state": None})
    result = compare_randomness(base, compare)
    diffs = [d for d in result.differences if d.field == "other_seeds.random_state"]
    assert len(diffs) == 1
    assert diffs[0].severity == Severity.HIGH


def test_other_seed_added():
    base = _randomness(python_seed=1)
    compare = _randomness(python_seed=1, other_seeds={"random_state": 5})
    result = compare_randomness(base, compare)
    added = [d for d in result.differences if d.field == "other_seeds.random_state"]
    assert len(added) == 1
    assert added[0].difference_type == DifferenceType.ADDED


def test_determinism_classification_change_recorded():
    base = _randomness(python_seed=1, numpy_seed=1)
    compare = _randomness(python_seed=1, numpy_seed=1, other_seeds={"random_state": None})
    result = compare_randomness(base, compare)
    assert any(d.field == "determinism_classification" for d in result.differences)


def test_both_none_is_not_comparable():
    result = compare_randomness(None, None)
    assert result.status == ComparisonStatus.NOT_COMPARABLE


def test_one_none_is_unknown():
    result = compare_randomness(_randomness(python_seed=1), None)
    assert result.status == ComparisonStatus.UNKNOWN


def test_version_mismatch_is_not_comparable():
    from dataclasses import replace

    base = _randomness(python_seed=1)
    compare = replace(base, fingerprint_version="2.0.0")
    result = compare_randomness(base, compare)
    assert result.status == ComparisonStatus.NOT_COMPARABLE


def test_real_capture_with_differing_other_seeds():
    base = capture_randomness_provenance(python_seed=42, numpy_seed=42, other_seeds={"random_state": 7})
    compare = capture_randomness_provenance(python_seed=42, numpy_seed=42, other_seeds={"random_state": 8})
    result = compare_randomness(base, compare)
    assert result.status == ComparisonStatus.DIFFERENT
    assert any(d.field == "other_seeds.random_state" for d in result.differences)
