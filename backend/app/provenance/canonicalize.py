"""Deterministic canonicalization + hashing primitive.

Every fingerprinting module in REPROX builds on this: recursively
normalize a JSON-compatible structure into one deterministic textual
representation, then SHA-256 it. See docs/FINGERPRINT_ALGORITHM.md.

Rules (must all hold for the composite experiment fingerprint to be
trustworthy):
  - dict keys are sorted recursively, so key-insertion-order never
    changes the hash.
  - list order is preserved (NOT sorted) - lists are treated as
    meaningfully ordered sequences, not sets. This is a documented
    limitation (see docs/EDGE_CASES.md): two lists containing the same
    elements in a different order will hash differently.
  - floats are formatted with a fixed, locale-independent representation
    so that e.g. 0.1 and 0.10 canonicalize identically, and NaN/Infinity
    (which are not valid JSON) are rejected rather than silently coerced.
  - strings are NFC unicode-normalized so visually identical strings with
    different Unicode encodings hash identically.
"""

from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from typing import Any

CANONICALIZATION_VERSION = "1.0.0"


class NonCanonicalizableValueError(ValueError):
    """Raised when a value cannot be deterministically canonicalized."""


def _canonicalize_value(value: Any) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise NonCanonicalizableValueError(
                f"Cannot canonicalize non-finite float: {value!r}"
            )
        # Fixed-precision, locale-independent, trailing-zero-stable formatting.
        return format(value, ".12g")
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, (list, tuple)):
        return [_canonicalize_value(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _canonicalize_value(v) for k, v in value.items()}
    raise NonCanonicalizableValueError(
        f"Cannot canonicalize value of type {type(value).__name__}: {value!r}"
    )


def canonicalize_json(obj: Any) -> str:
    """Return a deterministic, sorted-key JSON string for `obj`.

    Two structurally-equal-but-differently-ordered dicts always produce the
    identical string. Never use plain `json.dumps` for anything that feeds
    a fingerprint hash - only this function.
    """
    normalized = _canonicalize_value(obj)
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_hex(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def canonical_hash(obj: Any) -> str:
    """Canonicalize `obj` then SHA-256 the result. The core primitive used
    by every category-specific fingerprint function."""
    return sha256_hex(canonicalize_json(obj))
