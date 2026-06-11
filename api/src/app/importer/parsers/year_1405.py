"""Year-1405+ parser — thin wrapper over the generic layout engine.

The bespoke table-row walker that used to live here moved into
:mod:`app.importer.parsers.engine`, parameterised by the 1405 entry of
:data:`app.importer.parsers.layout.LAYOUTS` (rebased for 1406+).  The
public function is kept so existing callers and tests keep working
unchanged.
"""

from __future__ import annotations

from openpyxl.worksheet.worksheet import Worksheet

from app.importer.models import ParseResult
from app.importer.parsers.engine import parse_year
from app.importer.parsers.layout import TABLE_FORMAT_SINCE, layout_for


def parse_year_1405(ws: Worksheet, persian_year: int, result: ParseResult) -> None:
    """Append every loan in a 1405+ table-layout sheet to ``result.loans``."""
    layout = layout_for(max(persian_year, TABLE_FORMAT_SINCE))
    assert layout is not None  # 1405+ always resolves
    parse_year(ws, persian_year, layout, result)
