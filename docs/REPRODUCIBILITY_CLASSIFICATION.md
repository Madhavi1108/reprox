# Reproducibility Classification

Status: implemented (Phase 12), unit-tested, MVP scope.

Phase 12 consumes Phase 11's `ComparisonResult` and produces a single
`ReproducibilityClassification` verdict plus a structured `rationale` dict
explaining which rule fired and why. Per spec section 28: "Do not use
arbitrary thresholds. Define the mathematical/statistical basis for
determining each category." The classifier below uses only categorical
logic over `ComparisonStatus` values — no numeric thresholds anywhere.
Same style as Phase 10/11: a pure function
(`app/reproducibility/classifier.py:classify_reproducibility`), no DB
session touched. `assemble_reproducibility_assessment` builds an
unattached `ReproducibilityAssessment` ORM row; wiring a real session is
Phase 19's job.

## The two axes

**Outcome axis** — `metrics_status`, i.e. did the actual measured result
match?

| `metrics_status` | Meaning |
|---|---|
| `SAME` | exact match |
| `PARTIALLY_MATCHING` | matched within tolerance, not exact (Phase 13 will start producing this — metrics comparison isn't built yet) |
| `DIFFERENT` | mismatch outside tolerance |
| `UNKNOWN` / `NOT_COMPARABLE` | no outcome evidence at all |

**Setup axis** — aggregated over the 5 provenance categories (code,
dataset, environment, configuration, randomness): was the causal setup
identical?

| Value | Condition |
|---|---|
| `FULL` | all 5 categories are `SAME` |
| `CHANGED_OR_DEGRADED` | anything else — at least one confirmed `DIFFERENT`, or some mix of `SAME`/`UNKNOWN`/`NOT_COMPARABLE` with no verified `DIFFERENT` but incomplete confirmation |

`CHANGED_OR_DEGRADED` deliberately collapses "we know it changed" and "we
can't confirm it didn't change" into one bucket: in both cases the setup
is not verified-identical, so neither exact reproduction claim
(`EXACTLY_REPRODUCIBLE`/`REPRODUCIBLE_WITHIN_TOLERANCE`) is warranted.

## Decision table

Rules are evaluated in this priority order; the first match wins.

| # | Condition | Classification | Rationale |
|---|---|---|---|
| 1 | All 6 category statuses are `NOT_COMPARABLE` | `NOT_COMPARABLE` | Total evidence blackout — nothing exists on either side for anything. |
| 2 | Outcome is `UNKNOWN`/`NOT_COMPARABLE` (and rule 1 didn't match) | `INSUFFICIENT_EVIDENCE` | Reproducibility is fundamentally a claim about the outcome. With no outcome evidence, no verdict is possible no matter how clean the setup comparison looks. |
| 3 | Outcome is `DIFFERENT` | `NOT_REPRODUCIBLE` | A confirmed outcome mismatch is decisive, unconditionally — regardless of setup. |
| 4a | Outcome is `SAME`, setup is `FULL` | `EXACTLY_REPRODUCIBLE` | Identical setup, identical outcome — the strongest possible claim. |
| 4b | Outcome is `SAME`, setup is `CHANGED_OR_DEGRADED` | `CONDITIONALLY_REPRODUCIBLE` | The result held despite an unverified or actually-changed input — reproducible conditional on that factor not mattering. |
| 5a | Outcome is `PARTIALLY_MATCHING`, setup is `FULL` | `REPRODUCIBLE_WITHIN_TOLERANCE` | Identical setup, near-exact outcome. |
| 5b | Outcome is `PARTIALLY_MATCHING`, setup is `CHANGED_OR_DEGRADED` | `PARTIALLY_REPRODUCIBLE` | Neither axis is clean — partial confidence on both setup and outcome. |

This table is exhaustive: the outcome axis has exactly 4 partitions of
`ComparisonStatus` (`SAME`, `PARTIALLY_MATCHING`, `DIFFERENT`,
`{UNKNOWN, NOT_COMPARABLE}`) and each is handled by exactly one rule
(2, 5, 3, 4 respectively — rule 1 is a special case nested inside the
`{UNKNOWN, NOT_COMPARABLE}` outcome partition that ranks first because it
represents an even stronger absence of evidence). No case falls through
un-classified.

## Why most classifications land in `NOT_COMPARABLE` / `INSUFFICIENT_EVIDENCE` today

`app/comparison/engine.py::compare_experiments` currently hardcodes
`metrics_status = ComparisonStatus.UNKNOWN` on every comparison, because
real metric-tolerance comparison is Phase 13's job and hasn't been built
yet. Rule 2 (and, in the total-absence case, rule 1) therefore fires on
essentially every real comparison run through the system today. This is
the *correct*, honest behavior: REPROX cannot yet verify whether an
experiment's actual output reproduced, so it must not claim otherwise —
regardless of how identical the code/dataset/environment/configuration/
randomness inputs are. Once Phase 13 starts populating `metrics_status`
with real `SAME`/`PARTIALLY_MATCHING`/`DIFFERENT` values, rules 3–5 will
begin firing without any change to this module.

## `rationale` structure

Every `ClassificationResult.rationale` dict has the same shape, recorded
on the persisted `ReproducibilityAssessment.rationale_json` column:

```python
{
    "rule": "exact_outcome_full_setup",        # which table row fired
    "outcome": "SAME",                          # metrics_status value
    "setup": "FULL",                            # setup axis value, or None for rules 1/2
    "category_statuses": {                      # every category's raw status, for audit
        "code_status": "SAME",
        "dataset_status": "SAME",
        "environment_status": "SAME",
        "configuration_status": "SAME",
        "randomness_status": "SAME",
        "metrics_status": "SAME",
    },
}
```

## Scope deferred to later phases

- Real `metrics_status` values (Phase 13 — metric tolerance).
- Using `Difference.is_potential_contributor` / ranking which differences
  actually caused a `NOT_REPRODUCIBLE`/`PARTIALLY_REPRODUCIBLE` verdict
  (Phase 14, REDUCED SCOPE, deferred).
- A separate numeric reproducibility *score* (spec section 30) is
  explicitly required to never replace this classification — no such
  score is computed anywhere in this phase.
