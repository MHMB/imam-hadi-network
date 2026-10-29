"""Business-rule errors returned as FastAPI-style 422s, one message per field.

Services raise ``FieldError("phone", "…")``; the handler turns it into the
same ``{"detail": [{"loc": [...], "msg": ...}]}`` shape pydantic uses, so
the web client shows every message next to its input.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse


class FieldError(Exception):
    def __init__(self, field: str, message: str, *, code: str = "invalid") -> None:
        super().__init__(message)
        self.field = field
        self.message = message
        self.code = code


async def field_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, FieldError)
    return JSONResponse(
        status_code=422,
        content={"detail": [{"loc": ["body", exc.field], "msg": exc.message, "type": exc.code}]},
    )
