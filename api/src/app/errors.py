"""Business-rule errors returned as FastAPI-style 422s, one message per field.

Services raise ``FieldError("phone", "…")``; the handler turns it into the
same ``{"detail": [{"loc": [...], "msg": ...}]}`` shape pydantic uses, so
the web client shows every message next to its input.
"""

from __future__ import annotations

import re
from decimal import Decimal

from fastapi import Request
from fastapi.responses import JSONResponse


class FieldError(Exception):
    def __init__(self, field: str, message: str, *, code: str = "invalid") -> None:
        super().__init__(message)
        self.field = field
        self.message = message
        self.code = code


_DECIMAL = re.compile(r"\d+\.\d+")
_TO_PERSIAN = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def persian_numbers(message: str) -> str:
    """«1.833» → «۱٫۸۳۳», «0.800» → «۰٫۸», «1405/12/31» → «۱۴۰۵/۱۲/۳۱»."""
    trimmed = _DECIMAL.sub(lambda m: format(Decimal(m.group()).normalize(), "f"), message)
    return re.sub(r"(?<=\d)\.(?=\d)", "٫", trimmed).translate(_TO_PERSIAN)


async def field_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, FieldError)
    return JSONResponse(
        status_code=422,
        content={
            "detail": [
                {"loc": ["body", exc.field], "msg": persian_numbers(exc.message), "type": exc.code}
            ]
        },
    )
