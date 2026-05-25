"""Year-1404 sheet parser — row-pair encoding.  Body lands in P2.5."""

from __future__ import annotations

from openpyxl.worksheet.worksheet import Worksheet

from app.importer.models import ParseResult


def parse_year_1404(ws: Worksheet, persian_year: int, result: ParseResult) -> None:
    """Stub.  Phase 1, step P2.5 implements the row-pair decoder."""
    _ = (ws, persian_year, result)
    raise NotImplementedError("parse_year_1404 lands in P2.5")
