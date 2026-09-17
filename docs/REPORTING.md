# Reporting (Phase 26)

Status: implemented, **REDUCED SCOPE**, unit-tested (no live Postgres in
this dev environment).

## Spec requirement (§61, verbatim)

> Generate reproducibility reports. Include: 1. Experiment 2. Original run
> 3. Reproduction run 4. Code provenance 5. Dataset provenance 6. Pipeline
> provenance 7. Environment provenance 8. Configuration provenance
> 9. Randomness provenance 10. Artifact provenance 11. Metric comparison
> 12. Detected differences 13. Reproducibility classification
> 14. Potential contributors 15. Investigation results 16. Limitations
> 17. Evidence references. Never fabricate findings.

## Architecture: assembly-only, reuses everything, computes nothing new

`app/reporting/generator.py`'s `generate_report()` is a pure function over
already-computed data: it never re-derives a comparison status, a
difference, a reproducibility classification, or an evidence-strength
tier. It reuses Phase 14's `evidence_strength()` directly for potential
contributors, and passes `ReproducibilityAssessment.rationale_json`
through verbatim rather than re-explaining it. The only things this
module adds are (a) the assembly/shape and (b) explicit, honest
`reason`/`limitations` text wherever the underlying data doesn't exist -
never a fabricated finding in its place.

## Field-by-field mapping

| # | Spec field | Source | Availability caveat |
|---|---|---|---|
| 1 | Experiment | `Experiment` row via `original_run.experiment_id` | Always available. |
| 2 | Original run | `ExperimentRun` at `comparison.base_run_id` | Always available. |
| 3 | Reproduction run | `ExperimentRun` at `comparison.compare_run_id` | Always available. |
| 4 | Code provenance | `comparison.code_status` | Comparison-status granularity only - no persisted per-run snapshot (Phase 19). |
| 5 | Dataset provenance | `comparison.dataset_status` | Same as above. |
| 6 | Pipeline provenance | - | Always `NOT_AVAILABLE` - no comparator exists (Phase 21). |
| 7 | Environment provenance | `comparison.environment_status` | Comparison-status granularity only (Phase 19). |
| 8 | Configuration provenance | `comparison.configuration_status` | Comparison-status granularity only (Phase 19). |
| 9 | Randomness provenance | `comparison.randomness_status` | Comparison-status granularity only (Phase 19). |
| 10 | Artifact provenance | - | Always `NOT_AVAILABLE` - no comparator exists (Phase 21). |
| 11 | Metric comparison | `comparison.metrics_status` | Usually `NOT_COMPARABLE` - no metrics-storage column yet (Phase 13). |
| 12 | Detected differences | `comparison.differences` | Directly available. |
| 13 | Reproducibility classification | `ReproducibilityAssessment.classification`/`.rationale_json` | `available=False` if no assessment was ever produced for this comparison. |
| 14 | Potential contributors | `Difference.is_potential_contributor == True`, ranked via Phase 14's `evidence_strength()` | Empty if the comparison never triggered contributor ranking. |
| 15 | Investigation results | caller-supplied `InvestigationPlan`/`CounterfactualPlan` | `available=False` unless the caller resolves and supplies one (see below). |
| 16 | Limitations | static `REPORT_LIMITATIONS` tuple | Always fully populated - never conditionally omitted. |
| 17 | Evidence references | each difference's `evidence_source` + comparison/run identifiers | Directly available. |

## Why pipeline and artifact provenance are always unavailable

`DifferenceCategory` has no `PIPELINE` or `ARTIFACT` value - no comparator
was ever built for either category (Phase 21's comparison-UI tracker note
already established this gap: "Pipeline/Artifacts have no comparator").
Reporting a status for either would mean inventing one, which the spec's
own "Never fabricate findings" rules out. Both are reported as
`NOT_AVAILABLE` with a fixed reason instead.

## Why investigation/counterfactual results are caller-supplied

Phase 22's `InvestigationStore` and Phase 23's `CounterfactualStore` are
in-process stores keyed by their own randomly generated id, with no index
by `comparison_id` (documented reason: no reachable Postgres in this
environment to write and verify a migration against, so no DB table
exists for either). `generate_report()` cannot look a plan up for a given
comparison by itself, so it accepts an already-resolved
`InvestigationPlan`/`CounterfactualPlan` as an optional parameter - the
router resolves an `investigation_id`/`counterfactual_id` query param
against the relevant store and passes the result in. This mirrors Phase
24's `explain_comparison(comparison, reproducibility, provider)`
dependency-injection style rather than reimplementing store lookups
inside the generator.

## API

```
GET /api/v1/reports/{comparison_id}?investigation_id=<uuid>&counterfactual_id=<uuid>
```

- 404 if `comparison_id` doesn't resolve to an `ExperimentComparison`.
- `investigation_id`/`counterfactual_id` are optional. If supplied but
  unresolvable against their store, the report still generates - the
  corresponding section reports `available: false` with a `reason`
  rather than failing the whole request.

Sample response shape:

```json
{
  "report_version": "1.0.0",
  "comparison_id": "...",
  "experiment": {"id": "...", "name": "...", "description": null, "workload_type": "sklearn_tabular"},
  "original_run": {"id": "...", "run_type": "ORIGINAL", "status": "COMPLETED", "exit_code": 0, "started_at": "...", "finished_at": "..."},
  "reproduction_run": {"...": "..."},
  "provenance": [
    {"category": "code", "availability": "COMPARED", "status": "SAME", "reason": null},
    {"category": "pipeline", "availability": "NOT_AVAILABLE", "status": null, "reason": "No comparator exists for this category ..."}
  ],
  "metric_comparison": {"status": "NOT_COMPARABLE", "reason": "No ExperimentRun metrics-storage column exists yet ..."},
  "differences": ["..."],
  "reproducibility": {"available": true, "classification": "NOT_REPRODUCIBLE", "rationale": {"...": "..."}},
  "potential_contributors": ["..."],
  "investigation": {"available": false, "reason": "No matching investigation plan was supplied."},
  "counterfactual": {"available": false, "reason": "No matching counterfactual plan was supplied."},
  "limitations": ["..."],
  "evidence_references": ["provenance:environment", "comparison:...", "run:...", "run:..."],
  "generated_at": "..."
}
```

## "Never fabricate findings" - both directions

This constraint cuts two ways: REPROX must never invent a positive
finding it hasn't actually computed (e.g. a pipeline/artifact provenance
status, a metric delta it has no data for, a "confirmed" investigation
outcome), and it must never silently hide a known gap. The `limitations`
field exists specifically so a reader always sees exactly what this
report can and cannot vouch for, rather than being left to assume
completeness.

## Verification limitation

This dev environment has no reachable Postgres, so `GET
/api/v1/reports/{comparison_id}` is verified at the wiring/route-
registration level only (`test_api_app_wiring.py`); `generate_report()`
itself is fully unit-tested against mocked ORM objects
(`tests/unit/test_report_generator.py`, 10 tests). Real request/response
behavior against a live database is unverified here, consistent with
every phase since 15.
