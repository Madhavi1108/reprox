# Counterfactual Experiments

Status: implemented (Phase 23) — **plan generation + result evaluation**,
unit- and wiring-tested. Execution is still not automated. Requested
explicitly by the user after being flagged (in Phase 22's summary) that
this phase has the same execution gap, more acutely.

Spec section 34 (`REPROX.pdf` page 31, verbatim):

> **§34 COUNTERFACTUAL EXPERIMENTS** — Support: What happens if we restore one changed factor? Example: Original: PyTorch 2.5. Reproduction: PyTorch 2.6. Counterfactual: PyTorch = 2.5, Everything else = reproduction environment. Execute. Compare results. If the result moves significantly toward the original, increase evidence supporting PyTorch as a contributor. Still do NOT claim causality without sufficient experimental support.

## Relationship to Phase 22 (Investigation Engine)

A counterfactual is the mirror image of an investigation:

| | Baseline | Varies |
|---|---|---|
| Investigation (Phase 22) | ORIGINAL | one factor, toward REPRODUCTION |
| Counterfactual (Phase 23) | REPRODUCTION | one factor, restored to ORIGINAL |

Both reuse the exact same candidate-selection algorithm —
`app.investigation.planner.select_contributor` (Phase 14's
evidence-strength lattice + deterministic tie-break) — factored out
during this phase so there is one selection algorithm, not two
copy-pasted ones.

## The split: plan generation vs. result evaluation

"Execute. Compare results." has two halves, with different buildability:

1. **Execute** — still not automatable. Identical limitation to Phase
   22: Phase 17's `SandboxRunner` runs one fixed Docker image against one
   fixed entrypoint script, with no mechanism to parameterize a single
   named factor (e.g. "use PyTorch 2.5 instead of 2.6") for one run.
2. **Compare results** — **is** buildable as a pure, deterministic
   function, *given* the actually-measured counterfactual value from
   wherever it came from (a human ran the suggested restoration
   manually, or a future Phase 17 extension executed it). This is new
   capability beyond Phase 22, not a repeat of the same gap — it follows
   the same "accept inline data since we can't derive it ourselves"
   pattern Phase 19 already established for `POST /runs/{id}/compare`'s
   provenance payloads.

## "Moved significantly": reusing Phase 13's tolerance, not a new threshold

`evaluate_counterfactual_result(original, reproduction, counterfactual, tolerance)`
reuses `app.comparison.category_comparators.metrics.within_tolerance` —
the exact same abs/rel tolerance formula Phase 13 already documented and
versioned, rather than inventing a second "significantly moved" scheme:

- Counterfactual value within tolerance of the **original** → it moved
  all the way back → `SUPPORTS_CONTRIBUTION`.
- Counterfactual value within tolerance of the **reproduction** → it
  didn't move at all → `DOES_NOT_SUPPORT`.
- Anything else (partway, or moved further away) → `INCONCLUSIVE`.

Tolerances default to `0.0` (exact match only), same as Phase 13's own
"no arbitrary threshold unless a caller explicitly configures one"
policy — verified by
`test_evaluate_defaults_to_exact_equality_without_configured_tolerance`.

## Never "confirmed"

Per spec's own caution ("Still do NOT claim causality without sufficient
experimental support"), `CounterfactualOutcome` has exactly 3 values —
`SUPPORTS_CONTRIBUTION`, `DOES_NOT_SUPPORT`, `INCONCLUSIVE` — deliberately
never "confirmed" or "validated." This matches Phase 14's four-state
ceiling: even a `SUPPORTS_CONTRIBUTION` outcome is still evidence toward
"Potential contributor," not a promotion to "Confirmed cause."

## No new database table

`CounterfactualStore` is in-process, mirroring Phase 22's
`InvestigationStore` — same rationale (no reachable Postgres in this
session to verify a migration against, and persisting a plan for a
workflow whose execution half isn't automated yet is premature schema).

## API

`POST /api/v1/counterfactuals` (body: `{comparison_id, counterfactual_metrics?}`)
and `GET /api/v1/counterfactuals/{id}` — the exact pair named in spec
§72's minimum endpoint list. If `counterfactual_metrics` names a metric
that also appears as a `METRICS` difference on the comparison (giving us
the real original/reproduction values), the response includes a computed
`outcome`; otherwise the plan is returned with `outcome: null` — "a
counterfactual has been proposed, not yet executed or evaluated."

## Verification limitation

Unit-tested (`backend/tests/unit/test_counterfactual.py`, 10 tests:
plan generation with the reproduction-baseline framing, candidate
selection parity with Phase 22, all 3 evaluation outcomes, exact-match
boundaries, and the zero-tolerance default) and wiring-tested (both
routes registered). Same caveat as every phase since 17: never exercised
against a real Postgres.
