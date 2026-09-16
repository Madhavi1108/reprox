# Metric Tolerance

Status: implemented (Phase 13), unit-tested, MVP scope.

Spec section 29 requires configurable tolerances for comparing ML
metrics, since exact numerical equality is often inappropriate (94.27%
vs 94.25% "may be considered equivalent under a configured tolerance,"
while 94.27% vs 81.43% "should be classified differently"), and that "the
tolerance model must be documented and versioned" (this file; version
`METRIC_TOLERANCE_VERSION = "1.0.0"`, in
`app/comparison/category_comparators/metrics.py`).

## The formula

A metric pair `(old, new)` is **within tolerance** iff:

```
abs(old - new) <= max(abs_tolerance, rel_tolerance * max(abs(old), abs(new)))
```

This is the standard combined absolute/relative tolerance formula (the
same one `math.isclose` uses), made explicit here per the spec's
documentation requirement. `abs_tolerance` bounds the raw difference;
`rel_tolerance` scales the bound with the metrics' own magnitude, so the
same relative tolerance means a larger allowed gap for `loss=100.0` than
for `loss=0.01`.

## Zero-default design (no arbitrary threshold)

`ToleranceConfig.default_abs_tolerance` and `default_rel_tolerance` both
default to `0.0` — **exact equality is required unless a caller
explicitly configures a tolerance.** This is deliberate: the spec's own
example ("may be considered equivalent under a **configured**
tolerance") presupposes tolerance is an explicit choice a caller makes
for a specific metric, not a built-in guess REPROX silently applies. A
`ToleranceConfig` can also carry `per_metric: dict[str, tuple[abs, rel]]`
overrides — e.g. a looser tolerance for a noisy `loss` value and none at
all for a `row_count`-like metric that must match exactly.

## Per-metric classification

For each metric key present on both sides:

| Condition | Outcome | Severity |
|---|---|---|
| `old == new` | exact match, no difference recorded | — |
| different, within tolerance | difference recorded | `LOW` (tolerated) |
| different, outside tolerance | difference recorded | `HIGH` (real mismatch) |

A key present on only one side is `ADDED`/`REMOVED` at `Severity.MEDIUM`
— a metric appearing or disappearing between runs is itself informative,
independent of any tolerance.

## Aggregate status

Over the union of both sides' metric keys:

- Any outside-tolerance mismatch, or any added/removed key → `DIFFERENT`
- Else, any within-tolerance (but non-exact) difference → `PARTIALLY_MATCHING`
- Else (every key matched exactly, or both sides have no metrics at all) → `SAME`

`compare_metrics(None, None)` → `NOT_COMPARABLE`; `compare_metrics(None, {...})`
(or the reverse) → `UNKNOWN` with an explicit `MISSING_IN_BASE`/
`MISSING_IN_COMPARE` difference — the same missing-data convention the
other 5 comparators use, though implemented directly here rather than via
`resolve_missing_or_version_mismatch` (that helper expects a
`fingerprint_version` attribute; a plain metrics `dict` has none).

## Scope: what this module does not do

- **No metric capture/storage yet.** No `ExperimentRun` column stores
  captured metric values anywhere in the schema. `compare_metrics` takes
  plain `dict[str, float]` snapshots directly — it's ready to be pointed
  at real captured metrics once a later phase adds that storage, the same
  way Phase 9's artifact provenance was built ready for Phase 17's
  sandbox output before that sandbox existed.
- **Statistical tolerance / confidence intervals** (also named in spec
  section 29) are out of scope for this phase: both require
  distributional or repeated-sample data (e.g. multiple reruns, or a
  reported variance/standard error) that a single scalar metric snapshot
  does not carry. This is a documented scoping decision, not an
  oversight — analogous to the tracker's existing REDUCED SCOPE/OUT OF
  SCOPE calls for later phases.

## Wiring into the comparison engine

`app/comparison/engine.py::compare_experiments()` takes optional
`base_metrics`/`compare_metrics: dict[str, float] | None = None` and
`metrics_tolerance: ToleranceConfig = ToleranceConfig()` kwargs, calls
`compare_metrics(...)`, and sets `ComparisonResult.metrics_status`
directly from its result — no more hardcoded placeholder. Callers that
don't pass any metrics get `NOT_COMPARABLE`, consistent with every other
category's "no evidence on either side" convention.
