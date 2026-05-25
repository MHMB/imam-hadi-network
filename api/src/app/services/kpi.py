"""Aggregations powering the home page KPI cards + charts."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import jdatetime
from sqlalchemy import func, literal, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Installment, Loan, LoanParty, Person
from app.models.enums import InstallmentStatus, LoanPartyRole
from app.schemas.kpi import KPIByYear, KPIResponse


def _today_jalali() -> tuple[int, int, int]:
    """Today as a Jalali (year, month, day) triple."""
    g = jdatetime.date.fromgregorian(date=datetime.now().date())
    return (g.year, g.month, g.day)


async def get_kpi(session: AsyncSession) -> KPIResponse:
    """Compute all dashboard KPIs from live tables.

    Live aggregates are fine at the documented volume (~10k persons,
    10k–100k loans/year).  Add a refreshable summary table later if
    /api/kpi ever exceeds ~1 second.
    """
    persons_total = (await session.execute(select(func.count()).select_from(Person))).scalar_one()
    loans_total = (await session.execute(select(func.count()).select_from(Loan))).scalar_one()
    total_amount = (
        await session.execute(select(func.coalesce(func.sum(Loan.total_amount), 0)))
    ).scalar_one()

    # outstanding = Σ unpaid installments of lender-side parties
    outstanding_total = (
        await session.execute(
            select(func.coalesce(func.sum(Installment.amount), 0))
            .select_from(Installment)
            .join(LoanParty, LoanParty.id == Installment.loan_party_id)
            .where(
                Installment.status == InstallmentStatus.unpaid,
                LoanParty.role == LoanPartyRole.lender,
            )
        )
    ).scalar_one()

    # A loan is "settled" if it has zero unpaid installments on the lender side.
    loan_outstanding_q = (
        select(Loan.id, func.coalesce(func.sum(Installment.amount), 0).label("outstanding"))
        .select_from(Loan)
        .join(LoanParty, LoanParty.loan_id == Loan.id)
        .join(Installment, Installment.loan_party_id == LoanParty.id, isouter=True)
        .where(LoanParty.role == LoanPartyRole.lender)
        .group_by(Loan.id)
        .subquery()
    )
    loans_active = (
        await session.execute(
            select(func.count()).select_from(loan_outstanding_q).where(
                loan_outstanding_q.c.outstanding > 0
            )
        )
    ).scalar_one()
    loans_settled = loans_total - loans_active

    # Overdue: unpaid installments whose due date < today (Jalali, lexicographic).
    today_y, today_m, today_d = _today_jalali()
    overdue_installments = (
        await session.execute(
            select(func.count())
            .select_from(Installment)
            .where(
                Installment.status == InstallmentStatus.unpaid,
                # (year, month, day) < (today_y, today_m, today_d) via Postgres
                # row comparison.  tuple_() wraps the columns in SQL ROW(...).
                tuple_(
                    Installment.due_persian_year,
                    Installment.due_persian_month,
                    Installment.due_day_of_month,
                )
                < tuple_(literal(today_y), literal(today_m), literal(today_d)),
            )
        )
    ).scalar_one()

    # Per-year breakdown
    year_rows = (
        await session.execute(
            select(
                Loan.persian_year,
                func.count().label("loan_count"),
                func.coalesce(func.sum(Loan.total_amount), 0).label("total"),
            )
            .group_by(Loan.persian_year)
            .order_by(Loan.persian_year.desc())
        )
    ).all()
    # Per-year outstanding: sum unpaid lender-side installments grouped by
    # loan.persian_year.
    unpaid_year_rows = (
        await session.execute(
            select(
                Loan.persian_year,
                func.coalesce(func.sum(Installment.amount), 0).label("outstanding"),
            )
            .select_from(Loan)
            .join(LoanParty, LoanParty.loan_id == Loan.id)
            .join(Installment, Installment.loan_party_id == LoanParty.id)
            .where(
                LoanParty.role == LoanPartyRole.lender,
                Installment.status == InstallmentStatus.unpaid,
            )
            .group_by(Loan.persian_year)
        )
    ).all()
    outstanding_by_year: dict[int, Decimal] = {
        row[0]: row[1] for row in unpaid_year_rows
    }

    by_year = [
        KPIByYear(
            year=year,
            loan_count=loan_count,
            total=Decimal(total),
            outstanding=Decimal(outstanding_by_year.get(year, 0)),
        )
        for (year, loan_count, total) in year_rows
    ]

    return KPIResponse(
        persons_total=persons_total,
        loans_total=loans_total,
        loans_active=loans_active,
        loans_settled=loans_settled,
        total_amount=Decimal(total_amount),
        outstanding_total=Decimal(outstanding_total),
        overdue_installments=overdue_installments,
        by_year=by_year,
    )
