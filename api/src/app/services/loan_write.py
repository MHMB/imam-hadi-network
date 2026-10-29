"""Creating and editing loans, and the installment-schedule generator.

All money math lives here (never in the browser).  Amounts are million
toman with 3 decimals, i.e. 1,000-toman resolution.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import ROUND_DOWN, Decimal
from typing import Any

import jdatetime
from sqlalchemy import BigInteger, cast, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import FieldError
from app.jalali import add_months, is_valid
from app.models import AppUser, Installment, Loan, LoanParty, LoanTopic, Person
from app.models.enums import InstallmentStatus, LoanOrigin, LoanPartyRole
from app.schemas.loan_write import (
    JalaliDate,
    LenderSchedule,
    LoanCreate,
    LoanUpdate,
    ScheduledInstallment,
    SchedulePreview,
    SchedulePreviewRequest,
)
from app.services.audit import record, snapshot

STEP = Decimal("0.001")
_LOAN_NUMBER_LOCK = 7_340_001  # pg_advisory_xact_lock key for "next loan number"


def _today_year() -> int:
    return int(jdatetime.date.fromgregorian(date=date.today()).year)


def split_equal(amount: Decimal, months: int) -> list[Decimal]:
    """``amount`` in ``months`` equal parts; the rounding remainder goes on the last."""
    base = (amount / months).quantize(STEP, rounding=ROUND_DOWN)
    if base <= 0:
        raise FieldError("months", f"مبلغ {amount} برای {months} قسط کم است؛ تعداد ماه را کم کنید.")
    return [base] * (months - 1) + [amount - base * (months - 1)]


def preview_schedule(req: SchedulePreviewRequest) -> SchedulePreview:
    """Mode «همه متناسب»: every lender is repaid in the same months, pro rata."""
    fd = req.first_due
    if not is_valid(fd.year, fd.month, fd.day):
        raise FieldError("first_due", "تاریخ اولین قسط معتبر نیست.")
    dates = [add_months(fd.year, fd.month, fd.day, i) for i in range(req.months)]
    return SchedulePreview(
        lenders=[
            LenderSchedule(
                person_id=share.person_id,
                amount=share.amount,
                installments=[
                    ScheduledInstallment(year=y, month=m, day=d, amount=part)
                    for (y, m, d), part in zip(
                        dates, split_equal(share.amount, req.months), strict=True
                    )
                ],
            )
            for share in req.lenders
        ]
    )


def validate_schedule(lenders: Iterable[LenderSchedule]) -> None:
    """Mode «اولویت‌دار» (or any edited grid): each lender's row sums to their amount."""
    seen: set[int] = set()
    for i, ln in enumerate(lenders):
        if ln.person_id in seen:
            raise FieldError(f"lenders.{i}", "هر قرض‌دهنده فقط یک بار می‌آید؛ مبلغ‌ها را جمع کنید.")
        seen.add(ln.person_id)
        if not ln.installments:
            raise FieldError(f"lenders.{i}", "این قرض‌دهنده هیچ قسطی ندارد.")
        for inst in ln.installments:
            if not is_valid(inst.year, inst.month, inst.day):
                raise FieldError(
                    f"lenders.{i}", f"تاریخ {inst.year}/{inst.month}/{inst.day} معتبر نیست."
                )
        total = sum((inst.amount for inst in ln.installments), Decimal(0))
        if total != ln.amount:
            raise FieldError(
                f"lenders.{i}",
                f"جمع اقساط ({total}) با مبلغ این قرض‌دهنده ({ln.amount}) برابر نیست.",
            )


async def _require_people(session: AsyncSession, ids: dict[str, int | None]) -> None:
    wanted = {pid for pid in ids.values() if pid is not None}
    found = set((await session.execute(select(Person.id).where(Person.id.in_(wanted)))).scalars())
    for field, pid in ids.items():
        if pid is not None and pid not in found:
            raise FieldError(field, "این فرد پیدا نشد.")


async def _require_topic(session: AsyncSession, topic_id: int) -> None:
    if await session.get(LoanTopic, topic_id) is None:
        raise FieldError("topic_id", "این موضوع پیدا نشد.")


async def next_loan_number(session: AsyncSession) -> str:
    """Loan numbers are one sequence across years; serialised by an advisory lock."""
    await session.execute(text(f"SELECT pg_advisory_xact_lock({_LOAN_NUMBER_LOCK})"))
    current = (
        await session.execute(
            select(func.max(cast(func.substring(Loan.loan_number, r"^\d+"), BigInteger)))
        )
    ).scalar_one()
    return str((current or 0) + 1)


async def loan_state(session: AsyncSession, loan: Loan) -> dict[str, Any]:
    """Loan row + parties + installments, for the audit trail."""
    parties = (
        (await session.execute(select(LoanParty).where(LoanParty.loan_id == loan.id)))
        .scalars()
        .all()
    )
    insts = (
        (
            await session.execute(
                select(Installment).where(Installment.loan_party_id.in_([p.id for p in parties]))
            )
        )
        .scalars()
        .all()
    )
    return {
        **snapshot(loan),
        "parties": [snapshot(p) for p in parties],
        "installments": [snapshot(i) for i in insts],
    }


async def create_loan(session: AsyncSession, user: AppUser, body: LoanCreate) -> Loan:
    validate_schedule(body.lenders)
    lender_ids = [ln.person_id for ln in body.lenders]
    if body.borrower_id in lender_ids:
        raise FieldError("borrower_id", "قرض‌گیرنده نمی‌تواند قرض‌دهنده همین قرض باشد.")
    await _require_people(
        session,
        {
            "borrower_id": body.borrower_id,
            "guarantor_id": body.guarantor_id,
            "liaison_person_id": body.liaison_person_id,
            **{f"lenders.{i}": pid for i, pid in enumerate(lender_ids)},
        },
    )
    await _require_topic(session, body.topic_id)
    if body.issued and not is_valid(body.issued.year, body.issued.month, body.issued.day):
        raise FieldError("issued", "تاریخ پرداخت قرض معتبر نیست.")

    total = sum((ln.amount for ln in body.lenders), Decimal(0))
    year = body.persian_year or (body.issued.year if body.issued else _today_year())
    loan = Loan(
        persian_year=year,
        loan_number=await next_loan_number(session),
        total_amount=total,
        topic_id=body.topic_id,
        import_id=None,
        origin=LoanOrigin.app,
        guarantor_id=body.guarantor_id,
        liaison_label=body.liaison_label,
        liaison_person_id=body.liaison_person_id,
        source_platform=body.source_platform,
        description=(body.description or "").strip() or None,
        note_flagged=body.note_flagged,
        issued_persian_year=body.issued.year if body.issued else None,
        issued_persian_month=body.issued.month if body.issued else None,
        issued_persian_day=body.issued.day if body.issued else None,
        created_by=user.id,
    )
    session.add(loan)
    await session.flush()
    session.add(
        LoanParty(
            loan_id=loan.id,
            person_id=body.borrower_id,
            role=LoanPartyRole.borrower,
            amount=total,
            display_order=0,
        )
    )
    for order, ln in enumerate(body.lenders, start=1):
        party = LoanParty(
            loan_id=loan.id,
            person_id=ln.person_id,
            role=LoanPartyRole.lender,
            amount=ln.amount,
            display_order=order,
        )
        session.add(party)
        await session.flush()
        for inst in ln.installments:
            session.add(
                Installment(
                    loan_party_id=party.id,
                    due_persian_year=inst.year,
                    due_persian_month=inst.month,
                    due_day_of_month=inst.day,
                    amount=inst.amount,
                    status=InstallmentStatus.unpaid,
                )
            )
    await session.flush()
    await record(
        session,
        user,
        action="create",
        entity="loan",
        entity_id=loan.id,
        before=None,
        after=await loan_state(session, loan),
    )
    await session.commit()
    return loan


def _set_issued(loan: Loan, issued: JalaliDate | None) -> None:
    if issued is not None and not is_valid(issued.year, issued.month, issued.day):
        raise FieldError("issued", "تاریخ پرداخت قرض معتبر نیست.")
    loan.issued_persian_year = issued.year if issued else None
    loan.issued_persian_month = issued.month if issued else None
    loan.issued_persian_day = issued.day if issued else None


async def update_loan(
    session: AsyncSession, user: AppUser, loan_id: int, body: LoanUpdate
) -> Loan | None:
    loan = await session.get(Loan, loan_id, with_for_update=True)
    if loan is None:
        return None
    before = snapshot(loan)
    fields = body.model_fields_set
    await _require_people(
        session,
        {f: getattr(body, f) for f in ("guarantor_id", "liaison_person_id") if f in fields},
    )
    if "topic_id" in fields:
        if body.topic_id is None:
            raise FieldError("topic_id", "موضوع لازم است.")
        await _require_topic(session, body.topic_id)
        loan.topic_id = body.topic_id
    for f in ("guarantor_id", "liaison_person_id", "source_platform"):
        if f in fields:
            setattr(loan, f, getattr(body, f))
    if "description" in fields:
        loan.description = (body.description or "").strip() or None
    if "note_flagged" in fields:
        loan.note_flagged = bool(body.note_flagged)
    if "issued" in fields:
        _set_issued(loan, body.issued)
    await session.flush()
    after = snapshot(loan)
    if after != before:
        await record(
            session,
            user,
            action="update",
            entity="loan",
            entity_id=loan.id,
            before=before,
            after=after,
        )
    await session.commit()
    return loan
