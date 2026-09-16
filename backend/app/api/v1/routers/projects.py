from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import PageParams, get_current_user_id
from app.core.errors import ConflictError
from app.db.models.core import Project
from app.db.session import get_db
from app.schemas.common import Page
from app.schemas.project import ProjectCreate, ProjectRead

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectRead, status_code=201)
def create_project(
    payload: ProjectCreate, db: Session = Depends(get_db), user_id: uuid.UUID = Depends(get_current_user_id)
) -> Project:
    project = Project(
        id=uuid.uuid4(),
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        owner_user_id=user_id,
    )
    db.add(project)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError(f"a project with slug {payload.slug!r} already exists")
    db.refresh(project)
    return project


@router.get("", response_model=Page[ProjectRead])
def list_projects(db: Session = Depends(get_db), page: PageParams = Depends()) -> Page[ProjectRead]:
    total = db.query(Project).count()
    items = db.query(Project).order_by(Project.created_at.desc()).offset(page.offset).limit(page.limit).all()
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)
