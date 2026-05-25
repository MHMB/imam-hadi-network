"""Year-1404 sheet parser — legacy row-pair encoding.

Layout (SPEC.md §2.4 + §2.6):

- Header rows 1–3; data starts at row 4.
- Each lender contribution occupies **two consecutive rows**:
    - Top row carries the day-of-month;
    - Bottom row carries the amount and the green-fill paid sentinel.
- A loan group spans one or more lender pairs.  The first row of a
  group has the ``ردیف`` / loan number / total / topic / liaison /
  description set; continuation rows use ``=IFNA(B{r-2}, B{r})`` to
  inherit the same loan number (we resolve those by carry-forward).
- Columns P..AO (16..41) are 26 month cells covering
  Farvardin 1404 → Ordibehesht 1406.
- Borrower is the legacy ``قرض گیرنده`` column (E) — exactly one
  borrower per loan in the sample.  The N-to-N schema lets future xlsm
  revisions add multiple borrowers without code changes.
"""

from __future__ import annotations

import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Final, cast

from openpyxl.cell import Cell
from openpyxl.styles import PatternFill
from openpyxl.worksheet.worksheet import Worksheet

from app.importer.colors import fill_signature, is_green
from app.importer.models import (
    ParsedInstallment,
    ParsedIssue,
    ParsedLoan,
    ParsedParty,
    ParseResult,
)
from app.models.enums import InstallmentStatus, IssueCategory, IssueSeverity, LoanPartyRole

# --- column indexes (1-based, A=1) ---
COL_ROW_INDEX = 1
COL_LOAN_NUMBER = 2
COL_CHANNEL_NUMBER = 3
COL_LIAISON = 4
COL_BORROWER = 5
COL_TOTAL_AMOUNT = 7
COL_TOPIC = 8
COL_DESCRIPTION = 9
COL_LENDER = 12  # the "خیر" column
COL_LENDER_AMOUNT = 14
FIRST_MONTH_COL = 16  # P
LAST_MONTH_COL = 41  # AO

HEADER_ROW = 3
FIRST_DATA_ROW = 4
EXPECTED_PERSIAN_YEAR = 1404

# Month grid: 26 columns covering Farvardin 1404 → Ordibehesht 1406.
# Order matters; index into this list with (col - FIRST_MONTH_COL).
MONTH_GRID: Final[tuple[tuple[int, int], ...]] = (
    *((1404, m) for m in range(1, 13)),  # 1404/01..1404/12
    *((1405, m) for m in range(1, 13)),  # 1405/01..1405/12
    (1406, 1),
    (1406, 2),
)
assert len(MONTH_GRID) == LAST_MONTH_COL - FIRST_MONTH_COL + 1


def _normalise_text(value: object) -> str:
    if value is None:
        return ""
    return unicodedata.normalize("NFC", str(value)).strip()


def _to_decimal(
    value: object, *, sheet: str, cell: str, issues: list[ParsedIssue]
) -> Decimal | None:
    """Coerce a numeric cell to ``Decimal``; return ``None`` if blank."""
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        issues.append(
            ParsedIssue(
                severity=IssueSeverity.warning,
                category=IssueCategory.bad_day,  # closest existing category for "unparseable number"
                message=f"مقدار نامعتبر در سلول {cell}: نمی‌توان به عدد تبدیل کرد ({value!r}).",
                sheet=sheet,
                cell=cell,
                context={"raw": str(value)},
            )
        )
        return None


def _to_day_of_month(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        # int(float(...)) tolerates openpyxl returning e.g. 15.0
        return int(float(str(value)))
    except (ValueError, TypeError):
        return None


def parse_year_1404(ws: Worksheet, persian_year: int, result: ParseResult) -> None:
    """Append every loan in the 1404 sheet to ``result.loans``.

    Algorithm (SPEC.md §2.6):
    1. Walk rows in pairs r, r+1 starting at FIRST_DATA_ROW.
    2. Whenever ``ردیف`` (col A) is non-blank, start a new loan group:
       capture borrower, total, topic, liaison, description from this row.
    3. The current row is always a lender contribution: read lender name
       (L) and amount (N).
    4. For each month column, pair top-row day with bottom-row amount;
       a green fill on the amount cell marks the installment as paid.
    5. Move to r += 2 and continue.  Loan boundary detected when the next
       non-blank ``ردیف`` appears.
    """
    sheet = ws.title
    if persian_year != EXPECTED_PERSIAN_YEAR:
        result.issues.append(
            ParsedIssue(
                severity=IssueSeverity.error,
                category=IssueCategory.orphan_row,
                message=(
                    f"parse_year_1404 invoked on سال {persian_year}; sheet has unexpected layout."
                ),
                sheet=sheet,
            )
        )
        return

    # Resolved loan state (set when a new group starts; reused on continuation rows).
    cur_loan_number: str | None = None
    cur_total: Decimal | None = None
    cur_borrower: str | None = None
    cur_topic: str | None = None
    cur_channel: str | None = None
    cur_liaison: str | None = None
    cur_description: str | None = None

    # Loans being assembled.  When a new ردیف appears, flush the previous one.
    cur_parties: list[ParsedParty] = []
    next_party_order = 0

    def _flush() -> None:
        nonlocal cur_parties, next_party_order
        if (
            cur_loan_number is None
            or cur_total is None
            or cur_borrower is None
            or cur_topic is None
        ):
            return
        loan = ParsedLoan(
            persian_year=persian_year,
            loan_number=cur_loan_number,
            total_amount=cur_total,
            topic_name=cur_topic,
            parties=(
                # Synthesise the single-borrower party first; importer
                # contract: 1 borrower party covering the full total.
                ParsedParty(
                    role=LoanPartyRole.borrower,
                    person_name=cur_borrower,
                    amount=cur_total,
                    display_order=0,
                ),
                *cur_parties,
            ),
            channel_number=cur_channel,
            liaison_label=cur_liaison,
            description=cur_description,
            source_sheet=sheet,
        )
        result.loans.append(loan)
        cur_parties = []
        next_party_order = 0

    r = FIRST_DATA_ROW
    while r <= ws.max_row:
        row_index_value = ws.cell(row=r, column=COL_ROW_INDEX).value
        starts_new_group = row_index_value not in (None, "")

        if starts_new_group:
            _flush()
            # Read loan-level fields from this row.
            cur_loan_number = _normalise_text(ws.cell(row=r, column=COL_LOAN_NUMBER).value) or None
            cur_borrower = _normalise_text(ws.cell(row=r, column=COL_BORROWER).value) or None
            cur_topic = _normalise_text(ws.cell(row=r, column=COL_TOPIC).value) or None
            cur_liaison = _normalise_text(ws.cell(row=r, column=COL_LIAISON).value) or None
            cur_description = _normalise_text(ws.cell(row=r, column=COL_DESCRIPTION).value) or None
            channel_raw = ws.cell(row=r, column=COL_CHANNEL_NUMBER).value
            cur_channel = _normalise_text(channel_raw) or None
            cur_total = _to_decimal(
                ws.cell(row=r, column=COL_TOTAL_AMOUNT).value,
                sheet=sheet,
                cell=f"{sheet}!G{r}",
                issues=result.issues,
            )

        # Lender + amount on this row pair
        lender = _normalise_text(ws.cell(row=r, column=COL_LENDER).value)
        amount = _to_decimal(
            ws.cell(row=r, column=COL_LENDER_AMOUNT).value,
            sheet=sheet,
            cell=f"{sheet}!N{r}",
            issues=result.issues,
        )

        # If the row has neither a lender nor an amount, just skip (blank pair).
        if lender or amount is not None:
            installments = _read_installment_pair(ws, r, sheet, result.issues)
            cur_parties.append(
                ParsedParty(
                    role=LoanPartyRole.lender,
                    person_name=lender or "",
                    amount=amount if amount is not None else Decimal(0),
                    display_order=next_party_order,
                    installments=tuple(installments),
                )
            )
            next_party_order += 1
            if not lender:
                result.issues.append(
                    ParsedIssue(
                        severity=IssueSeverity.warning,
                        category=IssueCategory.unresolved_person,
                        message=f"وام‌دهنده در ردیف {r} نامشخص است.",
                        sheet=sheet,
                        cell=f"{sheet}!L{r}",
                    )
                )

        r += 2

    _flush()


def _read_installment_pair(
    ws: Worksheet,
    top_row: int,
    sheet: str,
    issues: list[ParsedIssue],
) -> list[ParsedInstallment]:
    """Walk P..AO columns; pair top-row day with bottom-row amount."""
    out: list[ParsedInstallment] = []
    for col in range(FIRST_MONTH_COL, LAST_MONTH_COL + 1):
        day_cell = ws.cell(row=top_row, column=col)
        amount_cell = ws.cell(row=top_row + 1, column=col)
        day_val = day_cell.value
        amount_val = amount_cell.value
        if day_val in (None, "") and amount_val in (None, ""):
            continue
        year, month = MONTH_GRID[col - FIRST_MONTH_COL]
        day = _to_day_of_month(day_val)
        amount = _to_decimal(
            amount_val,
            sheet=sheet,
            cell=f"{sheet}!{amount_cell.coordinate}",
            issues=issues,
        )
        if day is None and amount is None:
            continue
        if day is None:
            issues.append(
                ParsedIssue(
                    severity=IssueSeverity.info,
                    category=IssueCategory.missing_day,
                    message=f"قسط در سلول {amount_cell.coordinate} روز سررسید ندارد.",
                    sheet=sheet,
                    cell=f"{sheet}!{day_cell.coordinate}",
                )
            )
            day = 1  # parking value; importer/DB constraint will reject if amount > 0 lingers
        if amount is None:
            issues.append(
                ParsedIssue(
                    severity=IssueSeverity.info,
                    category=IssueCategory.missing_amount,
                    message=f"روز سررسید در {day_cell.coordinate} بدون مبلغ.",
                    sheet=sheet,
                    cell=f"{sheet}!{amount_cell.coordinate}",
                )
            )
            continue
        status, color_issue = _classify(cast(Cell, amount_cell), sheet)
        if color_issue is not None:
            issues.append(color_issue)
        out.append(
            ParsedInstallment(
                due_persian_year=year,
                due_persian_month=month,
                due_day_of_month=day,
                amount=amount,
                status=status,
                sheet=sheet,
                cell=f"{sheet}!{amount_cell.coordinate}",
            )
        )
    return out


def _classify(amount_cell: Cell, sheet: str) -> tuple[InstallmentStatus, ParsedIssue | None]:
    """Inspect the amount cell's fill; return (status, optional anomaly issue)."""
    # openpyxl returns a StyleProxy for cell.fill — at runtime it quacks like
    # PatternFill; cast for mypy.
    fill = cast(PatternFill, amount_cell.fill)
    if is_green(fill):
        return InstallmentStatus.paid, None
    # Unfilled / white = unpaid.  Any other fill is a colour anomaly — still
    # treated as unpaid but flagged so admins can normalize the source xlsm.
    sig = fill_signature(fill)
    if sig is None:
        return InstallmentStatus.unpaid, None
    issue = ParsedIssue(
        severity=IssueSeverity.info,
        category=IssueCategory.color_anomaly,
        message=(
            f"رنگ غیرمنتظره روی سلول {amount_cell.coordinate}؛ "
            f"امضای رنگ: {sig}. به عنوان «پرداخت‌نشده» در نظر گرفته شد."
        ),
        sheet=sheet,
        cell=f"{sheet}!{amount_cell.coordinate}",
        context={"signature": sig},
    )
    return InstallmentStatus.unpaid, issue
