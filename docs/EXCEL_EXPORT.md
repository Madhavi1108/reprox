# Excel Export (Phase 27)

Status: implemented, **REDUCED SCOPE**, unit-tested (no live Postgres in
this dev environment).

## Spec requirement (§62, verbatim)

> Support Excel export using: openpyxl. Workbook sheets: Experiments,
> Runs, Code, Datasets, Data Splits, Pipelines, Environments,
> Dependencies, Configurations, Randomness, Metrics, Artifacts,
> Differences, Reproducibility, Investigations, Lineage, Reports. Excel
> output must use the same domain services as the API. Do not implement
> separate business logic for Excel.

## Architecture: reuses domain services, computes nothing new

`app/export/excel.py`'s `build_workbook()` assembles one `openpyxl`
workbook entirely from existing domain access:

- Flat-table sheets (Experiments, Runs, Code, Datasets, Environments,
  Dependencies, Configurations, Randomness, Metrics, Artifacts,
  Differences, Reproducibility) are direct `db.query(Model).all()` reads —
  the same class of query glue already used directly inside
  `dashboard.py`, `provenance.py`, and `lineage.py`'s routers. This is
  data access, not the "separate business logic" the spec forbids.
- The Lineage sheet reuses Phase 15's `build_lineage_graph()` exactly,
  fed by the same per-experiment sibling-run/comparison query
  `GET /lineage/{run_id}` already performs, just looped over every
  experiment instead of one run.
- The Reports sheet reuses Phase 26's `generate_report()` exactly, called
  once per `ExperimentComparison` with `investigation_plan=None,
  counterfactual_plan=None` (no comparison-scoped id is available in a
  bulk export context — the same soft-unavailable behavior
  `GET /reports/{comparison_id}` already supports for an omitted query
  param).
- The Investigations sheet reads Phase 22/23's `InvestigationStore`/
  `CounterfactualStore` via a new `list_all()` accessor on each — a
  trivial enumeration, not new business logic, the same shape as their
  existing `.get()` method.

No new computation, no new classification, no new ranking. The Excel
export never diverges from what the API already computes.

## Per-sheet source table

| # | Sheet | Source | Key columns |
|---|---|---|---|
| 1 | Experiments | `Experiment` table | id, project_id, name, description, workload_type, created_at |
| 2 | Runs | `ExperimentRun` table | id, experiment_id, run_type, parent_run_id, status, exit_code, started_at, finished_at |
| 3 | Code | `CodeSnapshot` table | id, run_id, git_commit_sha, is_dirty, tree_fingerprint_hash, file_count |
| 4 | Datasets | `DatasetVersion` table (+ related `Dataset.name`) | id, dataset_name, content_hash, row_count, column_count |
| 5 | Data Splits | none | fixed `NOT_AVAILABLE` reason row |
| 6 | Pipelines | none | fixed `NOT_AVAILABLE` reason row |
| 7 | Environments | `Environment` table | id, run_id, os_name, python_version, gpu_present, environment_fingerprint_hash |
| 8 | Dependencies | `Dependency` table | id, environment_id, package_name, version |
| 9 | Configurations | `Configuration` table | id, run_id, configuration_fingerprint_hash, canonical_json |
| 10 | Randomness | `RandomnessProfile` table | id, run_id, python_seed, numpy_seed, determinism_classification |
| 11 | Metrics | `Metric` table | id, run_id, name, value, captured_at |
| 12 | Artifacts | `Artifact` table | id, run_id, artifact_type, file_path, content_hash, size_bytes |
| 13 | Differences | `Difference` table | id, comparison_id, category, field, old_value, new_value, severity, confidence, is_potential_contributor |
| 14 | Reproducibility | `ReproducibilityAssessment` table | id, comparison_id, classification, algorithm_version, created_at |
| 15 | Investigations | `InvestigationStore.list_all()` + `CounterfactualStore.list_all()` | id, comparison_id, kind, category, field, evidence_strength, outcome |
| 16 | Lineage | per-experiment `build_lineage_graph()` | experiment_id, from_run_id, to_run_id, edge_type |
| 17 | Reports | per-comparison `generate_report()` | comparison_id, experiment_name, classification, metrics_status, report_json |

## Gaps

**Always empty by design** — no backing model or comparator exists:
- Data Splits: no `DataSplit`-shaped model anywhere in the schema.
- Pipelines: `DifferenceCategory` has no PIPELINE value — the same gap
  Phase 21's comparison UI and Phase 26's Reporting already document.

**Currently empty in practice** — real Phase 2 tables that no phase
writes to yet: Code, Datasets, Environments, Dependencies,
Configurations, Randomness, Metrics, Artifacts. These sheets are queried
correctly and will populate as soon as a future phase wires provenance
ingestion into them. This is the same documented gap as
`GET /api/v1/provenance/{run_id}` (see `app/api/v1/routers/provenance.py`).

## API

```
GET /api/v1/exports/excel
```

Streams an `.xlsx` file (`Content-Type:
application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`,
`Content-Disposition: attachment; filename=reprox_export.xlsx`). No
query parameters — this is a single full-database export, matching every
other bulk query in this codebase (dashboard, provenance, lineage) being
unfiltered and unpaginated. No row-count cap, for the same consistency
reason. No 404 path: exporting an all-empty database is a valid, honest
result.

## Verification limitation

This dev environment has no reachable Postgres, so `build_workbook()` is
unit-tested against mocked ORM objects only
(`tests/unit/test_excel_export.py`); the actual downloaded `.xlsx` file
has never been opened in Excel/LibreOffice against real data in this
session. `GET /api/v1/exports/excel` is verified at the wiring/route-
registration level (`test_api_app_wiring.py`) and via a successful
OpenAPI schema generation check, consistent with every phase since 15.
