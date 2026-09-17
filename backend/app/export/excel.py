"""Excel export (Phase 27, spec section 62).

"Support Excel export using: openpyxl. Workbook sheets: Experiments,
Runs, Code, Datasets, Data Splits, Pipelines, Environments, Dependencies,
Configurations, Randomness, Metrics, Artifacts, Differences,
Reproducibility, Investigations, Lineage, Reports. Excel output must use
the same domain services as the API. Do not implement separate business
logic for Excel."

This module computes nothing new. Flat-table sheets are direct
`db.query(Model).all()` reads - the same class of query glue every prior
router already uses (`dashboard.py`, `provenance.py`, `lineage.py`), not
"separate business logic." The three sheets with real domain logic behind
them call the exact functions the API already calls: Phase 15's
`build_lineage_graph()` for Lineage, Phase 26's `generate_report()` for
Reports, and Phase 22/23's `InvestigationStore`/`CounterfactualStore` for
Investigations.

Known gaps, reported honestly rather than fabricated:
- "Data Splits" and "Pipelines" have no backing model or comparator
  anywhere in this codebase (Phase 21's scoping note - `DifferenceCategory`
  has no PIPELINE value, and no DataSplit-shaped model was ever built).
  Both sheets ship header-only plus one fixed reason row.
- Code/Datasets/Environments/Dependencies/Configurations/Randomness/
  Metrics/Artifacts query real Phase 2 tables that no phase currently
  writes to (same gap `app/api/v1/routers/provenance.py` already
  documents for `/provenance/{run_id}`) - present, correctly queried,
  honestly empty until a future phase wires ingestion.
- Investigations/Counterfactuals live only in Phase 22/23's in-process
  stores (no DB table, no reachable Postgres in this environment to
  verify a migration against) - `list_all()` was added to each store as
  a trivial accessor, not new business logic, mirroring their existing
  `.get()` method.
"""

from __future__ import annotations

import json
import uuid

from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.db.models.comparison import Difference, ExperimentComparison, ReproducibilityAssessment
from app.db.models.core import Experiment, ExperimentRun
from app.db.models.provenance import (
    Artifact,
    CodeSnapshot,
    Configuration,
    DatasetVersion,
    Dependency,
    Environment,
    Metric,
    RandomnessProfile,
)
from app.investigation.counterfactual import CounterfactualPlan, get_counterfactual_store
from app.investigation.planner import InvestigationPlan, get_investigation_store
from app.lineage.graph import ComparisonLink, LineageEdge, RunNode, build_lineage_graph
from app.reporting.generator import generate_report

_NOT_AVAILABLE_REASON_PIPELINE_LIKE = (
    "NOT_AVAILABLE - no model or comparator exists for this category "
    "(Phase 21 scoping note)."
)


def _write_sheet(wb: Workbook, title: str, headers: list[str], rows: list[list]) -> None:
    ws = wb.create_sheet(title=title)
    ws.append(headers)
    for row in rows:
        ws.append(row)


def _build_experiments_sheet(wb: Workbook, experiments: list[Experiment]) -> None:
    _write_sheet(
        wb,
        "Experiments",
        ["id", "project_id", "name", "description", "workload_type", "created_at"],
        [
            [str(e.id), str(e.project_id), e.name, e.description, e.workload_type, e.created_at]
            for e in experiments
        ],
    )


def _build_runs_sheet(wb: Workbook, runs: list[ExperimentRun]) -> None:
    _write_sheet(
        wb,
        "Runs",
        [
            "id",
            "experiment_id",
            "run_type",
            "parent_run_id",
            "status",
            "exit_code",
            "started_at",
            "finished_at",
        ],
        [
            [
                str(r.id),
                str(r.experiment_id),
                r.run_type.value,
                str(r.parent_run_id) if r.parent_run_id else None,
                r.status.value,
                r.exit_code,
                r.started_at,
                r.finished_at,
            ]
            for r in runs
        ],
    )


def _build_code_sheet(wb: Workbook, snapshots: list[CodeSnapshot]) -> None:
    _write_sheet(
        wb,
        "Code",
        ["id", "run_id", "git_commit_sha", "is_dirty", "tree_fingerprint_hash", "file_count"],
        [
            [str(s.id), str(s.run_id), s.git_commit_sha, s.is_dirty, s.tree_fingerprint_hash, s.file_count]
            for s in snapshots
        ],
    )


def _build_datasets_sheet(wb: Workbook, versions: list[DatasetVersion]) -> None:
    _write_sheet(
        wb,
        "Datasets",
        ["id", "dataset_name", "content_hash", "row_count", "column_count"],
        [
            [str(v.id), v.dataset.name, v.content_hash, v.row_count, v.column_count]
            for v in versions
        ],
    )


def _build_data_splits_sheet(wb: Workbook) -> None:
    _write_sheet(
        wb,
        "Data Splits",
        ["reason"],
        [[_NOT_AVAILABLE_REASON_PIPELINE_LIKE]],
    )


def _build_pipelines_sheet(wb: Workbook) -> None:
    _write_sheet(
        wb,
        "Pipelines",
        ["reason"],
        [[_NOT_AVAILABLE_REASON_PIPELINE_LIKE]],
    )


def _build_environments_sheet(wb: Workbook, environments: list[Environment]) -> None:
    _write_sheet(
        wb,
        "Environments",
        ["id", "run_id", "os_name", "python_version", "gpu_present", "environment_fingerprint_hash"],
        [
            [str(e.id), str(e.run_id), e.os_name, e.python_version, e.gpu_present, e.environment_fingerprint_hash]
            for e in environments
        ],
    )


def _build_dependencies_sheet(wb: Workbook, dependencies: list[Dependency]) -> None:
    _write_sheet(
        wb,
        "Dependencies",
        ["id", "environment_id", "package_name", "version"],
        [[str(d.id), str(d.environment_id), d.package_name, d.version] for d in dependencies],
    )


def _build_configurations_sheet(wb: Workbook, configurations: list[Configuration]) -> None:
    _write_sheet(
        wb,
        "Configurations",
        ["id", "run_id", "configuration_fingerprint_hash", "canonical_json"],
        [
            [str(c.id), str(c.run_id), c.configuration_fingerprint_hash, c.canonical_json[:500]]
            for c in configurations
        ],
    )


def _build_randomness_sheet(wb: Workbook, profiles: list[RandomnessProfile]) -> None:
    _write_sheet(
        wb,
        "Randomness",
        ["id", "run_id", "python_seed", "numpy_seed", "determinism_classification"],
        [
            [str(p.id), str(p.run_id), p.python_seed, p.numpy_seed, p.determinism_classification.value]
            for p in profiles
        ],
    )


def _build_metrics_sheet(wb: Workbook, metrics: list[Metric]) -> None:
    _write_sheet(
        wb,
        "Metrics",
        ["id", "run_id", "name", "value", "captured_at"],
        [[str(m.id), str(m.run_id), m.name, float(m.value), m.captured_at] for m in metrics],
    )


def _build_artifacts_sheet(wb: Workbook, artifacts: list[Artifact]) -> None:
    _write_sheet(
        wb,
        "Artifacts",
        ["id", "run_id", "artifact_type", "file_path", "content_hash", "size_bytes"],
        [
            [str(a.id), str(a.run_id), a.artifact_type.value, a.file_path, a.content_hash, a.size_bytes]
            for a in artifacts
        ],
    )


def _build_differences_sheet(wb: Workbook, differences: list[Difference]) -> None:
    _write_sheet(
        wb,
        "Differences",
        [
            "id",
            "comparison_id",
            "category",
            "field",
            "old_value",
            "new_value",
            "severity",
            "confidence",
            "is_potential_contributor",
        ],
        [
            [
                str(d.id),
                str(d.comparison_id),
                d.category.value,
                d.field,
                d.old_value,
                d.new_value,
                d.severity.value,
                d.confidence.value,
                d.is_potential_contributor,
            ]
            for d in differences
        ],
    )


def _build_reproducibility_sheet(wb: Workbook, assessments: list[ReproducibilityAssessment]) -> None:
    _write_sheet(
        wb,
        "Reproducibility",
        ["id", "comparison_id", "classification", "algorithm_version", "created_at"],
        [
            [str(a.id), str(a.comparison_id), a.classification.value, a.algorithm_version, a.created_at]
            for a in assessments
        ],
    )


def _build_investigations_sheet(
    wb: Workbook,
    investigations: list[InvestigationPlan],
    counterfactuals: list[CounterfactualPlan],
) -> None:
    rows = [
        [
            str(i.id),
            str(i.comparison_id),
            "INVESTIGATION",
            i.changed_category.value,
            i.changed_field,
            i.evidence_strength.value,
            None,
        ]
        for i in investigations
    ] + [
        [
            str(c.id),
            str(c.comparison_id),
            "COUNTERFACTUAL",
            c.restored_category.value,
            c.restored_field,
            c.evidence_strength.value,
            c.outcome.value if c.outcome is not None else None,
        ]
        for c in counterfactuals
    ]
    _write_sheet(
        wb,
        "Investigations",
        ["id", "comparison_id", "kind", "category", "field", "evidence_strength", "outcome"],
        rows,
    )


def _build_lineage_sheet(wb: Workbook, edges_by_experiment: list[tuple[uuid.UUID, LineageEdge]]) -> None:
    _write_sheet(
        wb,
        "Lineage",
        ["experiment_id", "from_run_id", "to_run_id", "edge_type"],
        [
            [str(experiment_id), str(edge.from_run_id), str(edge.to_run_id), edge.edge_type.value]
            for experiment_id, edge in edges_by_experiment
        ],
    )


def _build_reports_sheet(wb: Workbook, reports: list[tuple[ExperimentComparison, object]]) -> None:
    rows = []
    for comparison, report in reports:
        rows.append(
            [
                str(comparison.id),
                report.experiment["name"],
                report.reproducibility.classification,
                report.metric_comparison.status,
                json.dumps(_report_to_dict(report), default=str),
            ]
        )
    _write_sheet(wb, "Reports", ["comparison_id", "experiment_name", "classification", "metrics_status", "report_json"], rows)


def _report_to_dict(report) -> dict:
    from dataclasses import asdict

    return asdict(report)


def _lineage_edges_for_experiments(db: Session) -> list[tuple[uuid.UUID, LineageEdge]]:
    experiments = db.query(Experiment).all()
    edges_by_experiment: list[tuple[uuid.UUID, LineageEdge]] = []
    for experiment in experiments:
        sibling_runs = db.query(ExperimentRun).filter(ExperimentRun.experiment_id == experiment.id).all()
        run_nodes = [RunNode(run_id=r.id, parent_run_id=r.parent_run_id, run_type=r.run_type) for r in sibling_runs]
        run_ids = [r.id for r in sibling_runs]
        comparisons = (
            db.query(ExperimentComparison)
            .filter(ExperimentComparison.base_run_id.in_(run_ids), ExperimentComparison.compare_run_id.in_(run_ids))
            .all()
            if run_ids
            else []
        )
        comparison_links = [
            ComparisonLink(base_run_id=c.base_run_id, compare_run_id=c.compare_run_id) for c in comparisons
        ]
        graph = build_lineage_graph(run_nodes, comparison_links)
        edges_by_experiment.extend((experiment.id, edge) for edge in graph.edges)
    return edges_by_experiment


def _reports_for_comparisons(db: Session) -> list[tuple[ExperimentComparison, object]]:
    comparisons = db.query(ExperimentComparison).all()
    results: list[tuple[ExperimentComparison, object]] = []
    for comparison in comparisons:
        original_run = db.get(ExperimentRun, comparison.base_run_id)
        reproduction_run = db.get(ExperimentRun, comparison.compare_run_id)
        experiment = db.get(Experiment, original_run.experiment_id)
        reproducibility = (
            db.query(ReproducibilityAssessment).filter_by(comparison_id=comparison.id).one_or_none()
        )
        report = generate_report(
            comparison=comparison,
            experiment=experiment,
            original_run=original_run,
            reproduction_run=reproduction_run,
            reproducibility=reproducibility,
        )
        results.append((comparison, report))
    return results


def build_workbook(db: Session) -> Workbook:
    wb = Workbook()
    wb.remove(wb.active)

    _build_experiments_sheet(wb, db.query(Experiment).all())
    _build_runs_sheet(wb, db.query(ExperimentRun).all())
    _build_code_sheet(wb, db.query(CodeSnapshot).all())
    _build_datasets_sheet(wb, db.query(DatasetVersion).all())
    _build_data_splits_sheet(wb)
    _build_pipelines_sheet(wb)
    _build_environments_sheet(wb, db.query(Environment).all())
    _build_dependencies_sheet(wb, db.query(Dependency).all())
    _build_configurations_sheet(wb, db.query(Configuration).all())
    _build_randomness_sheet(wb, db.query(RandomnessProfile).all())
    _build_metrics_sheet(wb, db.query(Metric).all())
    _build_artifacts_sheet(wb, db.query(Artifact).all())
    _build_differences_sheet(wb, db.query(Difference).all())
    _build_reproducibility_sheet(wb, db.query(ReproducibilityAssessment).all())
    _build_investigations_sheet(
        wb, get_investigation_store().list_all(), get_counterfactual_store().list_all()
    )
    _build_lineage_sheet(wb, _lineage_edges_for_experiments(db))
    _build_reports_sheet(wb, _reports_for_comparisons(db))

    return wb
