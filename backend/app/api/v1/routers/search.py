"""GET /search (Phase 25).

Not in spec §72's literal minimum endpoint list, but required by
acceptance checklist item 28 ("Natural-language experiment search
works.") - the same "necessary addition" situation as Phase 19's
/dashboard and Phase 24's /explain.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import PageParams
from app.config import get_settings
from app.db.models.comparison import Difference, ExperimentComparison
from app.db.models.core import Experiment, ExperimentRun, Project
from app.db.session import get_db
from app.schemas.common import Page
from app.schemas.search import SearchResultRead
from app.search.engine import (
    SearchDocument,
    build_document_for_difference,
    build_document_for_experiment,
    build_document_for_project,
    search,
)
from app.search.provider import get_search_provider

router = APIRouter(tags=["search"])


def _load_documents(db: Session) -> list[SearchDocument]:
    documents: list[SearchDocument] = []

    projects = db.query(Project).all()
    documents.extend(build_document_for_project(project) for project in projects)

    experiments = db.query(Experiment).all()
    documents.extend(build_document_for_experiment(experiment) for experiment in experiments)

    run_to_experiment_project = {
        run_id: project_id
        for run_id, project_id in db.query(ExperimentRun.id, Experiment.project_id).join(
            Experiment, ExperimentRun.experiment_id == Experiment.id
        )
    }
    differences = (
        db.query(Difference, ExperimentComparison.base_run_id)
        .join(ExperimentComparison, Difference.comparison_id == ExperimentComparison.id)
        .all()
    )
    for difference, base_run_id in differences:
        project_id = run_to_experiment_project.get(base_run_id)
        documents.append(build_document_for_difference(difference, project_id))

    return documents


@router.get("/search", response_model=Page[SearchResultRead])
def search_all(
    q: str = Query(..., min_length=1, max_length=500),
    db: Session = Depends(get_db),
    page: PageParams = Depends(),
) -> Page[SearchResultRead]:
    documents = _load_documents(db)
    provider = get_search_provider(get_settings())
    result = search(q, documents, provider, page.limit, page.offset)

    items = [
        SearchResultRead(
            entity_type=r.entity_type,
            entity_id=r.entity_id,
            project_id=r.project_id,
            title=r.title,
            snippet=r.snippet,
            score=r.score,
        )
        for r in result.results
    ]
    return Page(items=items, total=result.total, limit=page.limit, offset=page.offset)
