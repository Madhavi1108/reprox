# Fingerprint Algorithm

Status: implemented (Phases 4-10), unit-tested, MVP scope.

## Core primitive: `canonicalize_json` (`app/provenance/canonicalize.py`)

Every fingerprint in REPROX is `SHA-256(canonicalize_json(payload))`, never a
raw string concatenation. Canonicalization rules:

- dict keys sorted recursively → key-insertion order never affects the hash
- list order **preserved** (lists are ordered sequences, not sets — a
  documented limitation, see `docs/EDGE_CASES.md`)
- floats formatted with fixed, locale-independent precision (`.12g`);
  `NaN`/`Infinity` are rejected (`NonCanonicalizableValueError`), never
  silently coerced
- strings NFC-normalized so visually identical strings with different
  Unicode encodings hash identically
- final serialization: `json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=True)`

`CANONICALIZATION_VERSION = "1.0.0"`.

## Category fingerprints

### Code (`app/provenance/code.py`, version `1.0.0`)

Ground truth is `tree_fingerprint_hash`, **not** `git_commit_sha`. For each
file (git-tracked + untracked-but-not-ignored, or a full filesystem walk if
no git repo): `{path (posix, relative), size_bytes, sha256(raw bytes),
language}`. Entries sorted by path, canonicalized, hashed.

Supplementary metadata captured but excluded from the hash: `git_commit_sha`,
`git_branch`, `is_dirty`, `is_detached_head`, `is_shallow_clone`. A dirty
working tree (uncommitted changes, staged changes, or new untracked files)
always changes `tree_fingerprint_hash` even when `git_commit_sha` is
unchanged — this is deliberate and tested.

### Dataset (`app/provenance/dataset.py`, version `1.0.0`)

`content_hash = streamed SHA-256(raw file bytes)` is what feeds the
composite fingerprint — Level 1, byte-exact. Schema (`{col: dtype}`, Level 2)
and per-column statistics (missing/distinct/mean/std/min/max, duplicate row
count — Level 3) are captured alongside it for the comparison engine to
explain *why* two datasets differ, even when row counts match. **Level 4
(distribution similarity) and Level 5 (semantic metadata) comparison are not
implemented** — see `docs/EDGE_CASES.md`.

### Environment (`app/provenance/environment.py`, version `1.0.0`)

Hash payload: `{os_name, os_version, architecture, python_version,
gpu_present, gpu_model, cuda_version, sorted dependency list}`. GPU/CUDA
fields are always present as explicit `null` in this CPU-only MVP so a
future real GPU capture changes the hash without a version bump.
`hostname`, `cpu_model`, `ram_total_mb` are captured for display but are
**not parameters of the hashing function at all** — structurally excluded,
not just unused, so two machines with an identical software environment
never appear "different."

### Configuration (`app/provenance/configuration.py`, version `1.0.0`)

`SHA-256(canonicalize_json(raw_config))`. Key-order permutations of an
equivalent config are guaranteed to hash identically (unit-tested,
including nested objects).

### Randomness (`app/provenance/randomness.py`, version `1.0.0`)

Hash payload: `{python_seed, numpy_seed, sorted(other_seeds),
determinism_classification}`. `other_seeds` models named, workload-specific
stochastic parameters (e.g. a scikit-learn `random_state`); a key present
with value `null` means "this workload has a known stochastic source that
was not seeded."

Classification (`app/db/models/enums.DeterminismClassification`) is never
`DETERMINISTIC` outright:

| Condition | Classification |
|---|---|
| No seeds and no declared stochastic sources at all | `UNKNOWN` |
| A declared stochastic source left unbound (`None`), regardless of other seeds | `NON_DETERMINISTIC` |
| At least one seed bound, no unbound declared sources | `CONDITIONALLY_DETERMINISTIC` |
| Declared sources present but none bound and no other seed | `NON_DETERMINISTIC` |

The classification is itself part of the hashed payload, so two runs with
identical seed values but different declared-stochastic-source coverage
produce different randomness fingerprints.

## Composite experiment fingerprint (`app/fingerprint/composite.py`, version `1.0.0`)

```
payload = {
  "fingerprint_version": "1.0.0",
  "code_hash": <tree_fingerprint_hash or null>,
  "dataset_hash": <content_hash or null>,
  "environment_hash": <environment_fingerprint_hash or null>,
  "configuration_hash": <configuration_fingerprint_hash or null>,
  "randomness_hash": <randomness_fingerprint_hash or null>,
}
composite_hash = SHA-256(canonicalize_json(payload))
```

Nulls are kept **explicit**, never omitted from the payload — a missing
category changes the hash differently than a category that failed to
compute silently would. `missing_components` lists (in fixed category
order: code, dataset, environment, configuration, randomness) which
categories were `None`, so downstream consumers (the reproducibility
classifier, Phase 12) can distinguish "provenance missing" from "provenance
present but different" without re-deriving it from the hash.

`assemble_experiment_fingerprint()` is the convenience entry point that
takes the Phase 4-8 provenance dataclasses directly (`CodeProvenance |
None`, `DatasetProvenance | None`, etc.) and extracts each one's own hash
field, so callers never have to know the internal field names.

## Versioning policy

Every fingerprint dataclass carries its own `fingerprint_version` string,
starting at `"1.0.0"`. If a hashing/canonicalization algorithm changes in a
way that would alter previously-computed hashes for unchanged inputs, the
version **must** be bumped. Historical fingerprints remain stored with the
version they were computed under and are never silently recomputed or
reinterpreted under a new algorithm — a version mismatch between two runs
being compared is itself a `NOT_COMPARABLE` signal for the comparison engine
(Phase 11), not something to paper over.

## Determinism guarantee

Every category fingerprint function, and the composite assembly, is a pure
function of its inputs (no wall-clock time, no randomness, no environment
lookups inside the hashing step itself — only in the separate *capture*
step). Calling any `compute_*`/`capture_*` function twice with identical
inputs always produces an identical hash; this is enforced by unit tests in
`backend/tests/unit/test_*_fingerprint.py` for every category and for the
composite.
