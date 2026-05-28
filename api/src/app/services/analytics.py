"""Monthly analytics rollups for the admin landing page.

All counts and amounts use what's already in the DB.  Two framings:

- ``installments_due`` — grouped by the Jalali **due** triple (no paid-date
  required).  paid_amount = sum of due installments with status='paid';
  unpaid_amount = remainder.
- ``new_loans`` — grouped by ``loan.created_at`` converted to Jalali (i.e.
  loan-import time, not real loan creation; Phase 1 approximation).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal

import jdatetime
from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models import Installment, Loan, LoanParty, LoanTopic, Person
from app.models.enums import InstallmentStatus, LoanPartyRole
from app.schemas.analytics import (
    InstallmentsDueByDay,
    InstallmentsDueSummary,
    MonthlyAnalyticsResponse,
    MonthlyPeriod,
    NewLoansSummary,
    PersonAmountItem,
    TopicBreakdownItem,
)

PERSIAN_MONTH_NAMES = [
    "فروردین",
    "اردیبهشت",
    "خرداد",
    "تیر",
    "مرداد",
    "شهریور",
    "مهر",
    "آبان",
    "آذر",
    "دی",
    "بهمن",
    "اسفند",
]
_TOP_N = 5
_JALALI_LAST_MONTH = 12


def previous_jalali_month(today: jdatetime.date) -> tuple[int, int]:
    """Return (year, month) of the calendar month *before* `today`."""
    if today.month == 1:
        return (today.year - 1, _JALALI_LAST_MONTH)
    return (today.year, today.month - 1)


def _jalali_to_persian_label(year: int, month: int) -> str:
    return f"{PERSIAN_MONTH_NAMES[month - 1]} {year}"


def _persian_digits(value: int) -> str:
    return str(value).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


def _label_with_persian_digits(year: int, month: int) -> str:
    return f"{PERSIAN_MONTH_NAMES[month - 1]} {_persian_digits(year)}"


async def get_monthly_analytics(
    session: AsyncSession,
    *,
    year: int | None = None,
    month: int | None = None,
) -> MonthlyAnalyticsResponse:
    """All chart payloads for one Jalali month.

    Default month = the previous **completed** Jalali month relative to
    today.  Override via ``year`` + ``month`` query params.
    """
    if year is None or month is None:
        today_j = jdatetime.date.fromgregorian(date=date.today())
        year, month = previous_jalali_month(today_j)

    period = MonthlyPeriod(
        persian_year=year,
        persian_month=month,
        label_fa=_label_with_persian_digits(year, month),
    )

    new_loans = await _new_loans_summary(session, year, month)
    installments_due = await _installments_due_summary(session, year, month)
    by_topic = await _new_loans_by_topic(session, year, month)
    top_borrowers = await _top_persons_by_role(session, year, month, LoanPartyRole.borrower)
    top_lenders = await _top_persons_by_role(session, year, month, LoanPartyRole.lender)

    return MonthlyAnalyticsResponse(
        period=period,
        new_loans=new_loans,
        installments_due=installments_due,
        new_loans_by_topic=by_topic,
        top_borrowers=top_borrowers,
        top_lenders=top_lenders,
    )


# --------------------------------------------------------------------- internals


def _gregorian_range_for_jalali_month(year: int, month: int) -> tuple[datetime, datetime]:
    """First-of-month inclusive, first-of-next-month exclusive, in UTC."""
    start_j = jdatetime.date(year, month, 1)
    end_j = (
        jdatetime.date(year + 1, 1, 1)
        if month == _JALALI_LAST_MONTH
        else jdatetime.date(year, month + 1, 1)
    )
    start_g = start_j.togregorian()
    end_g = end_j.togregorian()
    return (
        datetime.combine(start_g, datetime.min.time()),
        datetime.combine(end_g, datetime.min.time()),
    )


async def _new_loans_summary(session: AsyncSession, year: int, month: int) -> NewLoansSummary:
    start_g, end_g = _gregorian_range_for_jalali_month(year, month)
    row = (
        await session.execute(
            select(
                func.count().label("count"),
                func.coalesce(func.sum(Loan.total_amount), 0).label("total"),
            ).where(Loan.created_at >= start_g, Loan.created_at < end_g)
        )
    ).one()
    return NewLoansSummary(count=row.count, total_amount=Decimal(row.total))


async def _installments_due_summary(
    session: AsyncSession, year: int, month: int
) -> InstallmentsDueSummary:
    rows = (
        await session.execute(
            select(
                Installment.due_day_of_month.label("day"),
                func.count().label("count"),
                func.coalesce(
                    func.sum(
                        case(
                            (Installment.status == InstallmentStatus.paid, Installment.amount),
                            else_=0,
                        )
                    ),
                    0,
                ).label("paid_amount"),
                func.coalesce(
                    func.sum(
                        case(
                            (Installment.status == InstallmentStatus.unpaid, Installment.amount),
                            else_=0,
                        )
                    ),
                    0,
                ).label("unpaid_amount"),
            )
            .select_from(Installment)
            .join(LoanParty, LoanParty.id == Installment.loan_party_id)
            .where(
                LoanParty.role == LoanPartyRole.lender,
                Installment.due_persian_year == year,
                Installment.due_persian_month == month,
            )
            .group_by(Installment.due_day_of_month)
            .order_by(Installment.due_day_of_month)
        )
    ).all()
    by_day = [
        InstallmentsDueByDay(
            day=r.day,
            count=r.count,
            paid_amount=Decimal(r.paid_amount),
            unpaid_amount=Decimal(r.unpaid_amount),
        )
        for r in rows
    ]
    count = sum(d.count for d in by_day)
    paid = sum((d.paid_amount for d in by_day), Decimal(0))
    unpaid = sum((d.unpaid_amount for d in by_day), Decimal(0))
    total = paid + unpaid
    rate = float(paid / total * 100) if total > 0 else 0.0
    return InstallmentsDueSummary(
        count=count,
        amount_total=total,
        amount_paid=paid,
        amount_unpaid=unpaid,
        payment_rate_pct=round(rate, 2),
        by_day=by_day,
    )


async def _new_loans_by_topic(
    session: AsyncSession, year: int, month: int
) -> list[TopicBreakdownItem]:
    start_g, end_g = _gregorian_range_for_jalali_month(year, month)
    rows = (
        await session.execute(
            select(
                LoanTopic.name.label("topic_name"),
                func.count().label("count"),
                func.coalesce(func.sum(Loan.total_amount), 0).label("total"),
            )
            .select_from(Loan)
            .join(LoanTopic, LoanTopic.id == Loan.topic_id)
            .where(Loan.created_at >= start_g, Loan.created_at < end_g)
            .group_by(LoanTopic.name)
            .order_by(func.coalesce(func.sum(Loan.total_amount), 0).desc())
        )
    ).all()
    return [
        TopicBreakdownItem(topic_name=r.topic_name, count=r.count, total=Decimal(r.total))
        for r in rows
    ]


async def _top_persons_by_role(
    session: AsyncSession,
    year: int,
    month: int,
    role: LoanPartyRole,
) -> list[PersonAmountItem]:
    """Top N borrowers / lenders by their per-month loan-party amount.

    Counted by ``loan.created_at`` (= import time) — same approximation
    used elsewhere on this page.
    """
    start_g, end_g = _gregorian_range_for_jalali_month(year, month)
    lp = aliased(LoanParty)
    rows = (
        await session.execute(
            select(
                Person.id.label("person_id"),
                Person.full_name,
                func.coalesce(func.sum(lp.amount), 0).label("total"),
            )
            .select_from(lp)
            .join(Loan, Loan.id == lp.loan_id)
            .join(Person, Person.id == lp.person_id)
            .where(
                lp.role == role,
                and_(Loan.created_at >= start_g, Loan.created_at < end_g),
            )
            .group_by(Person.id, Person.full_name)
            .order_by(func.coalesce(func.sum(lp.amount), 0).desc())
            .limit(_TOP_N)
        )
    ).all()
    out: list[PersonAmountItem] = []
    for r in rows:
        # Skip persons with zero (shouldn't happen due to >0 check but defensive).
        if Decimal(r.total) <= 0:
            continue
        out.append(
            PersonAmountItem(person_id=r.person_id, full_name=r.full_name, total=Decimal(r.total))
        )
    return out


# Re-bucket helper so callers can also dedupe / sum if multiple parties of
# same role exist for a person across loans in the month.  Currently SUM in
# SQL handles it; kept for future use if we move grouping client-side.
def _dedupe_persons(items: list[PersonAmountItem]) -> list[PersonAmountItem]:
    bucket: dict[int, Decimal] = defaultdict(lambda: Decimal(0))
    names: dict[int, str] = {}
    for item in items:
        bucket[item.person_id] += item.total
        names[item.person_id] = item.full_name
    out = [
        PersonAmountItem(person_id=pid, full_name=names[pid], total=total)
        for pid, total in bucket.items()
    ]
    out.sort(key=lambda x: x.total, reverse=True)
    return out[:_TOP_N]
