"""Jalali calendar helpers shared by the API services and the importer.

The ledgers carry due dates as raw (year, month, day) triples, and the
DB CHECK only enforces day 1..31 — so impossible dates (اسفند 30 of a
common year) do occur in real data and must be handled, not crashed on.
"""

from __future__ import annotations

import jdatetime

#: Months 1..6 have 31 days.
LONG_MONTHS_END = 6
#: Months 7..11 have 30 days; اسفند (12) has 29, or 30 in leap years.
SHORT_MONTHS_END = 11


def last_day_of_month(year: int, month: int) -> int:
    """Real last day of a Jalali month (leap-aware for اسفند)."""
    if month <= LONG_MONTHS_END:
        return 31
    if month <= SHORT_MONTHS_END:
        return 30
    return 30 if jdatetime.date(year, 1, 1).isleap() else 29


def safe_date(year: int, month: int, day: int) -> jdatetime.date:
    """Build a jdatetime.date, clamping a too-large day to the month's end.

    The production workbook contains 24 installments due ``1402/12/30``
    though اسفند 1402 (a common year) ends on the 29th; clamping keeps
    calendar math (overdue-days etc.) working on such rows.
    """
    return jdatetime.date(year, month, min(day, last_day_of_month(year, month)))


def add_months(year: int, month: int, day: int, months: int) -> tuple[int, int, int]:
    """Same day ``months`` later, clamped to the month's last day (31 → 30 in مهر)."""
    index = year * 12 + (month - 1) + months
    y, m = divmod(index, 12)
    return (y, m + 1, min(day, last_day_of_month(y, m + 1)))


MONTHS_PER_YEAR = 12


def is_valid(year: int, month: int, day: int) -> bool:
    return 1 <= month <= MONTHS_PER_YEAR and 1 <= day <= last_day_of_month(year, month)
