"""GET /reports/{comparison_id} (Phase 26).

Not in spec section 72's literal minimum endpoint list, but the natural
single-resource endpoint for spec section 61's report generation
requirement - the same "necessary addition" situation as Phase 19's
/dashboard and Phase 24's /explain.

Investigation/counterfactual plans live only in Phase 22/23's in-process
stores, keyed by their own id with no index by comparison_id, so this
router resolves the optional `investigation_id`/`counterfactual_id` query
params against those stores itself and passes the already-resolved plan
into `generate_report()` - the generator never reaches into store
internals (mirrors Phase 24's explainer taking pre-fetched arguments).

An unresolvable `investigation_id`/`counterfactual_id` does not fail the
whole request - the report still generates, with that section reporting
`available=False` and a reason. Only a missing `comparison_id` is a hard
404.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db.models.comparison import ExperimentComparison, ReproducibilityAssessment
from app.db.models.core import Experiment, ExperimentRun
from app.db.session import get_db
from app.investigation.counterfactual import get_counterfactual_store
from app.investigation.planner import get_investigation_store
from app.reporting.generator import generate_report
from app.schemas.report import (
    CategoryProvenanceRead,
    ContributorRead,
    CounterfactualSummaryRead,
    DifferenceRead,
    ExperimentSummary,
    InvestigationSummaryRead,
    MetricComparisonRead,
    ReportRead,
    ReproducibilitySummaryRead,
    RunSummary,
)

router = APIRouter(tags=["reports"])


def _to_read(report) -> ReportRead:
    return ReportRead(
        report_version=report.report_version,
        comparison_id=report.comparison_id,
        experiment=ExperimentSummary(**report.experiment),
        original_run=RunSummary(**report.original_run),
        reproduction_run=RunSummary(**report.reproduction_run),
        provenance=[CategoryProvenanceRead(**p.__dict__) for p in report.provenance],
        metric_comparison=MetricComparisonRead(**report.metric_comparison.__dict__),
        differences=[DifferenceRead(**d.__dict__) for d in report.differences],
        reproducibility=ReproducibilitySummaryRead(**report.reproducibility.__dict__),
        potential_contributors=[ContributorRead(**c.__dict__) for c in report.potential_contributors],
        investigation=InvestigationSummaryRead(**report.investigation.__dict__),
        counterfactual=CounterfactualSummaryRead(**report.counterfactual.__dict__),
        limitations=report.limitations,
        evidence_references=report.evidence_references,
        generated_at=report.generated_at,
    )


@router.get("/reports/{comparison_id}", response_model=ReportRead)
def get_report(
    comparison_id: uuid.UUID,
    investigation_id: uuid.UUID | None = None,
    counterfactual_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
) -> ReportRead:
    comparison = db.get(ExperimentComparison, comparison_id)
    if comparison is None:
        raise NotFoundError(f"comparison {comparison_id} not found")

    original_run = db.get(ExperimentRun, comparison.base_run_id)
    reproduction_run = db.get(ExperimentRun, comparison.compare_run_id)
    experiment = db.get(Experiment, original_run.experiment_id)
    reproducibility = (
        db.query(ReproducibilityAssessment).filter_by(comparison_id=comparison_id).one_or_none()
    )

    investigation_plan = get_investigation_store().get(investigation_id) if investigation_id else None
    counterfactual_plan = get_counterfactual_store().get(counterfactual_id) if counterfactual_id else None

    report = generate_report(
        comparison=comparison,
        experiment=experiment,
        original_run=original_run,
        reproduction_run=reproduction_run,
        reproducibility=reproducibility,
        investigation_plan=investigation_plan,
        counterfactual_plan=counterfactual_plan,
    )
    return _to_read(report)
