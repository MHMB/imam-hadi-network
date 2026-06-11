"""Per-year sheet layout configuration.

The ledger format evolved every year; the differences are pure geometry
(which column holds what, how the repayment grid is encoded), so each year
is described by a ``YearLayout`` value and one generic engine
(:mod:`app.importer.parsers.engine`) walks them all.

Verified against ``real_data.xlsm`` (the production source of truth):

========  =======================  ==========================================
sheet     shape                    notes
========  =======================  ==========================================
سال 1401  paired rows, step 2      lender K / amount L (bottom row); real
                                   Gregorian date columns exist (Phase 2);
                                   no topic column.
سال 1402  paired rows, step 2      same geometry as 1401, months shifted.
سال 1403  paired rows, step 2      lender J / amount K (top row); grid holds
                                   amounts only — no due-day row.
سال 1404  paired rows, step 2      the layout the original importer shipped
                                   with; topic column H.
سال 1405  Excel table, step 1      one row per contribution; 17 (day,
                                   amount) column pairs; topic column D.
========  =======================  ==========================================

Years after 1405 are assumed to continue the 1405 table format with the
month grid rebased — exactly what the old ``year_parser_for`` did.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

#: Topic assigned to loans on sheets that predate the topic column.
#: Already present in the موضوعات master (legacy_num 0).
DEFAULT_TOPIC = "نامعلوم"

#: First year using the Excel-table single-row format; later years are
#: assumed to keep it (with the month grid rebased).
TABLE_FORMAT_SINCE = 1405


class GridEncoding(StrEnum):
    """How the per-month repayment grid is written."""

    paired_day_amount = "paired_day_amount"
    """Two physical rows per contribution: due-day on the top row, amount on
    the bottom row, one column per month (1401, 1402, 1404)."""

    paired_amount_only = "paired_amount_only"
    """Amounts on the bottom row only — the sheet records no due day; the
    engine dates every installment to day 1 (1403)."""

    table_pairs = "table_pairs"
    """Single row, two columns per month: (day, amount) (1405+)."""


def month_span(start_year: int, start_month: int, count: int) -> tuple[tuple[int, int], ...]:
    """``count`` consecutive Persian (year, month) pairs from the start."""
    months: list[tuple[int, int]] = []
    index = start_month - 1
    for i in range(count):
        year, month = divmod(index + i, 12)
        months.append((start_year + year, month + 1))
    return tuple(months)


@dataclass(frozen=True, slots=True)
class YearLayout:
    """Geometry of one year sheet.  All columns 1-based (A=1)."""

    first_data_row: int
    row_step: int  # 2 = paired layout, 1 = table layout

    c_loan_number: int
    c_borrower: int
    c_total: int
    c_lender: int
    c_amount: int
    amount_row_offset: int  # 0 = lender's row, 1 = the row below

    grid_first_col: int
    grid_encoding: GridEncoding
    grid_months: tuple[tuple[int, int], ...]

    c_topic: int | None = None  # None → DEFAULT_TOPIC
    c_guarantor: int | None = None
    c_channel: int | None = None
    c_liaison: int | None = None
    c_description: int | None = None

    @property
    def grid_width(self) -> int:
        """Number of physical columns the grid occupies."""
        per_month = 2 if self.grid_encoding is GridEncoding.table_pairs else 1
        return len(self.grid_months) * per_month


_LAYOUT_1401 = YearLayout(
    first_data_row=3,
    row_step=2,
    c_loan_number=2,  # B ش
    c_borrower=6,  # F قرض گیرنده
    c_total=5,  # E مجموع
    c_lender=11,  # K خیر
    c_amount=12,  # L مبلغ — on the bottom row of the pair
    amount_row_offset=1,
    grid_first_col=16,  # P فروردین .. AM اسفند (24 months)
    grid_encoding=GridEncoding.paired_day_amount,
    grid_months=month_span(1401, 1, 24),
    c_topic=None,
    c_guarantor=10,  # J ضامن
    c_channel=3,  # C ش.کانال
    c_liaison=4,  # D رابط
    c_description=8,  # H توضیحات
)

_LAYOUT_1403 = YearLayout(
    first_data_row=4,
    row_step=2,
    c_loan_number=2,  # B ش
    c_borrower=5,  # E قرض گیرنده
    c_total=6,  # F مجموع
    c_lender=10,  # J خیر
    c_amount=11,  # K مبلغ — on the lender's own row
    amount_row_offset=0,
    grid_first_col=13,  # M فروردین 03 .. AL اردیبهشت 05 (26 months)
    grid_encoding=GridEncoding.paired_amount_only,
    grid_months=month_span(1403, 1, 26),
    c_topic=None,
    c_guarantor=9,  # I ضامن
    c_channel=3,
    c_liaison=4,
    c_description=7,  # G توضیحات
)

_LAYOUT_1404 = YearLayout(
    first_data_row=4,
    row_step=2,
    c_loan_number=2,
    c_borrower=5,  # E قرض گیرنده
    c_total=7,  # G مجموع
    c_lender=12,  # L خیر
    c_amount=14,  # N مبلغ — on the lender's own row
    amount_row_offset=0,
    grid_first_col=16,  # P .. AO (26 months)
    grid_encoding=GridEncoding.paired_day_amount,
    grid_months=month_span(1404, 1, 26),
    c_topic=8,  # H موضوع
    c_guarantor=None,
    c_channel=3,
    c_liaison=4,
    c_description=9,
)

_LAYOUT_1405 = YearLayout(
    first_data_row=3,
    row_step=1,
    c_loan_number=2,
    c_borrower=7,  # G
    c_total=8,  # H
    c_lender=10,  # J
    c_amount=11,  # K
    amount_row_offset=0,
    grid_first_col=13,  # M.. — 17 (day, amount) pairs
    grid_encoding=GridEncoding.table_pairs,
    grid_months=month_span(1405, 1, 17),
    c_topic=4,  # D
    c_guarantor=6,  # F
    c_channel=3,
    c_liaison=5,
    c_description=9,
)

LAYOUTS: dict[int, YearLayout] = {
    1401: _LAYOUT_1401,
    1402: replace(_LAYOUT_1401, grid_months=month_span(1402, 1, 24)),
    1403: _LAYOUT_1403,
    1404: _LAYOUT_1404,
    1405: _LAYOUT_1405,
}


def layout_for(persian_year: int) -> YearLayout | None:
    """Layout for a year sheet; 1406+ rebases the 1405 table format."""
    if persian_year in LAYOUTS:
        return LAYOUTS[persian_year]
    if persian_year > TABLE_FORMAT_SINCE:
        return replace(_LAYOUT_1405, grid_months=month_span(persian_year, 1, 17))
    return None
