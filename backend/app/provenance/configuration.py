"""Configuration provenance capture (spec section 19).

Arbitrary structured experiment configuration (hyperparameters, model
type, etc). Must be canonicalized before hashing so that key-order
permutations of an equivalent config produce an identical fingerprint.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.provenance.canonicalize import canonical_hash, canonicalize_json

CONFIGURATION_FINGERPRINT_VERSION = "1.0.0"


@dataclass(frozen=True)
class ConfigurationProvenance:
    raw: dict[str, Any]
    canonical_json: str
    configuration_fingerprint_hash: str
    fingerprint_version: str = CONFIGURATION_FINGERPRINT_VERSION


def capture_configuration_provenance(raw_config: dict[str, Any]) -> ConfigurationProvenance:
    canonical = canonicalize_json(raw_config)
    return ConfigurationProvenance(
        raw=raw_config,
        canonical_json=canonical,
        configuration_fingerprint_hash=canonical_hash(raw_config),
    )
