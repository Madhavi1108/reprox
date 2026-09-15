from fastapi import FastAPI
from sqlalchemy import text

from app.core.errors import ReproxError, reprox_error_handler
from app.core.logging import configure_logging
from app.db.session import SessionLocal

configure_logging()

app = FastAPI(
    title="REPROX API",
    description=(
        "Experiment Provenance, Reproducibility Intelligence & Root-Cause "
        "Analysis Platform - MVP backend"
    ),
    version="0.1.0",
)

app.add_exception_handler(ReproxError, reprox_error_handler)


@app.get("/health", tags=["system"])
def health() -> dict:
    return {"status": "ok"}


@app.get("/health/db", tags=["system"])
def health_db() -> dict:
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok"}
    finally:
        db.close()


from app.api.v1.router import api_router  # noqa: E402

app.include_router(api_router, prefix="/api/v1")
