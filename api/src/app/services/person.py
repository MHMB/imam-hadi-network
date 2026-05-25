"""Person list + detail queries.

Persian-aware name search uses ``pg_trgm`` similarity over the
normalised form of ``person.full_name``.  We normalise both the query
and the stored value the same way (``normalize_persian_name``) so
admins typing Arabic ye/kaf still hit Persian records.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

import jdatetime
from sqlalchemy import case, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Installment,
    Loan,
    LoanParty,
    Person,
    PersonGuarantor,
)
from app.models.enums import (
    GuarantorRole,
    InstallmentStatus,
    LoanPartyRole,
)
from app.schemas.person import (
    PersonDetailResponse,
    PersonGuarantorRef,
    PersonInstallmentRef,
    PersonLifetime,
    PersonListItem,
    PersonRef,
    PersonYearBreakdown,
)
from app.services.query import Page, normalize_persian_name, page_bounds


def _today_jalali() -> tuple[int, int, int]:
    g = jdatetime.date.fromgregorian(date=datetime.now().date())
    return (g.year, g.month, g.day)


# --------------------------------------------------------------------- rollup CTE


def _rollup_subq() -> Any:
    """One CTE-equivalent subquery: per-person totals + outstandings.

    Columns:
        person_id, total_lent, outstanding_receivable,
        total_borrowed, outstanding_debt.

    Built by joining LoanParty → (Installment | borrower-counterpart-installments)
    once, and bucketing with conditional SUMs so we get all four rollups in
    a single scan.  Persons with no participation get zero via outer-join in
    the consumer.
    """
    lender_lp = LoanParty.__table__.alias("lender_lp")
    borrower_lp = LoanParty.__table__.alias("borrower_lp")
    inst = Installment.__table__.alias("inst")

    # Lender side aggregates — two separate subqueries so an installment count
    # of N for a single party doesn't multiply the lender amount by N when
    # joined.
    lender_total_subq = (
        select(
            lender_lp.c.person_id.label("person_id"),
            func.coalesce(func.sum(lender_lp.c.amount), 0).label("total_lent"),
        )
        .where(lender_lp.c.role == LoanPartyRole.lender.value)
        .group_by(lender_lp.c.person_id)
        .subquery()
    )
    lender_outstanding_subq = (
        select(
            lender_lp.c.person_id.label("person_id"),
            func.coalesce(func.sum(inst.c.amount), 0).label("outstanding_receivable"),
        )
        .select_from(lender_lp)
        .join(inst, inst.c.loan_party_id == lender_lp.c.id)
        .where(
            lender_lp.c.role == LoanPartyRole.lender.value,
            inst.c.status == InstallmentStatus.unpaid.value,
        )
        .group_by(lender_lp.c.person_id)
        .subquery()
    )

    # Borrower side: total borrowed = Σ borrower-party amount.
    # outstanding debt = Σ unpaid lender installments on loans this person
    # borrowed.
    borrower_subq = (
        select(
            borrower_lp.c.person_id.label("person_id"),
            func.coalesce(func.sum(borrower_lp.c.amount), 0).label("total_borrowed"),
        )
        .where(borrower_lp.c.role == LoanPartyRole.borrower.value)
        .group_by(borrower_lp.c.person_id)
        .subquery()
    )
    borrower_debt_subq = (
        select(
            borrower_lp.c.person_id.label("person_id"),
            func.coalesce(func.sum(inst.c.amount), 0).label("outstanding_debt"),
        )
        .select_from(borrower_lp)
        .join(lender_lp, lender_lp.c.loan_id == borrower_lp.c.loan_id)
        .join(inst, inst.c.loan_party_id == lender_lp.c.id)
        .where(
            borrower_lp.c.role == LoanPartyRole.borrower.value,
            lender_lp.c.role == LoanPartyRole.lender.value,
            inst.c.status == InstallmentStatus.unpaid.value,
        )
        .group_by(borrower_lp.c.person_id)
        .subquery()
    )

    return (
        select(
            Person.id.label("person_id"),
            func.coalesce(lender_total_subq.c.total_lent, 0).label("total_lent"),
            func.coalesce(lender_outstanding_subq.c.outstanding_receivable, 0).label(
                "outstanding_receivable"
            ),
            func.coalesce(borrower_subq.c.total_borrowed, 0).label("total_borrowed"),
            func.coalesce(borrower_debt_subq.c.outstanding_debt, 0).label("outstanding_debt"),
        )
        .select_from(Person)
        .join(lender_total_subq, lender_total_subq.c.person_id == Person.id, isouter=True)
        .join(
            lender_outstanding_subq,
            lender_outstanding_subq.c.person_id == Person.id,
            isouter=True,
        )
        .join(borrower_subq, borrower_subq.c.person_id == Person.id, isouter=True)
        .join(borrower_debt_subq, borrower_debt_subq.c.person_id == Person.id, isouter=True)
        .subquery()
    )


def _row_to_list_item(person_row: Any, rollup_row: Any) -> PersonListItem:
    receivable = Decimal(rollup_row.outstanding_receivable)
    debt = Decimal(rollup_row.outstanding_debt)
    return PersonListItem(
        id=person_row.id,
        full_name=person_row.full_name,
        phone=person_row.phone,
        is_verified=person_row.is_verified,
        total_lent=Decimal(rollup_row.total_lent),
        total_borrowed=Decimal(rollup_row.total_borrowed),
        outstanding_receivable=receivable,
        outstanding_debt=debt,
        net_capital=receivable - debt,
    )


# --------------------------------------------------------------------- list


async def list_persons(
    session: AsyncSession,
    *,
    q: str | None = None,
    verified_only: bool = False,
    has_debt: bool = False,
    has_receivable: bool = False,
    page: int = 1,
    page_size: int = 50,
) -> Page[PersonListItem]:
    """Paginated person list with search + flags."""
    rollup = _rollup_subq()

    base = (
        select(
            Person.id,
            Person.full_name,
            Person.phone,
            Person.is_verified,
            rollup.c.total_lent,
            rollup.c.outstanding_receivable,
            rollup.c.total_borrowed,
            rollup.c.outstanding_debt,
        )
        .select_from(Person)
        .join(rollup, rollup.c.person_id == Person.id, isouter=True)
    )

    filters: list[Any] = []
    if verified_only:
        filters.append(Person.is_verified.is_(True))
    if has_debt:
        filters.append(func.coalesce(rollup.c.outstanding_debt, 0) > 0)
    if has_receivable:
        filters.append(func.coalesce(rollup.c.outstanding_receivable, 0) > 0)
    if q:
        normalised = normalize_persian_name(q)
        if normalised:
            # Two complementary signals: trigram similarity on the full_name
            # (for fuzzy Persian match) OR a digits-only phone substring match.
            digits_only = "".join(c for c in normalised if c.isdigit())
            similar_clause = func.lower(Person.full_name).op("%")(normalised)
            if digits_only:
                phone_clause = Person.phone.icontains(digits_only)
                filters.append(or_(similar_clause, phone_clause))
            else:
                filters.append(similar_clause)
    if filters:
        base = base.where(*filters)

    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()

    offset, limit = page_bounds(page, page_size)
    page_q = base.order_by(Person.full_name).offset(offset).limit(limit)
    rows = (await session.execute(page_q)).all()

    return Page[PersonListItem](
        items=[_row_to_list_item(row, row) for row in rows],
        total=total,
        page=page,
        page_size=limit,
    )


# --------------------------------------------------------------------- detail


async def get_person_detail(session: AsyncSession, person_id: int) -> PersonDetailResponse | None:
    rollup = _rollup_subq()
    row = (
        await session.execute(
            select(
                Person.id,
                Person.full_name,
                Person.phone,
                Person.is_verified,
                rollup.c.total_lent,
                rollup.c.outstanding_receivable,
                rollup.c.total_borrowed,
                rollup.c.outstanding_debt,
            )
            .select_from(Person)
            .join(rollup, rollup.c.person_id == Person.id, isouter=True)
            .where(Person.id == person_id)
        )
    ).first()
    if row is None:
        return None
    list_item = _row_to_list_item(row, row)

    guarantors = await _person_guarantors(session, person_id)
    by_year = await _person_year_breakdown(session, person_id)
    upcoming, overdue = await _person_installments(session, person_id)

    return PersonDetailResponse(
        person=list_item,
        guarantors=guarantors,
        by_year=by_year,
        lifetime=PersonLifetime(
            receivable=list_item.outstanding_receivable,
            debt=list_item.outstanding_debt,
            net_capital=list_item.net_capital,
        ),
        upcoming=upcoming,
        overdue=overdue,
    )


async def _person_guarantors(session: AsyncSession, person_id: int) -> list[PersonGuarantorRef]:
    rows = (
        await session.execute(
            select(PersonGuarantor.role, Person.id, Person.full_name, Person.phone)
            .select_from(PersonGuarantor)
            .join(Person, Person.id == PersonGuarantor.guarantor_id)
            .where(PersonGuarantor.person_id == person_id)
            .order_by(PersonGuarantor.role)
        )
    ).all()
    return [
        PersonGuarantorRef(
            role=GuarantorRole(role.value if hasattr(role, "value") else role),
            person=PersonRef(id=pid, full_name=name, phone=phone),
        )
        for role, pid, name, phone in rows
    ]


async def _person_year_breakdown(
    session: AsyncSession, person_id: int
) -> list[PersonYearBreakdown]:
    # Borrower side per year: loan count + total
    borrower_total_rows = (
        await session.execute(
            select(
                Loan.persian_year,
                func.count(func.distinct(Loan.id)).label("loans_count"),
                func.coalesce(func.sum(LoanParty.amount), 0).label("total"),
            )
            .select_from(LoanParty)
            .join(Loan, Loan.id == LoanParty.loan_id)
            .where(
                LoanParty.role == LoanPartyRole.borrower,
                LoanParty.person_id == person_id,
            )
            .group_by(Loan.persian_year)
        )
    ).all()
    borrower_total_by_year: dict[int, tuple[int, Decimal]] = {
        row[0]: (row[1], Decimal(row[2])) for row in borrower_total_rows
    }

    # Borrower side paid + remaining per year (from lender-side installments
    # on loans this person borrowed)
    borrower_paid_rows = (
        await session.execute(
            select(
                Loan.persian_year,
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
            .where(
                LoanParty.role == LoanPartyRole.lender,
                Loan.id.in_(
                    select(LoanParty.loan_id).where(
                        LoanParty.role == LoanPartyRole.borrower,
                        LoanParty.person_id == person_id,
                    )
                ),
            )
            .group_by(Loan.persian_year)
        )
    ).all()
    borrower_paid_by_year: dict[int, tuple[Decimal, Decimal]] = {
        row[0]: (Decimal(row[1]), Decimal(row[2])) for row in borrower_paid_rows
    }

    # Lender side per year: parties count + total — computed WITHOUT joining
    # installments (join-inflation would multiply LoanParty.amount by
    # installment count).
    lender_total_rows = (
        await session.execute(
            select(
                Loan.persian_year,
                func.count(func.distinct(LoanParty.id)).label("parties_count"),
                func.coalesce(func.sum(LoanParty.amount), 0).label("total"),
            )
            .select_from(LoanParty)
            .join(Loan, Loan.id == LoanParty.loan_id)
            .where(
                LoanParty.role == LoanPartyRole.lender,
                LoanParty.person_id == person_id,
            )
            .group_by(Loan.persian_year)
        )
    ).all()
    # Paid + remaining come from the installment table, joined to LoanParty.
    lender_paid_rows = (
        await session.execute(
            select(
                Loan.persian_year,
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
            .select_from(LoanParty)
            .join(Loan, Loan.id == LoanParty.loan_id)
            .join(Installment, Installment.loan_party_id == LoanParty.id)
            .where(
                LoanParty.role == LoanPartyRole.lender,
                LoanParty.person_id == person_id,
            )
            .group_by(Loan.persian_year)
        )
    ).all()
    lender_paid_by_year: dict[int, tuple[Decimal, Decimal]] = {
        row[0]: (Decimal(row[1]), Decimal(row[2])) for row in lender_paid_rows
    }
    lender_by_year: dict[int, tuple[int, Decimal, Decimal, Decimal]] = {}
    for row in lender_total_rows:
        year, parties_count, total = row
        paid, remaining = lender_paid_by_year.get(year, (Decimal(0), Decimal(0)))
        lender_by_year[year] = (parties_count, Decimal(total), paid, remaining)

    years = sorted(set(borrower_total_by_year) | set(lender_by_year))
    out: list[PersonYearBreakdown] = []
    for year in years:
        b_count, b_total = borrower_total_by_year.get(year, (0, Decimal(0)))
        b_paid, b_remaining = borrower_paid_by_year.get(year, (Decimal(0), Decimal(0)))
        l_count, l_total, l_paid, l_remaining = lender_by_year.get(
            year, (0, Decimal(0), Decimal(0), Decimal(0))
        )
        out.append(
            PersonYearBreakdown(
                year=year,
                as_borrower_loans=b_count,
                as_borrower_total=b_total,
                as_borrower_paid=b_paid,
                as_borrower_remaining=b_remaining,
                as_lender_parties=l_count,
                as_lender_total=l_total,
                as_lender_paid=l_paid,
                as_lender_remaining=l_remaining,
            )
        )
    return out


async def _person_installments(
    session: AsyncSession, person_id: int
) -> tuple[list[PersonInstallmentRef], list[PersonInstallmentRef]]:
    """Return (upcoming, overdue) installments touching this person on either side."""
    today_y, today_m, today_d = _today_jalali()

    # Counterparty (borrower) name for lender-side installments
    borrower_name_sq = (
        select(Person.full_name)
        .select_from(LoanParty)
        .join(Person, Person.id == LoanParty.person_id)
        .where(
            LoanParty.loan_id == Loan.id,
            LoanParty.role == LoanPartyRole.borrower,
        )
        .limit(1)
        .scalar_subquery()
    )

    lender_q = (
        select(
            Loan.id.label("loan_id"),
            Loan.loan_number.label("loan_number"),
            borrower_name_sq.label("counterparty_name"),
            Installment.due_persian_year.label("due_persian_year"),
            Installment.due_persian_month.label("due_persian_month"),
            Installment.due_day_of_month.label("due_day_of_month"),
            Installment.amount.label("amount"),
            Installment.status.label("status"),
            literal("lender").label("role"),
        )
        .select_from(Installment)
        .join(LoanParty, LoanParty.id == Installment.loan_party_id)
        .join(Loan, Loan.id == LoanParty.loan_id)
        .where(
            LoanParty.role == LoanPartyRole.lender,
            LoanParty.person_id == person_id,
            Installment.status == InstallmentStatus.unpaid,
        )
    )
    borrower_q = (
        select(
            Loan.id.label("loan_id"),
            Loan.loan_number.label("loan_number"),
            Person.full_name.label("counterparty_name"),
            Installment.due_persian_year.label("due_persian_year"),
            Installment.due_persian_month.label("due_persian_month"),
            Installment.due_day_of_month.label("due_day_of_month"),
            Installment.amount.label("amount"),
            Installment.status.label("status"),
            literal("borrower").label("role"),
        )
        .select_from(Installment)
        .join(LoanParty, LoanParty.id == Installment.loan_party_id)
        .join(Loan, Loan.id == LoanParty.loan_id)
        .join(Person, Person.id == LoanParty.person_id)
        .where(
            LoanParty.role == LoanPartyRole.lender,
            Loan.id.in_(
                select(LoanParty.loan_id).where(
                    LoanParty.role == LoanPartyRole.borrower,
                    LoanParty.person_id == person_id,
                )
            ),
            Installment.status == InstallmentStatus.unpaid,
        )
    )

    union_q = lender_q.union_all(borrower_q).subquery()
    rows = (
        await session.execute(
            select(union_q).order_by(
                union_q.c.due_persian_year,
                union_q.c.due_persian_month,
                union_q.c.due_day_of_month,
            )
        )
    ).all()

    upcoming: list[PersonInstallmentRef] = []
    overdue: list[PersonInstallmentRef] = []
    for row in rows:
        ref = PersonInstallmentRef(
            loan_id=row.loan_id,
            loan_number=row.loan_number,
            counterparty_name=row.counterparty_name or "",
            due_persian_year=row.due_persian_year,
            due_persian_month=row.due_persian_month,
            due_day_of_month=row.due_day_of_month,
            amount=Decimal(row.amount),
            status=InstallmentStatus(row.status),
            role=row.role,
        )
        due = (row.due_persian_year, row.due_persian_month, row.due_day_of_month)
        if due < (today_y, today_m, today_d):
            overdue.append(ref)
        else:
            upcoming.append(ref)

    # Cap upcoming to 10 (DESIGN.md §5.2 contract).
    return upcoming[:10], overdue
