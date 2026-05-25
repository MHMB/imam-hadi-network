"""Year-1405+ sheet parser — row-major encoding.

Layout (SPEC.md §2.5):

- Header rows 1–2; data starts at row 3.  Sheet is wrapped in an Excel
  table (``Table7``), but we read raw cells: the table only contributes
  styling.
- One **row per lender contribution**.  Loan-level fields (number,
  borrower, total, topic, ...) are replicated across continuation rows
  via formulas like ``=A3`` — we detect group boundaries by looking at
  the literal ``ردیف`` value rather than evaluating formulas.
- Per month, **two columns**: ``M=Farvardin day``, ``N=Farvardin amount``,
  ``O=Ordibehesht day``, ``P=amount``, ...  17 month-pairs total,
  covering Farvardin 1405 → Mordad 1406.  The numeric header in row 2
  (1..17) is the structured-reference column name used by the
  ``SumifColor`` formula on the مانده column.
- Per-loan guarantor lives on col F (``ضامن``) — set in this sheet,
  unlike 1404 where it was always blank.
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
COL_TOPIC = 4
COL_LIAISON = 5
COL_GUARANTOR = 6
COL_BORROWER = 7
COL_TOTAL_AMOUNT = 8
COL_DESCRIPTION = 9
COL_LENDER = 10
COL_LENDER_AMOUNT = 11
FIRST_MONTH_COL = 13  # M

# Number of months in the schedule grid (covers Farvardin 1405 → Mordad 1406).
_SCHEDULE_MONTHS = 17

FIRST_DATA_ROW = 3
HEADER_ROW = 2

# Build the (year, month) sequence for the 17 day/amount column pairs.
# Index into it with (col_pair_index = (col - FIRST_MONTH_COL) // 2).
_BASE_YEAR_OFFSET = 1405


def _build_month_grid(base_year: int) -> tuple[tuple[int, int], ...]:
    """``(year, month)`` for each of the 17 month-pairs starting at base_year/1."""
    months: list[tuple[int, int]] = []
    for i in range(_SCHEDULE_MONTHS):
        year, month = divmod(i, 12)
        months.append((base_year + year, month + 1))
    return tuple(months)


MONTH_GRID_1405: Final = _build_month_grid(_BASE_YEAR_OFFSET)


def _normalise_text(value: object) -> str:
    if value is None:
        return ""
    return unicodedata.normalize("NFC", str(value)).strip()


def _is_formula(value: object) -> bool:
    """openpyxl returns formulas as plain strings beginning with ``=``."""
    return isinstance(value, str) and value.startswith("=")


def _to_decimal(
    value: object,
    *,
    sheet: str,
    cell: str,
    issues: list[ParsedIssue],
) -> Decimal | None:
    if value is None or value == "":
        return None
    if _is_formula(value):
        # Loan-level fields can carry formulas like ``=H3``; we ignore them
        # here — the writer reads the literal from the loan's first row.
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        issues.append(
            ParsedIssue(
                severity=IssueSeverity.warning,
                category=IssueCategory.bad_day,
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
    if _is_formula(value):
        return None
    try:
        return int(float(str(value)))
    except (ValueError, TypeError):
        return None


def _literal_text(ws: Worksheet, row: int, col: int) -> str | None:
    """Read a text cell, skipping ``=...`` formula strings (continuation rows)."""
    value = ws.cell(row=row, column=col).value
    if value is None or _is_formula(value):
        return None
    return _normalise_text(value) or None


def _starts_new_group(ws: Worksheet, row: int) -> bool:
    """A new loan group starts whenever col A holds a literal (non-formula) value."""
    a_value = ws.cell(row=row, column=COL_ROW_INDEX).value
    if a_value is None or a_value == "":
        return False
    return not _is_formula(a_value)


def parse_year_1405(ws: Worksheet, persian_year: int, result: ParseResult) -> None:
    """Append every loan in a 1405+ sheet to ``result.loans``.

    The parser is layout-driven; the actual year used to date installments
    is taken from the ``persian_year`` parameter (so a sheet named
    ``سال 1406`` reuses the same code with base year 1406).
    """
    sheet = ws.title
    month_grid = _build_month_grid(persian_year)

    # Resolved loan state — set when a new group starts.
    cur_loan_number: str | None = None
    cur_total: Decimal | None = None
    cur_borrower: str | None = None
    cur_topic: str | None = None
    cur_channel: str | None = None
    cur_liaison: str | None = None
    cur_description: str | None = None
    cur_guarantor: str | None = None

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
                ParsedParty(
                    role=LoanPartyRole.borrower,
                    person_name=cur_borrower,
                    amount=cur_total,
                    display_order=0,
                ),
                *cur_parties,
            ),
            channel_number=cur_channel,
            guarantor_name=cur_guarantor,
            liaison_label=cur_liaison,
            description=cur_description,
            source_sheet=sheet,
        )
        result.loans.append(loan)
        cur_parties = []
        next_party_order = 0

    for r in range(FIRST_DATA_ROW, ws.max_row + 1):
        if _starts_new_group(ws, r):
            _flush()
            cur_loan_number = _literal_text(ws, r, COL_LOAN_NUMBER)
            cur_borrower = _literal_text(ws, r, COL_BORROWER)
            cur_topic = _literal_text(ws, r, COL_TOPIC)
            cur_liaison = _literal_text(ws, r, COL_LIAISON)
            cur_guarantor = _literal_text(ws, r, COL_GUARANTOR)
            cur_description = _literal_text(ws, r, COL_DESCRIPTION)
            channel_raw = ws.cell(row=r, column=COL_CHANNEL_NUMBER).value
            channel_text = (
                None if _is_formula(channel_raw) else _normalise_text(channel_raw) or None
            )
            # The legacy sheet stores absent channel numbers as the literal 0;
            # normalise to NULL for the DB.
            cur_channel = None if channel_text in (None, "0") else channel_text
            cur_total = _to_decimal(
                ws.cell(row=r, column=COL_TOTAL_AMOUNT).value,
                sheet=sheet,
                cell=f"{sheet}!H{r}",
                issues=result.issues,
            )

        # Lender + amount on this row
        lender = _literal_text(ws, r, COL_LENDER)
        amount = _to_decimal(
            ws.cell(row=r, column=COL_LENDER_AMOUNT).value,
            sheet=sheet,
            cell=f"{sheet}!K{r}",
            issues=result.issues,
        )
        if lender is None and amount is None:
            continue

        installments = _read_row_installments(ws, r, month_grid, sheet, result.issues)
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
        if lender is None:
            result.issues.append(
                ParsedIssue(
                    severity=IssueSeverity.warning,
                    category=IssueCategory.unresolved_person,
                    message=f"وام‌دهنده در ردیف {r} نامشخص است.",
                    sheet=sheet,
                    cell=f"{sheet}!J{r}",
                )
            )

    _flush()


def _read_row_installments(
    ws: Worksheet,
    row: int,
    month_grid: tuple[tuple[int, int], ...],
    sheet: str,
    issues: list[ParsedIssue],
) -> list[ParsedInstallment]:
    """Walk M..AT in pairs (day, amount); emit installments + colour issues."""
    out: list[ParsedInstallment] = []
    for pair_index in range(_SCHEDULE_MONTHS):
        day_col = FIRST_MONTH_COL + pair_index * 2
        amount_col = day_col + 1
        day_cell = ws.cell(row=row, column=day_col)
        amount_cell = ws.cell(row=row, column=amount_col)
        day_val = day_cell.value
        amount_val = amount_cell.value
        if day_val in (None, "") and amount_val in (None, ""):
            continue
        year, month = month_grid[pair_index]
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
            day = 1
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
    fill = cast(PatternFill, amount_cell.fill)
    if is_green(fill):
        return InstallmentStatus.paid, None
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
