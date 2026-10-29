"""Overdue installments — list of unpaid installments past their due date.

Uses only data we have today: `Installment.status='unpaid'` AND the
Jalali (year, month, day) due triple < today's Jalali date.  No
payment-date column required (that's a Phase-2 concern).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import jdatetime
from sqlalchemy import and_, func, literal, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.jalali import safe_date as safe_jalali_date
from app.models import Installment, Loan, LoanParty, LoanTopic, Person
from app.models.enums import InstallmentStatus, LoanPartyRole
from app.schemas.overdue import OverdueInstallmentItem
from app.schemas.person import PersonRef
from app.services.money import REMAINING
from app.services.query import Page, page_bounds


def _today_jalali() -> tuple[int, int, int]:
    g = jdatetime.date.fromgregorian(date=date.today())
    return (g.year, g.month, g.day)


def _days_overdue(due: tuple[int, int, int], today: tuple[int, int, int]) -> int:
    """Difference in days between today and `due` (Jalali triples).

    Converts both to gregorian and subtracts.  Guaranteed ≥ 0 for caller
    use because callers only invoke with `due < today`.  Impossible
    legacy due-days (e.g. اسفند 30 of a common year — present in the real
    ledgers) are clamped to the month's last day instead of raising and
    500ing the whole listing.
    """
    due_g = safe_jalali_date(*due).togregorian()
    today_g = safe_jalali_date(*today).togregorian()
    diff = (today_g - due_g).days
    return int(max(diff, 0))


def _extra_filters(
    year: int | None,
    due_from: tuple[int, int, int] | None,
    due_to: tuple[int, int, int] | None,
) -> list[Any]:
    """Optional loan-year and inclusive due-date-range filters."""
    due = tuple_(
        Installment.due_persian_year,
        Installment.due_persian_month,
        Installment.due_day_of_month,
    )
    filters: list[Any] = []
    if year is not None:
        filters.append(Loan.persian_year == year)
    if due_from is not None:
        filters.append(due >= tuple_(*(literal(v) for v in due_from)))
    if due_to is not None:
        filters.append(due <= tuple_(*(literal(v) for v in due_to)))
    return filters


async def list_overdue(
    session: AsyncSession,
    *,
    min_days_overdue: int = 0,
    year: int | None = None,
    due_from: tuple[int, int, int] | None = None,
    due_to: tuple[int, int, int] | None = None,
    page: int = 1,
    page_size: int = 50,
) -> Page[OverdueInstallmentItem]:
    """List currently-overdue lender-side installments, worst-first.

    `min_days_overdue` filters in Python after Jalali→gregorian diff
    (negligible cost at expected scale, avoids modelling Jalali calendar
    arithmetic in SQL).
    """
    today_y, today_m, today_d = _today_jalali()

    borrower_lp = aliased(LoanParty, name="borrower_lp")
    lender_lp = aliased(LoanParty, name="lender_lp")
    borrower_person = aliased(Person, name="borrower_person")
    lender_person = aliased(Person, name="lender_person")
    guarantor_person = aliased(Person, name="guarantor_person")

    # Single query: installment → lender party → loan → borrower party →
    # both persons + topic + optional per-loan guarantor.
    stmt = (
        select(
            Installment.id.label("installment_id"),
            Loan.id.label("loan_id"),
            Loan.loan_number,
            Loan.persian_year,
            Loan.description,
            LoanTopic.name.label("topic_name"),
            Installment.due_persian_year,
            Installment.due_persian_month,
            Installment.due_day_of_month,
            REMAINING.label("amount"),
            borrower_person.id.label("b_id"),
            borrower_person.full_name.label("b_name"),
            borrower_person.phone.label("b_phone"),
            lender_person.id.label("l_id"),
            lender_person.full_name.label("l_name"),
            lender_person.phone.label("l_phone"),
            guarantor_person.id.label("g_id"),
            guarantor_person.full_name.label("g_name"),
            guarantor_person.phone.label("g_phone"),
        )
        .select_from(Installment)
        .join(lender_lp, lender_lp.id == Installment.loan_party_id)
        .join(Loan, Loan.id == lender_lp.loan_id)
        .join(LoanTopic, LoanTopic.id == Loan.topic_id)
        .join(lender_person, lender_person.id == lender_lp.person_id)
        # Outer: a few Excel loans have no borrower row; they are still late.
        .join(
            borrower_lp,
            and_(
                borrower_lp.loan_id == Loan.id,
                borrower_lp.role == LoanPartyRole.borrower,
            ),
            isouter=True,
        )
        .join(borrower_person, borrower_person.id == borrower_lp.person_id, isouter=True)
        .join(guarantor_person, guarantor_person.id == Loan.guarantor_id, isouter=True)
        .where(
            lender_lp.role == LoanPartyRole.lender,
            Installment.status == InstallmentStatus.unpaid,
            # Row comparison: (due triple) < (today triple)
            tuple_(
                Installment.due_persian_year,
                Installment.due_persian_month,
                Installment.due_day_of_month,
            )
            < tuple_(literal(today_y), literal(today_m), literal(today_d)),
            *_extra_filters(year, due_from, due_to),
        )
        .order_by(
            Installment.due_persian_year,
            Installment.due_persian_month,
            Installment.due_day_of_month,
        )
    )

    rows = (await session.execute(stmt)).all()

    items: list[OverdueInstallmentItem] = []
    for r in rows:
        due = (r.due_persian_year, r.due_persian_month, r.due_day_of_month)
        days = _days_overdue(due, (today_y, today_m, today_d))
        if days < min_days_overdue:
            continue
        items.append(
            OverdueInstallmentItem(
                installment_id=r.installment_id,
                loan_id=r.loan_id,
                loan_number=r.loan_number,
                persian_year=r.persian_year,
                has_note=bool((r.description or "").strip()),
                topic_name=r.topic_name,
                borrower=(
                    PersonRef(id=r.b_id, full_name=r.b_name, phone=r.b_phone)
                    if r.b_id is not None
                    else None
                ),
                lender=PersonRef(id=r.l_id, full_name=r.l_name, phone=r.l_phone),
                guarantor=(
                    PersonRef(id=r.g_id, full_name=r.g_name, phone=r.g_phone)
                    if r.g_id is not None
                    else None
                ),
                due_persian_year=r.due_persian_year,
                due_persian_month=r.due_persian_month,
                due_day_of_month=r.due_day_of_month,
                amount=Decimal(r.amount),
                days_overdue=days,
            )
        )

    # Worst-first
    items.sort(key=lambda i: i.days_overdue, reverse=True)
    total = len(items)
    offset, limit = page_bounds(page, page_size)
    return Page[OverdueInstallmentItem](
        items=items[offset : offset + limit],
        total=total,
        page=page,
        page_size=limit,
    )


# Re-exports kept narrow so tests + routers import only what they need.
__all__ = ["_days_overdue", "_today_jalali", "list_overdue"]

# Silence unused-symbol warnings on this side; func / or_ are reserved for
# future iterations (e.g. min/max-days-overdue facets that pre-filter in SQL).
_ = (func, or_)
