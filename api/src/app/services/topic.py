"""Topic-summary queries for /api/topics."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Installment, Loan, LoanParty, LoanTopic
from app.models.enums import InstallmentStatus, LoanPartyRole
from app.schemas.topic import TopicSummary


async def list_topics(
    session: AsyncSession,
    *,
    year: int | None = None,
) -> list[TopicSummary]:
    """All topics from the catalog, with counts/totals for the given year.

    Returns a row per topic.  Topics with no loans in the year still appear
    (loan_count=0, total=0, outstanding=0) — admins use the page to
    discover *which* topics are unused as much as the ones in heavy use.
    """
    loan_q = select(Loan.id, Loan.topic_id, Loan.total_amount)
    if year is not None:
        loan_q = loan_q.where(Loan.persian_year == year)
    loan_sub = loan_q.subquery()

    # Per-topic loan count + total
    totals_q = (
        select(
            loan_sub.c.topic_id,
            func.count().label("loan_count"),
            func.coalesce(func.sum(loan_sub.c.total_amount), 0).label("total"),
        )
        .group_by(loan_sub.c.topic_id)
        .subquery()
    )

    # Per-topic outstanding = Σ unpaid lender-side installments scoped to those loans
    outstanding_select = (
        select(
            Loan.topic_id,
            func.coalesce(func.sum(Installment.amount), 0).label("outstanding"),
        )
        .select_from(Loan)
        .join(LoanParty, LoanParty.loan_id == Loan.id)
        .join(Installment, Installment.loan_party_id == LoanParty.id)
        .where(
            LoanParty.role == LoanPartyRole.lender,
            Installment.status == InstallmentStatus.unpaid,
        )
    )
    if year is not None:
        outstanding_select = outstanding_select.where(Loan.persian_year == year)
    outstanding_q = outstanding_select.group_by(Loan.topic_id).subquery()

    rows = (
        await session.execute(
            select(
                LoanTopic.id,
                LoanTopic.name,
                func.coalesce(totals_q.c.loan_count, 0).label("loan_count"),
                func.coalesce(totals_q.c.total, 0).label("total"),
                func.coalesce(outstanding_q.c.outstanding, 0).label("outstanding"),
            )
            .select_from(LoanTopic)
            .join(totals_q, totals_q.c.topic_id == LoanTopic.id, isouter=True)
            .join(outstanding_q, outstanding_q.c.topic_id == LoanTopic.id, isouter=True)
            .order_by(LoanTopic.name)
        )
    ).all()

    return [
        TopicSummary(
            id=row[0],
            name=row[1],
            loan_count=row[2],
            total=Decimal(row[3]),
            outstanding=Decimal(row[4]),
        )
        for row in rows
    ]
