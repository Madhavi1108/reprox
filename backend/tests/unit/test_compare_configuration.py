from app.comparison.category_comparators.configuration import compare_configuration
from app.db.models.enums import ComparisonStatus, DifferenceType
from app.provenance.configuration import ConfigurationProvenance, capture_configuration_provenance


def _config(raw: dict) -> ConfigurationProvenance:
    return capture_configuration_provenance(raw)


def test_identical_dict_different_key_order_is_same():
    base = _config({"model": "logreg", "C": 1.0})
    compare = _config({"C": 1.0, "model": "logreg"})
    result = compare_configuration(base, compare)
    assert result.status == ComparisonStatus.SAME
    assert result.differences == []


def test_top_level_scalar_change_is_value_changed():
    base = _config({"C": 1.0})
    compare = _config({"C": 2.0})
    result = compare_configuration(base, compare)
    assert result.status == ComparisonStatus.DIFFERENT
    diffs = [d for d in result.differences if d.field == "C"]
    assert len(diffs) == 1
    assert diffs[0].difference_type == DifferenceType.VALUE_CHANGED


def test_nested_key_change_uses_dotted_path():
    base = _config({"model": {"C": 1.0}})
    compare = _config({"model": {"C": 2.0}})
    result = compare_configuration(base, compare)
    diffs = [d for d in result.differences if d.field == "model.C"]
    assert len(diffs) == 1


def test_key_added_and_removed():
    base = _config({"C": 1.0})
    compare = _config({"C": 1.0, "penalty": "l2"})
    result = compare_configuration(base, compare)
    added = [d for d in result.differences if d.field == "penalty"]
    assert len(added) == 1
    assert added[0].difference_type == DifferenceType.ADDED

    result_reverse = compare_configuration(compare, base)
    removed = [d for d in result_reverse.differences if d.field == "penalty"]
    assert len(removed) == 1
    assert removed[0].difference_type == DifferenceType.REMOVED


def test_value_type_change_is_type_changed():
    base = _config({"C": 1})
    compare = _config({"C": "1"})
    result = compare_configuration(base, compare)
    diffs = [d for d in result.differences if d.field == "C"]
    assert len(diffs) == 1
    assert diffs[0].difference_type == DifferenceType.TYPE_CHANGED


def test_list_leaf_treated_as_atomic():
    base = _config({"layers": [1, 2, 3]})
    compare = _config({"layers": [1, 2, 4]})
    result = compare_configuration(base, compare)
    diffs = [d for d in result.differences if d.field == "layers"]
    assert len(diffs) == 1
    assert diffs[0].difference_type == DifferenceType.VALUE_CHANGED


def test_both_none_is_not_comparable():
    result = compare_configuration(None, None)
    assert result.status == ComparisonStatus.NOT_COMPARABLE


def test_one_none_is_unknown():
    result = compare_configuration(_config({"C": 1.0}), None)
    assert result.status == ComparisonStatus.UNKNOWN


def test_version_mismatch_is_not_comparable():
    from dataclasses import replace

    base = _config({"C": 1.0})
    compare = replace(base, fingerprint_version="2.0.0")
    result = compare_configuration(base, compare)
    assert result.status == ComparisonStatus.NOT_COMPARABLE
