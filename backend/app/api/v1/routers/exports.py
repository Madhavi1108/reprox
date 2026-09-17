"""GET /exports/excel (Phase 27, spec section 62).

Not in spec section 72's literal minimum endpoint list, but the natural
single endpoint for spec section 62's Excel export requirement - the
same "necessary addition" situation as Phase 19's /dashboard and Phase
26's /reports/{comparison_id}.

The first binary-file response in this codebase - no Pydantic response
model, since `StreamingResponse` streams raw bytes rather than a JSON
body. Exporting an all-empty database is a valid, honest result (same
"empty is honest, not an error" reasoning as `provenance.py`), so there
is no 404 path here.
"""

from __future__ import annotations

import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.export.excel import build_workbook

router = APIRouter(tags=["exports"])

_XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/exports/excel")
def export_excel(db: Session = Depends(get_db)) -> StreamingResponse:
    workbook = build_workbook(db)
    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type=_XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": "attachment; filename=reprox_export.xlsx"},
    )
