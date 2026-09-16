from fastapi import APIRouter

from app.api.v1.routers import (
    comparisons,
    dashboard,
    experiments,
    jobs,
    lineage,
    projects,
    provenance,
    reproducibility,
    runs,
)

api_router = APIRouter()

api_router.include_router(projects.router)
api_router.include_router(experiments.router)
api_router.include_router(runs.router)
api_router.include_router(comparisons.router)
api_router.include_router(reproducibility.router)
api_router.include_router(provenance.router)
api_router.include_router(lineage.router)
api_router.include_router(jobs.router)
api_router.include_router(dashboard.router)
