"""Recording payments against a loan's installments.

Rules (client decisions, DESIGN.md §7 Q2):
- By default money follows the schedule: oldest due installment first, ties
  broken by lender order.  The admin may instead give their own split.
- Whatever is not allocated to an installment is the borrower's *credit*.
  That only happens when the payment exceeds what is still owed (or the
  admin leaves part unallocated) and needs explicit confirmation.
- A payment is never deleted: voiding it removes its allocations from the
  installments and keeps the row for the record.
Every change goes through ``installment.amount_paid`` in the same
transaction, with the loan's installments row-locked.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import FieldError
from app.jalali import is_valid
from app.models import AppUser, Installment, Loan, LoanParty, Payment, PaymentAllocation, Person
from app.models.enums import InstallmentStatus, LoanPartyRole
from app.schemas.payment import (
    AllocationIn,
    AllocationOut,
    PaymentCreate,
    PaymentOut,
    PaymentPreview,
    ScheduleEdit,
)
from app.services.audit import record, snapshot
from app.services.loan_write import loan_state


@dataclass(slots=True)
class _Open:
    inst: Installment
    lender_name: str
    order: int

    @property
    def remaining(self) -> Decimal:
        return Decimal(self.inst.amount) - Decimal(self.inst.amount_paid)


async def _installments(session: AsyncSession, loan_id: int, *, lock: bool) -> list[_Open]:
    """The loan's lender installments in schedule order (oldest due, then lender order)."""
    stmt = (
        select(Installment, Person.full_name, LoanParty.display_order)
        .join(LoanParty, LoanParty.id == Installment.loan_party_id)
        .join(Person, Person.id == LoanParty.person_id)
        .where(LoanParty.loan_id == loan_id, LoanParty.role == LoanPartyRole.lender)
        .order_by(
            Installment.due_persian_year,
            Installment.due_persian_month,
            Installment.due_day_of_month,
            LoanParty.display_order,
            Installment.id,
        )
    )
    if lock:
        stmt = stmt.with_for_update(of=Installment)
    rows = (await session.execute(stmt)).all()
    return [_Open(inst=i, lender_name=name, order=order) for i, name, order in rows]


def _out(o: _Open, amount: Decimal, remaining_before: Decimal) -> AllocationOut:
    i = o.inst
    return AllocationOut(
        installment_id=i.id,
        lender_name=o.lender_name,
        due=(i.due_persian_year, i.due_persian_month, i.due_day_of_month),
        installment_amount=Decimal(i.amount),
        remaining_before=remaining_before,
        amount=amount,
    )


def _follow_schedule(open_: Sequence[_Open], amount: Decimal) -> tuple[list[AllocationIn], Decimal]:
    """Oldest-due-first split; returns (allocations, unallocated rest)."""
    left = amount
    out: list[AllocationIn] = []
    for o in open_:
        if left <= 0:
            break
        take = min(left, o.remaining)
        if take > 0:
            out.append(AllocationIn(installment_id=o.inst.id, amount=take))
            left -= take
    return out, left


async def _loan(session: AsyncSession, loan_id: int) -> Loan:
    loan = await session.get(Loan, loan_id)
    if loan is None:
        raise FieldError("loan_id", "این قرض پیدا نشد.", code="not_found")
    return loan


async def preview_payment(session: AsyncSession, loan_id: int, amount: Decimal) -> PaymentPreview:
    await _loan(session, loan_id)
    open_ = await _installments(session, loan_id, lock=False)
    allocs, credit = _follow_schedule(open_, amount)
    by_id = {o.inst.id: o for o in open_}
    owed = sum((o.remaining for o in open_), Decimal(0))
    return PaymentPreview(
        allocations=[
            _out(by_id[a.installment_id], a.amount, by_id[a.installment_id].remaining)
            for a in allocs
        ],
        credit=credit,
        remaining_after=owed - (amount - credit),
    )


async def record_payment(
    session: AsyncSession, user: AppUser, loan_id: int, body: PaymentCreate
) -> Payment:
    await _loan(session, loan_id)
    if not is_valid(body.paid.year, body.paid.month, body.paid.day):
        raise FieldError("paid", "تاریخ پرداخت معتبر نیست.")
    open_ = await _installments(session, loan_id, lock=True)
    by_id = {o.inst.id: o for o in open_}

    if body.allocations is None:
        allocs, _ = _follow_schedule(open_, body.amount)
    else:
        allocs = body.allocations
        if len({a.installment_id for a in allocs}) != len(allocs):
            raise FieldError("allocations", "یک قسط دو بار آمده است.")
        for a in allocs:
            o = by_id.get(a.installment_id)
            if o is None:
                raise FieldError("allocations", "این قسط متعلق به این قرض نیست.")
            if a.amount > o.remaining:
                raise FieldError(
                    "allocations",
                    f"به قسط {o.lender_name} بیش از مانده‌اش ({o.remaining}) اختصاص داده شده است.",
                )
    allocated = sum((a.amount for a in allocs), Decimal(0))
    if allocated > body.amount:
        raise FieldError("allocations", "جمع تقسیم از مبلغ پرداخت بیشتر است.")
    credit = body.amount - allocated
    if credit > 0 and not body.confirm_credit:
        raise FieldError(
            "amount",
            f"{credit} میلیون تومان از این پرداخت به هیچ قسطی نمی‌رسد و به‌عنوان طلب "
            "قرض‌گیرنده ثبت می‌شود. برای ادامه تأیید کنید.",
            code="credit_needs_confirmation",
        )

    payer = (
        await session.execute(
            select(LoanParty.person_id)
            .where(LoanParty.loan_id == loan_id, LoanParty.role == LoanPartyRole.borrower)
            .order_by(LoanParty.display_order)
            .limit(1)
        )
    ).scalar_one()
    payment = Payment(
        loan_id=loan_id,
        payer_id=payer,
        amount=body.amount,
        paid_persian_year=body.paid.year,
        paid_persian_month=body.paid.month,
        paid_persian_day=body.paid.day,
        credit=credit,
        note=(body.note or "").strip() or None,
        created_by=user.id,
    )
    session.add(payment)
    await session.flush()
    for a in allocs:
        inst = by_id[a.installment_id].inst
        session.add(
            PaymentAllocation(payment_id=payment.id, installment_id=inst.id, amount=a.amount)
        )
        _apply(inst, a.amount, (body.paid.year, body.paid.month, body.paid.day))
    await session.flush()
    await record(
        session,
        user,
        action="create",
        entity="payment",
        entity_id=payment.id,
        before=None,
        after={
            **snapshot(payment),
            "allocations": [a.model_dump(mode="json") for a in allocs],
        },
    )
    await session.commit()
    return payment


def _apply(inst: Installment, delta: Decimal, paid_on: tuple[int, int, int] | None) -> None:
    """Move ``amount_paid`` by ``delta`` and keep status / paid date consistent."""
    inst.amount_paid = Decimal(inst.amount_paid) + delta
    if inst.amount_paid == inst.amount:
        inst.status = InstallmentStatus.paid
        if paid_on is not None:
            inst.paid_persian_year, inst.paid_persian_month, inst.paid_persian_day = paid_on
    else:
        inst.status = InstallmentStatus.unpaid
        inst.paid_persian_year = inst.paid_persian_month = inst.paid_persian_day = None


async def void_payment(session: AsyncSession, user: AppUser, payment_id: int) -> Payment | None:
    payment = await session.get(Payment, payment_id, with_for_update=True)
    if payment is None:
        return None
    if payment.voided_at is not None:
        raise FieldError("payment_id", "این پرداخت قبلاً برگردانده شده است.")
    before = snapshot(payment)
    allocs = (
        (
            await session.execute(
                select(PaymentAllocation).where(PaymentAllocation.payment_id == payment.id)
            )
        )
        .scalars()
        .all()
    )
    insts = {
        i.id: i
        for i in (
            await session.execute(
                select(Installment)
                .where(Installment.id.in_([a.installment_id for a in allocs]))
                .with_for_update()
            )
        ).scalars()
    }
    for a in allocs:
        _apply(insts[a.installment_id], -Decimal(a.amount), None)
    payment.voided_at = datetime.now(UTC)
    payment.voided_by = user.id
    await session.flush()
    await record(
        session,
        user,
        action="void",
        entity="payment",
        entity_id=payment.id,
        before=before,
        after=snapshot(payment),
    )
    await session.commit()
    return payment


async def list_payments(session: AsyncSession, loan_id: int) -> list[PaymentOut]:
    open_ = {o.inst.id: o for o in await _installments(session, loan_id, lock=False)}
    rows = (
        await session.execute(
            select(Payment, AppUser.username)
            .outerjoin(AppUser, AppUser.id == Payment.created_by)
            .where(Payment.loan_id == loan_id)
            .order_by(Payment.created_at.desc(), Payment.id.desc())
        )
    ).all()
    allocs = (
        (
            await session.execute(
                select(PaymentAllocation).where(
                    PaymentAllocation.payment_id.in_([p.id for p, _ in rows])
                )
            )
        )
        .scalars()
        .all()
    )
    by_payment: dict[int, list[AllocationOut]] = {}
    for a in allocs:
        o = open_[a.installment_id]
        by_payment.setdefault(a.payment_id, []).append(_out(o, Decimal(a.amount), o.remaining))
    return [
        PaymentOut(
            id=p.id,
            amount=Decimal(p.amount),
            paid=(p.paid_persian_year, p.paid_persian_month, p.paid_persian_day),
            credit=Decimal(p.credit),
            note=p.note,
            created_by=username or "—",
            created_at=p.created_at,
            voided_at=p.voided_at,
            allocations=by_payment.get(p.id, []),
        )
        for p, username in rows
    ]


async def edit_schedule(
    session: AsyncSession, user: AppUser, loan_id: int, body: ScheduleEdit
) -> Loan:
    """Replace the unpaid part of the schedule.

    Each lender's rows must still add up to that lender's amount.  An
    installment that already received money keeps its id and cannot drop
    below what was paid on it; installments without payments can move,
    change or disappear, and new ones can be added.
    """
    loan = await _loan(session, loan_id)
    before = await loan_state(session, loan)
    parties = {
        p.id: p
        for p in (
            await session.execute(
                select(LoanParty).where(
                    LoanParty.loan_id == loan_id, LoanParty.role == LoanPartyRole.lender
                )
            )
        ).scalars()
    }
    existing = {o.inst.id: o.inst for o in await _installments(session, loan_id, lock=True)}
    for idx, ln in enumerate(body.lenders):
        party = parties.get(ln.party_id)
        if party is None:
            raise FieldError(f"lenders.{idx}", "این قرض‌دهنده متعلق به این قرض نیست.")
        total = sum((r.amount for r in ln.installments), Decimal(0))
        if total != party.amount:
            raise FieldError(
                f"lenders.{idx}",
                f"جمع اقساط ({total}) با مبلغ این قرض‌دهنده ({party.amount}) برابر نیست.",
            )
        kept: set[int] = set()
        for r in ln.installments:
            if not is_valid(r.year, r.month, r.day):
                raise FieldError(f"lenders.{idx}", f"تاریخ {r.year}/{r.month}/{r.day} معتبر نیست.")
            if r.id is not None:
                inst = existing.get(r.id)
                if inst is None or inst.loan_party_id != party.id:
                    raise FieldError(f"lenders.{idx}", "قسط نامعتبر است.")
                if r.amount < inst.amount_paid:
                    raise FieldError(
                        f"lenders.{idx}",
                        f"قسطی که {inst.amount_paid} از آن پرداخت شده نمی‌تواند کمتر از آن شود.",
                    )
                inst.due_persian_year, inst.due_persian_month, inst.due_day_of_month = (
                    r.year,
                    r.month,
                    r.day,
                )
                inst.amount = r.amount
                _apply(inst, Decimal(0), None)  # status follows the new amount
                kept.add(inst.id)
            else:
                session.add(
                    Installment(
                        loan_party_id=party.id,
                        due_persian_year=r.year,
                        due_persian_month=r.month,
                        due_day_of_month=r.day,
                        amount=r.amount,
                        status=InstallmentStatus.unpaid,
                    )
                )
        for inst in [i for i in existing.values() if i.loan_party_id == party.id]:
            if inst.id in kept:
                continue
            if inst.amount_paid > 0:
                raise FieldError(
                    f"lenders.{idx}",
                    "قسطی که پرداخت دارد را نمی‌توان حذف کرد؛ اول پرداخت را برگردانید.",
                )
            await session.delete(inst)
    await session.flush()
    await record(
        session,
        user,
        action="edit_schedule",
        entity="loan",
        entity_id=loan.id,
        before=before,
        after=await loan_state(session, loan),
    )
    await session.commit()
    return loan
