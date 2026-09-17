# Evaluation Plan (Phase 32, spec-required, §65 Evaluation Metrics)

Status: new. Maps the spec's named metric list to what's actually
measurable in this codebase today — acceptance item 37 ("Evaluation
metrics are calculated from actual results") and item 38 ("Performance
measurements are actual") both require this to be honest about which
metrics have real numbers behind them and which don't, rather than
inventing plausible-looking figures.

## What's actually measured today

`app/benchmark/scenarios.py` (Phase 28) runs 4 real scenarios — identical
rerun, dataset-only change, config-only change, missing provenance —
through the genuine `compare_experiments()` (Phase 11) and
`classify_reproducibility()` (Phase 12) pipeline, using real synthetic
fixtures captured by Phases 4-8's actual capture functions, not
fabricated comparison results. From these, the following spec metrics
have real, computed values:

- **Reproducibility Classification Accuracy**: each scenario asserts the
  classifier reaches the expected classification
  (`EXACTLY_REPRODUCIBLE`/`INSUFFICIENT_EVIDENCE`/etc.) — 4/4 scenarios
  pass today (`backend/tests/unit/test_benchmark_scenarios.py`).
- **Code/Dataset/Environment/Configuration/Randomness Difference
  Detection Accuracy**: the dataset-only and config-only scenarios each
  assert category-level isolation — only the deliberately-varied category
  is flagged `DIFFERENT`, every other category correctly stays `SAME` —
  a direct, real measurement of detection precision for those two
  categories on these fixtures.
- **Fingerprint Collision Rate**: not separately benchmarked as a metric,
  but structurally bounded — `app/fingerprint/composite.py`'s composite
  hash is SHA-256 over 5 category hashes, giving the same collision-
  resistance guarantee as SHA-256 itself; no empirical collision study
  was run (would need a large corpus this environment doesn't have).

## What's explicitly not measured, and why

- **False Positive Rate / False Negative Rate / Contributor Ranking
  Quality**: would need a labeled ground-truth corpus of real
  reproducibility incidents to score against — the spec's own §63
  synthetic dataset generator (19 dimensions) was never built (Phase 28's
  documented scope reduction), so there's no corpus to run this against
  yet.
- **Schema Difference Detection Accuracy** and **Dependency Difference
  Detection Accuracy**: not covered by any of the 4 implemented benchmark
  scenarios (they cover dataset-content, environment, configuration —
  not schema-only or dependency-only drift specifically); the spec names
  8 benchmark experiments, only 4 are built (Phase 28).
- **Provenance Completeness**: computable in principle from
  `app/fingerprint/composite.py`'s explicit-null missing-component
  tracking (it already distinguishes "captured" from "missing" per
  category), but no phase aggregates this into a reported metric.
- **Query Latency, Comparison Latency, Storage Overhead, Execution
  Overhead**: genuinely require a reachable Postgres and/or Docker daemon
  under real load to measure — this dev environment has neither
  (`docs/OUT_OF_SCOPE.md`). Phase 30's DB-index and N+1-query work
  reduces query *shape* (proven by fixed-vs-scaling query-count tests,
  `docs/PERFORMANCE_OPTIMIZATION.md`) but was never measured as wall-clock
  latency against real data volume.

No number in this document or elsewhere in the codebase claims to be a
latency/overhead measurement that wasn't actually taken — where a metric
isn't measured, it's stated as unmeasured, per spec RULE 12 ("missing
[evidence] must result in uncertainty, not invented values").
