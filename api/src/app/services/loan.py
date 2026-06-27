"""Loan list + detail queries."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import jdatetime
from sqlalchemy import BigInteger, case, cast, func, literal, nulls_last, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Installment,
    Loan,
    LoanParty,
    LoanTopic,
    Person,
)
from app.models.enums import InstallmentStatus, LoanPartyRole
from app.schemas.loan import (
    InstallmentRef,
    LenderPartyRef,
    LoanDetailResponse,
    LoanListItem,
    LoanPartyRef,
    LoanTotals,
    TopicRef,
)
from app.schemas.person import PersonRef
from app.services.query import Page, page_bounds


def _loan_paid_remaining_subq() -> Any:
    """Per-loan (paid, remaining) from unpaid+paid lender-side installments."""
    return (
        select(
            Loan.id.label("loan_id"),
            func.coalesce(
                func.sum(
                    case(
                        (Installment.status == InstallmentStatus.paid, Installment.amount),
                        else_=0,
                    )
                ),
                0,
            ).label("paid"),
            func.coalesce(
                func.sum(
                    case(
                        (Installment.status == InstallmentStatus.unpaid, Installment.amount),
                        else_=0,
                    )
                ),
                0,
            ).label("remaining"),
        )
        .select_from(Loan)
        .join(LoanParty, LoanParty.loan_id == Loan.id)
        .join(Installment, Installment.loan_party_id == LoanParty.id)
        .where(LoanParty.role == LoanPartyRole.lender)
        .group_by(Loan.id)
        .subquery()
    )


def _borrower_name_subq() -> Any:
    """One borrower name per loan.  Phase 1 always emits exactly one."""
    return (
        select(
            LoanParty.loan_id.label("loan_id"),
            func.min(Person.full_name).label("borrower_name"),
        )
        .select_from(LoanParty)
        .join(Person, Person.id == LoanParty.person_id)
        .where(LoanParty.role == LoanPartyRole.borrower)
        .group_by(LoanParty.loan_id)
        .subquery()
    )


# --------------------------------------------------------------------- list


async def list_loans(
    session: AsyncSession,
    *,
    year: int | None = None,
    topic_ids: list[int] | None = None,
    status: str | None = None,  # 'active' | 'settled'
    borrower_id: int | None = None,
    lender_id: int | None = None,
    liaison: str | None = None,
    q: str | None = None,
    due_within_days: int | None = None,
    sort: str | None = None,  # loan_number | year | total | remaining
    sort_dir: str = "asc",
    page: int = 1,
    page_size: int = 50,
) -> Page[LoanListItem]:
    paid_rem = _loan_paid_remaining_subq()
    borrower_q = _borrower_name_subq()

    base = (
        select(
            Loan.id,
            Loan.persian_year,
            Loan.loan_number,
            Loan.channel_number,
            Loan.liaison_label,
            Loan.total_amount,
            LoanTopic.name.label("topic_name"),
            func.coalesce(borrower_q.c.borrower_name, "").label("borrower_name"),
            func.coalesce(paid_rem.c.paid, 0).label("paid"),
            func.coalesce(paid_rem.c.remaining, 0).label("remaining"),
        )
        .select_from(Loan)
        .join(LoanTopic, LoanTopic.id == Loan.topic_id)
        .join(borrower_q, borrower_q.c.loan_id == Loan.id, isouter=True)
        .join(paid_rem, paid_rem.c.loan_id == Loan.id, isouter=True)
    )

    filters: list[Any] = []
    if year is not None:
        filters.append(Loan.persian_year == year)
    if topic_ids:
        filters.append(Loan.topic_id.in_(topic_ids))
    if liaison:
        filters.append(Loan.liaison_label == liaison)
    if borrower_id is not None:
        filters.append(
            Loan.id.in_(
                select(LoanParty.loan_id).where(
                    LoanParty.role == LoanPartyRole.borrower,
                    LoanParty.person_id == borrower_id,
                )
            )
        )
    if lender_id is not None:
        filters.append(
            Loan.id.in_(
                select(LoanParty.loan_id).where(
                    LoanParty.role == LoanPartyRole.lender,
                    LoanParty.person_id == lender_id,
                )
            )
        )
    if status == "active":
        filters.append(func.coalesce(paid_rem.c.remaining, 0) > 0)
    elif status == "settled":
        filters.append(func.coalesce(paid_rem.c.remaining, 0) == 0)
    if q:
        # cheap loan-number prefix match — Phase 1 admins typically type the
        # ش number, not free text.
        filters.append(Loan.loan_number.icontains(q))
    if due_within_days is not None:
        # Loans with a lender-side unpaid installment falling due between today
        # and today+N (Jalali). Today and the end are real dates → convert via
        # Gregorian; the stored due triples are compared as integer tuples, so
        # impossible legacy dates (e.g. 1402/12/30) don't break the comparison.
        today_j = jdatetime.date.fromgregorian(date=date.today())
        end_j = jdatetime.date.fromgregorian(date=date.today() + timedelta(days=due_within_days))
        due_tuple = tuple_(
            Installment.due_persian_year,
            Installment.due_persian_month,
            Installment.due_day_of_month,
        )
        filters.append(
            Loan.id.in_(
                select(LoanParty.loan_id)
                .join(Installment, Installment.loan_party_id == LoanParty.id)
                .where(
                    LoanParty.role == LoanPartyRole.lender,
                    Installment.status == InstallmentStatus.unpaid,
                    due_tuple
                    >= tuple_(literal(today_j.year), literal(today_j.month), literal(today_j.day)),
                    due_tuple
                    <= tuple_(literal(end_j.year), literal(end_j.month), literal(end_j.day)),
                )
            )
        )

    if filters:
        base = base.where(*filters)

    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()

    # Loan numbers are stored as text but are numeric; order on the digits so
    # "1000" sorts after "999". Non-numeric synthesised numbers sort last.
    loan_number_numeric = cast(
        func.nullif(func.regexp_replace(Loan.loan_number, r"\D", "", "g"), ""),
        BigInteger,
    )
    sort_columns = {
        "loan_number": loan_number_numeric,
        "year": Loan.persian_year,
        "total": Loan.total_amount,
        "remaining": func.coalesce(paid_rem.c.remaining, 0),
    }
    sort_col = sort_columns.get(sort) if sort else None
    order_by: list[Any]
    if sort_col is not None:
        primary = sort_col.desc() if sort_dir == "desc" else sort_col.asc()
        order_by = [nulls_last(primary), Loan.persian_year.desc(), loan_number_numeric]
    else:
        order_by = [Loan.persian_year.desc(), Loan.loan_number]

    offset, limit = page_bounds(page, page_size)
    page_q = base.order_by(*order_by).offset(offset).limit(limit)
    rows = (await session.execute(page_q)).all()

    items = [
        LoanListItem(
            id=row.id,
            persian_year=row.persian_year,
            loan_number=row.loan_number,
            channel_number=row.channel_number,
            topic_name=row.topic_name,
            borrower_name=row.borrower_name,
            liaison_label=row.liaison_label,
            total=Decimal(row.total_amount),
            paid=Decimal(row.paid),
            remaining=Decimal(row.remaining),
            status="settled" if Decimal(row.remaining) == 0 else "active",
        )
        for row in rows
    ]
    return Page[LoanListItem](items=items, total=total, page=page, page_size=limit)


# --------------------------------------------------------------------- detail


async def get_loan_detail(session: AsyncSession, loan_id: int) -> LoanDetailResponse | None:
    loan_row = (
        await session.execute(
            select(Loan, LoanTopic)
            .join(LoanTopic, LoanTopic.id == Loan.topic_id)
            .where(Loan.id == loan_id)
        )
    ).first()
    if loan_row is None:
        return None
    loan_obj, topic_obj = loan_row

    guarantor: PersonRef | None = None
    if loan_obj.guarantor_id is not None:
        g = (
            await session.execute(
                select(Person.id, Person.full_name, Person.phone).where(
                    Person.id == loan_obj.guarantor_id
                )
            )
        ).first()
        if g is not None:
            guarantor = PersonRef(id=g.id, full_name=g.full_name, phone=g.phone)

    # All parties + their person info
    parties_rows = (
        await session.execute(
            select(
                LoanParty.id,
                LoanParty.role,
                LoanParty.amount,
                LoanParty.display_order,
                Person.id.label("person_id"),
                Person.full_name,
                Person.phone,
            )
            .select_from(LoanParty)
            .join(Person, Person.id == LoanParty.person_id)
            .where(LoanParty.loan_id == loan_id)
            .order_by(LoanParty.display_order)
        )
    ).all()

    borrowers: list[LoanPartyRef] = []
    lender_parties: dict[int, LenderPartyRef] = {}
    for row in parties_rows:
        person_ref = PersonRef(id=row.person_id, full_name=row.full_name, phone=row.phone)
        if row.role == LoanPartyRole.borrower:
            borrowers.append(
                LoanPartyRef(
                    party_id=row.id,
                    person=person_ref,
                    amount=Decimal(row.amount),
                )
            )
        else:
            lender_parties[row.id] = LenderPartyRef(
                party_id=row.id,
                person=person_ref,
                amount=Decimal(row.amount),
                paid=Decimal(0),
                remaining=Decimal(0),
                installments=[],
            )

    # Installments + per-lender paid/remaining
    if lender_parties:
        inst_rows = (
            await session.execute(
                select(
                    Installment.loan_party_id,
                    Installment.due_persian_year,
                    Installment.due_persian_month,
                    Installment.due_day_of_month,
                    Installment.amount,
                    Installment.status,
                )
                .where(Installment.loan_party_id.in_(lender_parties.keys()))
                .order_by(
                    Installment.due_persian_year,
                    Installment.due_persian_month,
                    Installment.due_day_of_month,
                )
            )
        ).all()
        paid_by_party: dict[int, Decimal] = defaultdict(lambda: Decimal(0))
        remaining_by_party: dict[int, Decimal] = defaultdict(lambda: Decimal(0))
        for irow in inst_rows:
            inst_status = InstallmentStatus(irow.status)
            lender_parties[irow.loan_party_id].installments.append(
                InstallmentRef(
                    due_persian_year=irow.due_persian_year,
                    due_persian_month=irow.due_persian_month,
                    due_day_of_month=irow.due_day_of_month,
                    amount=Decimal(irow.amount),
                    status=inst_status,
                )
            )
            if inst_status is InstallmentStatus.paid:
                paid_by_party[irow.loan_party_id] += Decimal(irow.amount)
            else:
                remaining_by_party[irow.loan_party_id] += Decimal(irow.amount)
        for pid, lp in lender_parties.items():
            lp.paid = paid_by_party[pid]
            lp.remaining = remaining_by_party[pid]

    lenders = list(lender_parties.values())
    totals = LoanTotals(
        total=Decimal(loan_obj.total_amount),
        paid=sum((lp.paid for lp in lenders), Decimal(0)),
        remaining=sum((lp.remaining for lp in lenders), Decimal(0)),
        settled=all(lp.remaining == 0 for lp in lenders),
    )

    return LoanDetailResponse(
        loan={
            "id": loan_obj.id,
            "persian_year": loan_obj.persian_year,
            "loan_number": loan_obj.loan_number,
            "channel_number": loan_obj.channel_number,
            "total_amount": str(loan_obj.total_amount),
            "liaison_label": loan_obj.liaison_label,
            "description": loan_obj.description,
        },
        topic=TopicRef(id=topic_obj.id, name=topic_obj.name),
        guarantor=guarantor,
        borrowers=borrowers,
        lenders=lenders,
        totals=totals,
    )
