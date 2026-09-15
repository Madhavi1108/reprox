import math

import pytest

from app.provenance.canonicalize import (
    NonCanonicalizableValueError,
    canonical_hash,
    canonicalize_json,
)


def test_key_order_invariance():
    a = {"batch_size": 64, "learning_rate": 0.001}
    b = {"learning_rate": 0.001, "batch_size": 64}
    assert canonicalize_json(a) == canonicalize_json(b)
    assert canonical_hash(a) == canonical_hash(b)


def test_nested_key_order_invariance():
    a = {"outer": {"z": 1, "a": 2}, "list": [{"b": 1, "a": 2}]}
    b = {"list": [{"a": 2, "b": 1}], "outer": {"a": 2, "z": 1}}
    assert canonical_hash(a) == canonical_hash(b)


def test_list_order_is_significant():
    a = {"items": [1, 2, 3]}
    b = {"items": [3, 2, 1]}
    assert canonical_hash(a) != canonical_hash(b)


def test_float_formatting_stable():
    a = {"x": 0.1}
    b = {"x": 0.100000000000}
    assert canonicalize_json(a) == canonicalize_json(b)


def test_float_vs_int_are_distinguishable_in_practice():
    # 1 and 1.0 canonicalize to different tokens (int stays int, float
    # gets formatted) - this is intentional: type changes are meaningful
    # provenance differences, not noise to be smoothed away.
    assert canonicalize_json({"x": 1}) != canonicalize_json({"x": 1.0})


def test_unicode_nfc_normalization():
    # "e" + combining acute accent vs precomposed "é" must canonicalize
    # identically.
    decomposed = {"name": "café"}
    precomposed = {"name": "café"}
    assert canonical_hash(decomposed) == canonical_hash(precomposed)


def test_non_finite_float_rejected():
    with pytest.raises(NonCanonicalizableValueError):
        canonicalize_json({"x": math.nan})
    with pytest.raises(NonCanonicalizableValueError):
        canonicalize_json({"x": math.inf})


def test_none_and_bool_preserved():
    assert canonicalize_json({"a": None, "b": True, "c": False}) == '{"a":null,"b":true,"c":false}'


def test_different_content_produces_different_hash():
    assert canonical_hash({"a": 1}) != canonical_hash({"a": 2})


def test_hash_is_deterministic_across_repeated_calls():
    payload = {"nested": {"k": [1, 2, {"z": 9, "a": "x"}]}, "seed": 42}
    h1 = canonical_hash(payload)
    h2 = canonical_hash(payload)
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex digest length
