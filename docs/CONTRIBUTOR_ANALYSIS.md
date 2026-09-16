# Contributor Analysis

Status: implemented (Phase 14), unit-tested, MVP scope.

Spec sections 31–32 (pulled directly from `REPROX.pdf` pages 28–30, since
the tracked `pages_out.txt` excerpt is missing these pages) require
REPROX to identify and rank which detected differences potentially
explain a reproducibility failure, without an LLM and with a
deterministic algorithm. Implemented in `app/contributor/ranking.py`
(`CONTRIBUTOR_RANKING_VERSION = "1.0.0"`), consuming Phase 11's
`ComparisonResult` and Phase 12's `ReproducibilityClassification`.

## The four-state model (spec section 31)

The spec requires distinguishing:

1. **Observed difference** — any `RawDifference` Phase 11/13 detected.
2. **Potential contributor** — a detected difference that *could*
   plausibly explain an observed outcome mismatch.
3. **Validated contributor** — a potential contributor whose causal role
   has been checked against a controlled rerun (Phase 33 — REPROX's
   "Controlled Investigation").
4. **Confirmed cause** — a validated contributor established with
   sufficient experimental support (Phase 34 — "Counterfactual
   Experiments").

> "Only the strongest state may be used when controlled evidence actually establishes it."

REPROX's MVP has no controlled-rerun or counterfactual-execution
infrastructure (tracker Phases 22/23, "Investigation engine" /
"Counterfactual engine", both already `OUT OF SCOPE for MVP`). Without
that evidence, states 3 and 4 are never reachable — `rank_contributors`
can only ever produce state 2, **Potential contributor**. This is the
correct, honest behavior per the spec's own instruction to use the
weaker state absent controlled evidence, not a shortcut.

## When ranking triggers

Per spec: "when results differ." `rank_contributors` only produces
contributors when the reproducibility classification is:

- `NOT_REPRODUCIBLE` — a confirmed outcome mismatch, or
- `PARTIALLY_REPRODUCIBLE` — an outcome that only partially matched.

The other 5 classifications don't warrant contributor analysis:
`EXACTLY_REPRODUCIBLE`/`REPRODUCIBLE_WITHIN_TOLERANCE`/
`CONDITIONALLY_REPRODUCIBLE` all have a matching outcome (nothing to
explain), and `INSUFFICIENT_EVIDENCE`/`NOT_COMPARABLE` have no outcome
evidence at all (nothing established to attribute anything to).

## What's eligible

Only differences in the 5 provenance categories (code, dataset,
environment, configuration, randomness) are candidates. A `METRICS`
difference *is* the observed outcome difference itself (e.g. the
accuracy delta) — it's the effect being explained, never a contributor
to itself, so it's always excluded and never marked
`is_potential_contributor`.

## Evidence-strength formula (spec section 32)

Spec section 32 lists 7 potential ranking inputs: difference magnitude,
historical evidence, known sensitivity, experiment context, dependency
relationship, correlation, controlled rerun evidence — and requires "Do
not use an LLM-generated arbitrary ranking. The algorithm must be
deterministic where possible."

**Only difference magnitude is implemented.** It's already captured:
every `RawDifference` (Phases 11/13) carries a `severity`
(LOW/MEDIUM/HIGH/CRITICAL) and `confidence` (LOW/MEDIUM/HIGH), assigned
per-comparator based on exactly this kind of magnitude judgment (e.g. a
GPU/schema change is `HIGH` severity; a hostname difference is `LOW`).
The formula combines them into the spec's own vocabulary
(`HIGH`/`MODERATE`/`LOW` evidence strength):

```
severity_tier(severity)     = LOW→LOW, MEDIUM→MODERATE, HIGH/CRITICAL→HIGH
confidence_gate(confidence) = LOW→MODERATE (caps), MEDIUM→HIGH, HIGH→HIGH
evidence_strength            = min(severity_tier, confidence_gate)
```

Severity sets the base tier; confidence can only hold or downgrade it,
never upgrade it — a `HIGH`-severity but `LOW`-confidence difference is
capped at `MODERATE`, since low confidence in the underlying evidence
means we shouldn't call it `HIGH`. Full lattice:

| severity \ confidence | LOW | MEDIUM | HIGH |
|---|---|---|---|
| LOW | LOW | LOW | LOW |
| MEDIUM | MODERATE | MODERATE | MODERATE |
| HIGH | MODERATE | HIGH | HIGH |
| CRITICAL | MODERATE | HIGH | HIGH |

## Ranking order

Eligible differences are sorted by `(severity desc, confidence desc,
category name, field name)` — the last two are a stable alphabetical
tie-break, so any given input has exactly one valid ranking, never an
arbitrary one. Ranks are assigned `1..N` contiguously over eligible
differences only.

## Explicitly out of scope (the other 6 spec-listed inputs)

| Input | Why deferred |
|---|---|
| Historical evidence | No historical run/comparison store exists yet — there's nowhere to look up "has this kind of difference caused failures before." |
| Known sensitivity | No sensitivity registry (e.g. "this hyperparameter is known to be noise-sensitive") exists yet. |
| Experiment context | No mechanism captures broader experiment metadata beyond the 6 comparison categories. |
| Dependency relationship | Would require a dependency graph between provenance categories (e.g. "CUDA version depends on GPU driver") that isn't modeled. |
| Correlation | Requires statistics across many past comparisons; no such analysis pipeline exists. |
| Controlled rerun evidence | Requires Phase 22 (controlled investigation) and Phase 23 (counterfactual experiments), both explicitly `OUT OF SCOPE for MVP`. |

These are genuine infrastructure gaps, not omissions within this phase —
consistent with the tracker's existing `REDUCED SCOPE`/`OUT OF SCOPE`
pattern for Phases 14 (this one, partially), 22, 23, 25–27, 30.

## Wiring

`rank_contributors(comparison: ComparisonResult, classification:
ReproducibilityClassification) -> ContributorRankingResult` is a pure
function — no DB session touched, matching Phases 10–13's style.
`ContributorRankingResult.ranked_differences` is in the same order as
`comparison.differences` (one `RankedDifference` per input), so
`app.comparison.engine.assemble_comparison(result, ranking=...)` can zip
them by index to set each `Difference.is_potential_contributor` — an
optional parameter; omitting it keeps Phase 11's original behavior
(`False` for every row), so no existing caller breaks. End-to-end wiring
(comparison → classification → ranking → assembly → persistence) is
Phase 19's job (FastAPI).
