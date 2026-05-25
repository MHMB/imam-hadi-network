"""Year-1405+ sheet parser — row-major table layout.  Body lands in P2.6."""

from __future__ import annotations

from openpyxl.worksheet.worksheet import Worksheet

from app.importer.models import ParseResult


def parse_year_1405(ws: Worksheet, persian_year: int, result: ParseResult) -> None:
    """Stub.  Phase 1, step P2.6 implements the table-row decoder."""
    _ = (ws, persian_year, result)
    raise NotImplementedError("parse_year_1405 lands in P2.6")
