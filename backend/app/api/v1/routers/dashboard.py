"""GET /dashboard (Phase 19, spec section 53).

Not literally named in §72's minimum endpoint list, but §53 explicitly
requires "the dashboard must use real backend data" and names exactly
these fields - so this is a necessary addition, not scope creep. Every
field is a real aggregation query or a Phase 18 tracker read; nothing is
a placeholder/decorative number.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.models.comparison import ReproducibilityAssessment
from app.db.models.core import Experiment, ExperimentRun, Project
from app.db.models.enums import ReproducibilityClassification
from app.db.session import get_db
from app.jobs.orchestrator import get_job_tracker
from app.jobs.tracker import JobTracker, TERMINAL_STAGES
from app.schemas.dashboard import DashboardRead, RecentExperiment

router = APIRouter(tags=["dashboard"])

_REPRODUCIBLE = {
    ReproducibilityClassification.EXACTLY_REPRODUCIBLE,
    ReproducibilityClassification.REPRODUCIBLE_WITHIN_TOLERANCE,
    ReproducibilityClassification.CONDITIONALLY_REPRODUCIBLE,
}
_PARTIAL = {ReproducibilityClassification.PARTIALLY_REPRODUCIBLE}
_FAILED = {ReproducibilityClassification.NOT_REPRODUCIBLE}
_INSUFFICIENT = {ReproducibilityClassification.INSUFFICIENT_EVIDENCE, ReproducibilityClassification.NOT_COMPARABLE}


def _count_by_classification(db: Session, classifications: set[ReproducibilityClassification]) -> int:
    return (
        db.query(ReproducibilityAssessment)
        .filter(ReproducibilityAssessment.classification.in_(classifications))
        .count()
    )


@router.get("/dashboard", response_model=DashboardRead)
def get_dashboard(db: Session = Depends(get_db), tracker: JobTracker = Depends(get_job_tracker)) -> DashboardRead:
    recent = db.query(Experiment).order_by(Experiment.created_at.desc()).limit(5).all()
    active_jobs = sum(1 for record in tracker.list_jobs() if record.stage not in TERMINAL_STAGES)

    return DashboardRead(
        total_projects=db.query(Project).count(),
        total_experiments=db.query(Experiment).count(),
        total_runs=db.query(ExperimentRun).count(),
        reproducible_runs=_count_by_classification(db, _REPRODUCIBLE),
        partial_reproductions=_count_by_classification(db, _PARTIAL),
        failed_reproductions=_count_by_classification(db, _FAILED),
        insufficient_evidence=_count_by_classification(db, _INSUFFICIENT),
        active_jobs=active_jobs,
        recent_experiments=[
            RecentExperiment(id=e.id, name=e.name, project_id=e.project_id) for e in recent
        ],
    )
