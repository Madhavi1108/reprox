from fastapi import Request
from fastapi.responses import JSONResponse


class ReproxError(Exception):
    """Base application error carrying a stable machine-readable code."""

    status_code: int = 400
    code: str = "reprox_error"

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(ReproxError):
    status_code = 404
    code = "not_found"


class ConflictError(ReproxError):
    status_code = 409
    code = "conflict"


class ValidationFailedError(ReproxError):
    status_code = 422
    code = "validation_failed"


async def reprox_error_handler(request: Request, exc: ReproxError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )
