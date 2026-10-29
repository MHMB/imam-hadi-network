"""Payment actions that are not scoped to a loan URL."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.auth import CurrentUser
from app.db import SessionDep
from app.schemas.payment import PaymentOut
from app.services.payment import list_payments, void_payment

router = APIRouter(prefix="/api/payments", tags=["payments"])


@router.post(
    "/{payment_id}/void",
    response_model=list[PaymentOut],
    summary="Undo a payment: its money leaves the installments; the row stays for the record",
)
async def void(session: SessionDep, user: CurrentUser, payment_id: int) -> list[PaymentOut]:
    payment = await void_payment(session, user, payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="payment not found")
    return await list_payments(session, payment.loan_id)
