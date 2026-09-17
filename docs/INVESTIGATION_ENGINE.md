# Investigation Engine

Status: implemented (Phase 22) — **plan generation only**, unit- and
wiring-tested. Never run against a live database (same limitation as
every phase since 17). Requested explicitly by the user despite being
previously scoped `OUT OF SCOPE for MVP`.

Spec sections 33 and 35 (`REPROX.pdf` pages 30 and 32, verbatim):

> **§33 CONTROLLED INVESTIGATION** — Support controlled reproduction experiments. Example: Original: PyTorch 2.5. Reproduction: PyTorch 2.6. REPROX may generate an investigation: Change ONLY PyTorch version. Keep: Code = same, Dataset = same, Configuration = same, Seed = same, Hardware = same. Then run the experiment. This allows controlled evidence collection.
>
> **§35 ONE-VARIABLE-AT-A-TIME INVESTIGATION** — Support controlled isolation: Experiment A → Change ONE variable → Run → Compare. This allows contributor analysis.

(§34, Counterfactual Experiments, is the separate Phase 23 — still out of
scope, not built here.)

## Why this is plan generation only, not a closed loop

"Generate an investigation... then run the experiment" has two halves:

1. **Generate the plan** — identify the single highest-evidence-strength
   factor to vary, and what to hold constant. **Built.** Reuses Phase
   14's evidence-strength lattice directly
   (`app.contributor.ranking.evidence_strength`, made public for this
   phase rather than duplicated).
2. **Actually run the experiment, varying only that one factor** — **not
   built, and not buildable as a small extension.** Phase 17's
   `SandboxRunner` executes one fixed Docker image
   (`config.sandbox_image`) against one fixed `entrypoint_script`. There
   is no mechanism anywhere in the codebase to say "use PyTorch 2.6
   instead of 2.5 for this one run" — that would require either a
   per-run custom image build step or a package-override injection
   mechanism, neither of which exists. Building one now would be a
   separate, larger infrastructure project.

Per spec §34's own caution ("do NOT claim causality without sufficient
experimental support") and Phase 14's four-state model (Observed /
Potential contributor / Validated contributor / Confirmed cause): an
`InvestigationPlan` is a prerequisite artifact for eventually reaching
"Validated" — never a validation itself, since REPROX still cannot
execute the controlled rerun that would validate anything. Generating a
plan REPROX can't yet execute and calling it "done" would overclaim;
this document says so explicitly instead.

## Plan generation (`app/investigation/planner.py`)

`generate_investigation_plan(comparison_id, base_run_id, compare_run_id, differences)`:

- Filters to differences where `is_potential_contributor` is true (Phase
  14's output) **and** the category is controllable — `CODE`, `DATASET`,
  `ENVIRONMENT`, `CONFIGURATION`, `RANDOMNESS`. `METRICS` is the observed
  outcome, never a candidate to change.
- Picks the single highest `evidence_strength` candidate, with the exact
  same deterministic tie-break Phase 14 uses (severity desc, confidence
  desc, category, field) — one algorithm, one source of truth, reused
  rather than reimplemented.
- `held_constant` = every other controllable category. Matches §33's own
  vocabulary: "Seed" = `RANDOMNESS`, "Hardware" is folded into
  `ENVIRONMENT` (per `docs/COMPARISON_ENGINE.md`'s environment
  comparator, which already treats CPU/GPU/RAM as part of that one
  category).
- Returns `None` when there's nothing to investigate — no potential
  contributors at all (e.g. an `EXACTLY_REPRODUCIBLE` comparison never
  triggered Phase 14's ranking in the first place).

## No new database table

`InvestigationStore` is an in-process store (`app/investigation/planner.py`),
mirroring Phase 18's `JobTracker` — no migration was written. Two
reasons, not one: (a) no reachable Postgres exists in this session to
verify a migration against (same limitation as Phases 15/16/18), and (b)
persisting a plan that can never actually be executed would add schema
for a workflow that's intentionally half-built — premature until Phase
17's sandbox gains per-factor parameterization.

## API

`POST /api/v1/investigations` (body: `{comparison_id}`) and
`GET /api/v1/investigations/{id}` — the exact pair named in spec §72's
minimum endpoint list. `POST` loads the `ExperimentComparison` and its
persisted `Difference` rows, calls the planner, stores the result, and
returns it; a comparison with no potential contributors yields `422`
(`validation_failed`), not a fabricated plan.

## Verification limitation

Unit-tested (`backend/tests/unit/test_investigation_planner.py`, 7 tests:
correct candidate selection, `held_constant` correctness, `METRICS`
exclusion, non-contributor exclusion, empty input, deterministic
tie-break, and reference/id integrity) and wiring-tested (both routes
registered, per `test_api_app_wiring.py`). Like every phase since 17, the
API routes have never been exercised against a real Postgres — the same
"wiring/logic only" caveat as Phase 19's `docs/API.md`.
