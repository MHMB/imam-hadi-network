"""Parse the ``موضوعات`` (Topics) sheet.

Output is a deduplicated list of topic names.  Blank placeholder rows
are silently dropped; rows whose name resolves to a duplicate trigger
no warning (admins sometimes copy-paste rows).
"""

from __future__ import annotations

from openpyxl.worksheet.worksheet import Worksheet

from app.importer.models import ParseResult

# Layout (SPEC.md §2.3): table ``titles`` at A2:C22.
# Column B holds the topic name; A is a legacy_num (only set for "نامعلوم");
# C is a computed sum we ignore (recomputed in DB views).
_NAME_COL = 2
_HEADER_ROW = 2  # data starts at row 3


def parse_topics(ws: Worksheet, result: ParseResult) -> None:
    """Append topic names found in ``ws`` to ``result.topics``."""
    seen: set[str] = set()
    for r in range(_HEADER_ROW + 1, ws.max_row + 1):
        cell_value = ws.cell(row=r, column=_NAME_COL).value
        if cell_value is None:
            continue
        name = str(cell_value).strip()
        if not name or name in seen:
            continue
        seen.add(name)
        result.topics.append(name)
