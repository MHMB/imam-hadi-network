"""Sub-parsers for the legacy xlsm workbook.

Each parser is pure: take a ``Worksheet``, emit ``ParsedX`` records and
``ParsedIssue`` warnings into a ``ParseResult``.  No DB, no I/O beyond
the workbook itself.

Dispatch lives at the package level:

- :func:`detect_year_sheets` finds ``سال NNNN`` sheets.
- :func:`year_parser_for` returns the right per-year parser for a sheet
  name — Phase 1 ships the row-pair decoder (year_1404) and the
  table-row decoder (year_1405); future years can plug in here.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from openpyxl.workbook import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from app.importer.models import ParseResult

# Re-exported parser functions land here as their modules ship.
from app.importer.parsers.people import parse_people
from app.importer.parsers.topics import parse_topics
from app.importer.parsers.year_1404 import parse_year_1404
from app.importer.parsers.year_1405 import parse_year_1405

_YEAR_SHEET_RE = re.compile(r"^سال\s+(\d{4})$")

YearParser = Callable[[Worksheet, int, ParseResult], None]

# Year 1404 used the legacy row-pair encoding. Everything from 1405 onwards
# uses the cleaner Excel-table layout — we register parsers by predicate so
# adding 1406+ requires no edits unless the layout changes again.
_LEGACY_ROW_PAIR_YEAR = 1404


def detect_year_sheets(wb: Workbook) -> list[tuple[int, str]]:
    """Return ``[(persian_year, sheet_name), ...]`` ordered by year ascending."""
    found: list[tuple[int, str]] = []
    for name in wb.sheetnames:
        m = _YEAR_SHEET_RE.match(name)
        if m:
            found.append((int(m.group(1)), name))
    return sorted(found, key=lambda t: t[0])


def year_parser_for(persian_year: int) -> YearParser:
    """Pick the right per-year parser for the encoding used in that sheet."""
    if persian_year == _LEGACY_ROW_PAIR_YEAR:
        return parse_year_1404
    return parse_year_1405


__all__ = [
    "YearParser",
    "detect_year_sheets",
    "parse_people",
    "parse_topics",
    "parse_year_1404",
    "parse_year_1405",
    "year_parser_for",
]
