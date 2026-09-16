from app.comparison.category_comparators.metrics import ToleranceConfig, compare_metrics
from app.db.models.enums import ComparisonStatus, DifferenceType


def test_both_missing_is_not_comparable():
    result = compare_metrics(None, None)
    assert result.status == ComparisonStatus.NOT_COMPARABLE
    assert result.differences == []


def test_missing_on_one_side_is_unknown():
    result = compare_metrics(None, {"accuracy": 0.9})
    assert result.status == ComparisonStatus.UNKNOWN
    assert len(result.differences) == 1
    assert result.differences[0].difference_type == DifferenceType.MISSING_IN_BASE

    result = compare_metrics({"accuracy": 0.9}, None)
    assert result.status == ComparisonStatus.UNKNOWN
    assert result.differences[0].difference_type == DifferenceType.MISSING_IN_COMPARE


def test_exact_match_is_same():
    result = compare_metrics({"accuracy": 0.9427}, {"accuracy": 0.9427})
    assert result.status == ComparisonStatus.SAME
    assert result.differences == []


def test_empty_dicts_are_same():
    result = compare_metrics({}, {})
    assert result.status == ComparisonStatus.SAME
    assert result.differences == []


def test_small_difference_within_default_zero_tolerance_is_different():
    # Defaults require exact equality - no tolerance configured means no leniency.
    result = compare_metrics({"accuracy": 0.9427}, {"accuracy": 0.9425})
    assert result.status == ComparisonStatus.DIFFERENT


def test_small_difference_within_configured_tolerance_is_partially_matching():
    tolerance = ToleranceConfig(default_abs_tolerance=0.001)
    result = compare_metrics({"accuracy": 0.9427}, {"accuracy": 0.9425}, tolerance)
    assert result.status == ComparisonStatus.PARTIALLY_MATCHING
    assert len(result.differences) == 1
    assert result.differences[0].field == "metrics.accuracy"
    assert result.differences[0].difference_type == DifferenceType.VALUE_CHANGED


def test_large_difference_outside_tolerance_is_different():
    tolerance = ToleranceConfig(default_abs_tolerance=0.001)
    result = compare_metrics({"accuracy": 0.9427}, {"accuracy": 0.8143}, tolerance)
    assert result.status == ComparisonStatus.DIFFERENT


def test_relative_tolerance_scales_with_magnitude():
    tolerance = ToleranceConfig(default_rel_tolerance=0.01)
    # 1% of 100.0 is 1.0, so a difference of 0.5 is within tolerance.
    result = compare_metrics({"loss": 100.0}, {"loss": 100.5}, tolerance)
    assert result.status == ComparisonStatus.PARTIALLY_MATCHING
    # A difference of 5.0 exceeds 1% of 100.0.
    result = compare_metrics({"loss": 100.0}, {"loss": 105.0}, tolerance)
    assert result.status == ComparisonStatus.DIFFERENT


def test_per_metric_override_takes_precedence_over_default():
    tolerance = ToleranceConfig(default_abs_tolerance=0.0, per_metric={"accuracy": (0.01, 0.0)})
    result = compare_metrics({"accuracy": 0.94, "loss": 0.5}, {"accuracy": 0.945, "loss": 0.5}, tolerance)
    assert result.status == ComparisonStatus.PARTIALLY_MATCHING
    assert len(result.differences) == 1
    assert result.differences[0].field == "metrics.accuracy"


def test_added_metric_key_is_different():
    result = compare_metrics({"accuracy": 0.9}, {"accuracy": 0.9, "f1": 0.8})
    assert result.status == ComparisonStatus.DIFFERENT
    assert any(d.field == "metrics.f1" and d.difference_type == DifferenceType.ADDED for d in result.differences)


def test_removed_metric_key_is_different():
    result = compare_metrics({"accuracy": 0.9, "f1": 0.8}, {"accuracy": 0.9})
    assert result.status == ComparisonStatus.DIFFERENT
    assert any(d.field == "metrics.f1" and d.difference_type == DifferenceType.REMOVED for d in result.differences)


def test_mismatch_outweighs_tolerated_difference_in_aggregate_status():
    tolerance = ToleranceConfig(default_abs_tolerance=0.01)
    result = compare_metrics(
        {"accuracy": 0.94, "loss": 0.5},
        {"accuracy": 0.945, "loss": 0.9},
        tolerance,
    )
    assert result.status == ComparisonStatus.DIFFERENT
