"""Year-1404 parser — thin wrapper over the generic layout engine.

The bespoke row-pair walker that used to live here moved into
:mod:`app.importer.parsers.engine`, parameterised by the 1404 entry of
:data:`app.importer.parsers.layout.LAYOUTS`.  The public function is kept
so existing callers and tests keep working unchanged.
"""

from __future__ import annotations

from openpyxl.worksheet.worksheet import Worksheet

from app.importer.models import ParsedIssue, ParseResult
from app.importer.parsers.engine import parse_year
from app.importer.parsers.layout import LAYOUTS
from app.models.enums import IssueCategory, IssueSeverity

EXPECTED_PERSIAN_YEAR = 1404


def parse_year_1404(ws: Worksheet, persian_year: int, result: ParseResult) -> None:
    """Append every loan in the 1404 sheet to ``result.loans``."""
    if persian_year != EXPECTED_PERSIAN_YEAR:
        result.issues.append(
            ParsedIssue(
                severity=IssueSeverity.error,
                category=IssueCategory.orphan_row,
                message=(
                    f"parse_year_1404 invoked on سال {persian_year}; sheet has unexpected layout."
                ),
                sheet=ws.title,
            )
        )
        return
    parse_year(ws, persian_year, LAYOUTS[EXPECTED_PERSIAN_YEAR], result)
