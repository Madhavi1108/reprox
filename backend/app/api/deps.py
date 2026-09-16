"""Shared FastAPI dependencies (Phase 19).

No auth/RBAC scheme is specified anywhere in the spec (checked the full
PDF - the only adjacent requirement is a vague §49 "access control" bullet
under Data Privacy, with no concrete design given). Per the project's own
approved MVP scoping (docs/PHASE_TRACKER.md Phase 29), REPROX runs as a
single seeded user - `get_current_user_id` fetches-or-creates that one
user row rather than implementing real authentication.
"""

from __future__ import annotations

import uuid
from collections.abc import Generator

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from app.db.models.core import User
from app.db.session import get_db

SEEDED_USER_EMAIL = "dev@reprox.local"


def get_current_user_id(db: Session = Depends(get_db)) -> uuid.UUID:
    user = db.query(User).filter(User.email == SEEDED_USER_EMAIL).one_or_none()
    if user is None:
        user = User(id=uuid.uuid4(), email=SEEDED_USER_EMAIL, display_name="REPROX Dev User")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user.id


class PageParams:
    def __init__(self, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)) -> None:
        self.limit = limit
        self.offset = offset
