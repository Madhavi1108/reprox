# Comparison UI

Status: implemented (Phase 21), build/lint-verified. Never rendered
against real data — see Verification limitation.

Spec section 55 (`REPROX.pdf` page 47, verbatim):

> **§55 COMPARISON UI** — Provide side-by-side comparison: ORIGINAL vs REPRODUCTION. Sections: Code, Dataset, Pipeline, Dependencies, Environment, Hardware, Configuration, Randomness, Artifacts, Metrics. Use: MATCH, DIFFERENCE, UNKNOWN with clear evidence.

Implemented as `frontend/src/pages/ComparisonPage.tsx`, route `/compare`.

## Section scope: 6 of 10

The spec lists 10 sections; only 6 have a corresponding category in
`ComparisonResult` (Phase 11): Code, Dataset, Environment, Configuration,
Randomness, Metrics.

| Spec section | Status |
|---|---|
| Code, Dataset, Environment, Configuration, Randomness, Metrics | Shown — each has a real `*_status` field and `Difference` rows |
| Dependencies, Hardware | Not separate sections — already nested inside `EnvironmentProvenance` and folded into the single `environment_status` (`docs/COMPARISON_ENGINE.md`) |
| Pipeline, Artifacts | No comparator exists anywhere in the backend for these — nothing to show |

This mirrors the "N of spec's list" honesty pattern already used
throughout the backend (Phase 16's provenance-graph node types, Phase
15's lineage edge types) — the UI only displays what the API actually
computes, documented rather than silently narrowed.

## Status vocabulary: 3 of 5

`ComparisonStatus` has 5 values; the spec wants exactly 3
(MATCH/DIFFERENCE/UNKNOWN). `StatusBadge` (`frontend/src/components/StatusBadge.tsx`)
maps:

| Backend `ComparisonStatus` | Badge |
|---|---|
| `SAME` | MATCH |
| `DIFFERENT` | DIFFERENCE |
| `UNKNOWN`, `NOT_COMPARABLE`, `PARTIALLY_MATCHING` | UNKNOWN |

The exact backend status is still shown as small print next to every
badge, so collapsing to the spec's 3-word vocabulary for the badge color/
label never actually loses information.

## No comparison-list endpoint — a form-driven page

Spec §72's minimum endpoint list has `POST /runs/{id}/compare` and
`GET /comparisons/{id}`, but no listing endpoint. So this page is a
single form: base run ID (ORIGINAL) + compare run ID (REPRODUCTION), plus
a collapsible "advanced" section accepting optional inline provenance
JSON per side (`RunProvenanceIn`, matching `backend/app/schemas/comparison.py`).
Without a payload, every category will honestly report
`NOT_COMPARABLE`/UNKNOWN — no phase yet persists real captured provenance
for a run (`docs/API.md`) — so the advanced section exists to actually
exercise the comparison logic from the browser.

On submit: `POST /runs/{base_id}/compare`, then `GET /reproducibility/{comparison_id}`
(Phase 12's classifier output — a natural companion needing no new
endpoint, shown as a banner above the per-category sections).

## "With clear evidence"

Each section's `Difference` rows are rendered as a table: field, old
value → new value, severity, confidence. `old_value`/`new_value` map
directly onto ORIGINAL/REPRODUCTION (`base_run`/`compare_run`) — this
*is* the side-by-side view the spec asks for, backed by the same
evidence Phase 11's comparators already computed.

## Verification limitation

Same as Phase 20: `npm run build` (`tsc -b` + `vite build`) and
`npm run lint` (`oxlint`) both pass, and the dev server was confirmed to
serve `/compare` (`200`, along with every other route, since this is a
client-side-routed SPA). **Real comparison rendering — the loading→ready
path with actual differences and a real reproducibility classification —
has never been exercised**, since no reachable Postgres exists in this
environment to run the backend against.
