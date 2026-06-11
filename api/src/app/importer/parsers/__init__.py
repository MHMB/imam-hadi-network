"""Sub-parsers for the legacy xlsm workbook.

Each parser is pure: take a ``Worksheet``, emit ``ParsedX`` records and
``ParsedIssue`` warnings into a ``ParseResult``.  No DB, no I/O beyond
the workbook itself.

Dispatch lives at the package level:

- :func:`detect_year_sheets` finds ``سال NNNN`` sheets.
- :func:`year_parser_for` looks the year up in the layout registry
  (:mod:`app.importer.parsers.layout`) and binds the generic engine
  (:mod:`app.importer.parsers.engine`) to it.  Every historical format
  1401–1405 is covered; 1406+ reuses the 1405 table layout rebased.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from openpyxl.workbook import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from app.importer.models import ParseResult
from app.importer.parsers.engine import parse_year
from app.importer.parsers.layout import LAYOUTS, YearLayout, layout_for
from app.importer.parsers.people import parse_people
from app.importer.parsers.topics import parse_topics

_YEAR_SHEET_RE = re.compile(r"^سال\s+(\d{4})$")

YearParser = Callable[[Worksheet, int, ParseResult], None]


def detect_year_sheets(wb: Workbook) -> list[tuple[int, str]]:
    """Return ``[(persian_year, sheet_name), ...]`` ordered by year ascending."""
    found: list[tuple[int, str]] = []
    for name in wb.sheetnames:
        m = _YEAR_SHEET_RE.match(name)
        if m:
            found.append((int(m.group(1)), name))
    return sorted(found, key=lambda t: t[0])


def year_parser_for(persian_year: int) -> YearParser:
    """Bind the generic engine to the year's layout."""
    layout = layout_for(persian_year)
    if layout is None:
        # Pre-1401 sheets have no registered layout.  Parse nothing rather
        # than misparse; runner-level issues surface the gap.
        msg = f"no layout registered for سال {persian_year}"
        raise LookupError(msg)

    def _parse(ws: Worksheet, year: int, result: ParseResult) -> None:
        parse_year(ws, year, layout, result)

    return _parse


__all__ = [
    "LAYOUTS",
    "YearLayout",
    "YearParser",
    "detect_year_sheets",
    "layout_for",
    "parse_people",
    "parse_topics",
    "parse_year",
    "year_parser_for",
]
