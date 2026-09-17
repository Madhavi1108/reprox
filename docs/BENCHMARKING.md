# Benchmarking (Phase 28)

Status: implemented, **REDUCED SCOPE**, unit-tested.

## Spec requirements (verbatim)

> §63 RESEARCH BENCHMARK — Create a controlled benchmark dataset. Include
> experiments with: same/different code, same/different dataset,
> same/different environment, same/different configuration,
> same/different seed, dependency drift, dataset drift, schema drift,
> data split drift, hardware drift, multiple simultaneous changes,
> missing provenance, incomplete provenance, nondeterministic execution.
> The benchmark must be synthetic or openly reproducible. **Do not
> fabricate benchmark results.**

> §64 CONTROLLED EXPERIMENT SUITE — Build an experiment suite
> specifically for evaluating REPROX. Minimum: Experiment A (identical
> environment) → Reproducible; Experiment B (dataset modified) → Dataset
> difference detected; Experiment C (dependency changed) → Dependency
> difference detected; Experiment D (learning rate changed) →
> Configuration difference detected; Experiment E (random seed changed)
> → Randomness difference detected; Experiment F (code modified) → Code
> difference detected; Experiment G (multiple factors changed) →
> Multiple differences detected; Experiment H (provenance intentionally
> incomplete) → Insufficient evidence.

## Scope: 4 of 8 named experiments, no synthetic 19-dimension dataset generator

`docs/PHASE_TRACKER.md` row 28 recorded this scoping decision ahead of
implementation: build "a handful of concrete acceptance scenarios
(identical rerun, config-only change, dataset-only change, missing
provenance) instead of the full drift-type benchmark suite." This phase
implements exactly those four, mapping onto spec Experiments **A**, **D**,
**B**, and **H** respectively.

Experiments **C** (dependency drift), **E** (randomness changed), **F**
(code modified), and **G** (multiple simultaneous changes) are the same
pattern — a synthetic fixture pair run through the real comparison engine
— just not built in this pass. They are natural, low-effort extensions
of `app/benchmark/scenarios.py`, not gaps in the underlying approach.
Similarly, §63's full 19-dimension synthetic benchmark *dataset* (schema
drift, data split drift, hardware drift, nondeterministic execution,
etc.) is out of scope — this phase validates REPROX's own classification
logic against a handful of controlled scenarios, not a full external
benchmark corpus.

## Scenario table

| Scenario | Spec experiment | Mechanism | Expected | Actual (real, computed) |
|---|---|---|---|---|
| Identical rerun | A | Identical code/dataset/environment/configuration/seed, identical metrics on both sides | `EXACTLY_REPRODUCIBLE` | `EXACTLY_REPRODUCIBLE` |
| Dataset-only change | B | Only the compare side's CSV content differs | `DATASET` difference detected, all other categories `SAME` | `dataset_status=DIFFERENT`, all other categories `SAME` |
| Configuration-only change | D | Only the compare side's configuration dict differs | `CONFIGURATION` difference detected, all other categories `SAME` | `configuration_status=DIFFERENT`, all other categories `SAME` |
| Missing provenance | H | Compare side omits dataset and environment provenance entirely | `INSUFFICIENT_EVIDENCE` | `INSUFFICIENT_EVIDENCE` |

## Do not fabricate benchmark results

Every scenario in `app/benchmark/scenarios.py` builds real synthetic
fixtures on disk (a small git-less code directory, a real CSV file, a
real configuration dict) using Phases 4–8's actual capture functions
(`capture_code_provenance`, `capture_dataset_provenance`,
`capture_environment_provenance`, `capture_configuration_provenance`,
`capture_randomness_provenance` — the same pattern
`tests/unit/test_comparison_engine.py`'s `_capture_all()` helper already
uses), then runs them through Phase 11's real `compare_experiments()` and
Phase 12's real `classify_reproducibility()`. The `actual` field on each
`BenchmarkScenarioResult` is whatever those functions genuinely compute —
never a hand-authored string. If a future change to a comparator or the
classifier altered their behavior, the corresponding scenario test would
fail, not silently keep reporting a stale "actual" value.

## Verification

These scenarios run as part of the standard unit test suite
(`tests/unit/test_benchmark_scenarios.py`, 5 tests: one per scenario plus
`run_all_scenarios`'s own aggregate check). There is no separate
benchmark runner script or CLI — consistent with Phases 11–14 (the
comparison engine, classifier, metric tolerance, and contributor ranking)
also having no script surface, just tested pure functions. The test suite
is the benchmark's execution mechanism, and `pytest tests/unit` passing
is the "benchmark experiments execute successfully" evidence.
