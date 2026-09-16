# Comparison Engine

Status: implemented (Phases 11 and 13), unit-tested, MVP scope.

Phase 11 compares two runs' Phase 4-9 provenance objects, one category at a
time, and produces a `ComparisonStatus` plus a list of field-level
differences explaining *why* they differ (not just *that* they differ).
This is the evidence Phase 12 (reproducibility classification) consumes.
No DB session is touched anywhere in this phase — comparators
and the orchestrator are pure functions, matching the style of Phase 10's
`compute_composite_fingerprint`/`assemble_experiment_fingerprint`. Wiring a
real DB session belongs to Phase 19 (FastAPI). Phase 13 added a 6th
comparator, `metrics.py` (see `docs/METRIC_TOLERANCE.md`), completing the
set that feeds `ComparisonResult`.

## `RawDifference` (`app/comparison/difference.py`)

Comparators return `RawDifference` — a plain frozen dataclass, not an ORM
`Difference` row — so every comparator stays testable with bare `assert`s
and free of SQLAlchemy imports. A `Difference` row needs a `comparison_id`
FK that doesn't exist until the parent `ExperimentComparison` is built;
`engine.assemble_comparison` does that mechanical conversion once both
sides are known.

```python
RawDifference(category, field, old_value, new_value, difference_type,
               evidence_source, severity=LOW, confidence=MEDIUM)
```

`field` is a dotted path into the category's own data (e.g.
`"files.train.py"`, `"schema.age"`, `"other_seeds.random_state"`).
`evidence_source` names which provenance field(s) fed the comparison (e.g.
`"dataset.column_stats"`), for Phase 12's rationale and Phase 21's UI.

## Shared NOT_COMPARABLE / UNKNOWN / version-mismatch rule

Every one of the 5 provenance-based comparators calls
`resolve_missing_or_version_mismatch()` first, applying one rule
consistently:

| Condition | Status | Why |
|---|---|---|
| Both sides `None` | `NOT_COMPARABLE` | No evidence exists on either run — nothing to say beyond "we don't know." |
| Exactly one side `None` | `UNKNOWN` + one `MISSING_IN_BASE`/`MISSING_IN_COMPARE` difference | The side that *does* have the category is still informative — weaker than "can't compare at all." |
| Both present, `fingerprint_version` differs | `NOT_COMPARABLE` + one `VALUE_CHANGED` difference on `fingerprint_version` | Per `docs/FINGERPRINT_ALGORITHM.md`: a version mismatch is itself a signal, never papered over. |

If none of these apply, the comparator proceeds to its own fast-path hash
comparison. `metrics.py` (Phase 13) is the exception — its inputs are
plain `dict[str, float]` snapshots, not a versioned provenance dataclass,
so it applies its own two-case `None`/`None` → `NOT_COMPARABLE`, one-sided
`None` → `UNKNOWN` guard directly rather than calling
`resolve_missing_or_version_mismatch` (see `docs/METRIC_TOLERANCE.md`).

## Per-category comparators (`app/comparison/category_comparators/`)

Each returns a `<Category>ComparisonResult(status, differences)`. The 5
provenance-based comparators use their category's own fingerprint hash as
a SAME/DIFFERENT fast path, then (on DIFFERENT) diff the underlying
fields to explain why:

- **`code.py`** — fast path: `tree_fingerprint_hash`. On mismatch, diffs
  `files` by `relative_path` (`ADDED`/`REMOVED`/`VALUE_CHANGED` on
  `file_hash`). `vcs_present`, `git_commit_sha`, `git_branch`, `is_dirty`,
  `is_detached_head`, `is_shallow_clone` are **informative-only** — recorded
  when they differ but never flip the status, since the tree hash (not the
  commit SHA) is ground truth per `app/provenance/code.py`.
- **`dataset.py`** — fast path: `content_hash`. On mismatch, diffs
  `row_count`, `column_count`, `duplicate_row_count`, the `schema` dict
  (`ADDED`/`REMOVED`/`TYPE_CHANGED`), and per-column `column_stats`
  (`missing_count`/`distinct_count`/`mean`/`std`/`min`/`max`) — this is what
  catches "same row count, different content, same schema, different
  distribution." Comparison is **exact equality** throughout, no float
  tolerance — abs/rel tolerance is explicitly Phase 13's job (metric
  tolerance), not applied here to dataset stats.
- **`environment.py`** — fast path: `environment_fingerprint_hash`. On
  mismatch, diffs `os_name`/`os_version`/`architecture`/`python_version`,
  GPU/CUDA fields, and the `dependencies` list by package name
  (`ADDED`/`REMOVED`/`VALUE_CHANGED`). `hostname`, `cpu_model`, `cpu_count`,
  `ram_total_mb` are **informative-only**, enforcing the same
  hash-exclusion that `app/provenance/environment.py` already applies —
  two runs on different machines never appear "different" over descriptive
  metadata alone.
- **`configuration.py`** — fast path: `configuration_fingerprint_hash`. On
  mismatch, a recursive key-path diff over the two `raw` dicts, emitting one
  difference per changed leaf using dot-joined paths (e.g. `"model.C"`).
  Lists are treated as **atomic leaves**, not recursed element-by-element —
  consistent with `canonicalize.py`'s "lists are ordered sequences, not
  sets" stance; a documented limitation, not an oversight.
- **`randomness.py`** — fast path: `randomness_fingerprint_hash`. On
  mismatch, diffs `python_seed`, `numpy_seed`, the `other_seeds` dict, and
  `determinism_classification`/`determinism_intent`. An `other_seeds` value
  flipping between bound (an int) and unbound (`None`) is `Severity.HIGH`,
  matching `_classify_determinism`'s own treatment of that transition as
  decisive.
- **`metrics.py`** (Phase 13) — no fingerprint hash to fast-path on;
  instead applies a documented absolute/relative tolerance formula
  per-metric-key (see `docs/METRIC_TOLERANCE.md`). Unlike the other 5, it
  *does* assign `PARTIALLY_MATCHING` — for a metric within a configured
  tolerance but not exactly equal — since tolerance gives it an
  unambiguous, non-arbitrary boundary the other categories lack (see
  below).

## `PARTIALLY_MATCHING` at the provenance-category level

`ComparisonStatus.PARTIALLY_MATCHING` is deliberately unused by the 5
provenance-based comparators (code/dataset/environment/configuration/
randomness). Working through those categories, it never has an
unambiguous *single-category* meaning: "differs in N of M fields" is
already expressed by the differences list itself, and picking a threshold
for "partial" (how many changed keys make a configuration "partially"
matching rather than just "different"?) would be arbitrary. It reads more
naturally as a **cross-category** concept — e.g. "code matched but dataset
didn't" is partial reproducibility, which is a composite judgment across
all 5 categories, not a per-category one. That composite judgment belongs
to Phase 12 (reproducibility classification), which assigns
`PARTIALLY_REPRODUCIBLE`/`CONDITIONALLY_REPRODUCIBLE` at the
run-comparison level.

`metrics.py` (Phase 13) is the one exception, and it doesn't contradict
this reasoning: a *configured tolerance* is exactly the unambiguous,
non-arbitrary boundary the other categories lack, so "within tolerance
but not exact" has a precise, single-category meaning there that it never
had for e.g. "how many config keys changed."

## Scope deferred to later phases

- **`Difference.is_potential_contributor`** is always `False` on every row
  `assemble_comparison` produces. Ranking which differences actually
  explain a reproducibility failure is Phase 14 (REDUCED SCOPE, deferred).
  `False` reads as "not yet assessed," not "confirmed not a contributor."

## Orchestrator (`app/comparison/engine.py`)

`compare_experiments()` mirrors `assemble_experiment_fingerprint`'s flat
`base_*`/`compare_*` kwargs style, runs all 6 comparators, and
concatenates every category's differences into one `ComparisonResult`.
`base_metrics`/`compare_metrics` default to `None` (no `ExperimentRun`
column captures metric values yet — see `docs/METRIC_TOLERANCE.md`), so
callers that don't pass real metrics get `metrics_status = NOT_COMPARABLE`,
the same "no evidence on either side" convention every other category
already uses.

`assemble_comparison(result)` converts a `ComparisonResult` into an
**unattached** `ExperimentComparison` plus its `Difference` rows — no
`session.add()`/`commit()` here. `comparison.id` is generated eagerly via
`uuid.uuid4()` (rather than relying on the ORM column's `default=`, which
only runs at flush time) so the `Difference` rows can reference it as their
FK before anything is ever persisted.

`COMPARISON_ALGORITHM_VERSION = "1.0.0"`, matching the
`comparison_algorithm_version` column's default on `ExperimentComparison`.
