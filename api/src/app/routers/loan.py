"""Loans router — list with filters + detail."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.auth import CurrentUser
from app.db import SessionDep
from app.schemas.loan import LoanDetailResponse, LoanListItem
from app.schemas.loan_write import (
    CreatedResponse,
    LoanCreate,
    LoanUpdate,
    SchedulePreview,
    SchedulePreviewRequest,
)
from app.schemas.payment import (
    PaymentCreate,
    PaymentOut,
    PaymentPreview,
    PaymentPreviewRequest,
    ScheduleEdit,
)
from app.services.loan import get_loan_detail, list_loans
from app.services.loan_write import create_loan, preview_schedule, update_loan
from app.services.payment import (
    edit_schedule,
    list_payments,
    preview_payment,
    record_payment,
)
from app.services.query import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Page, parse_int_csv

router = APIRouter(prefix="/api/loans", tags=["loans"])


@router.get(
    "",
    response_model=Page[LoanListItem],
    summary="Paginated loan list with year/topic/status/person/liaison filters",
)
async def list_(
    session: SessionDep,
    year: int | None = Query(default=None, ge=1300, le=1500),
    topic_ids: str | None = Query(
        default=None, description="Comma-separated topic ids, e.g. '3,7'"
    ),
    status: str | None = Query(
        default=None, pattern="^(active|settled)$", description="active | settled"
    ),
    borrower_id: int | None = Query(default=None),
    lender_id: int | None = Query(default=None),
    liaison: str | None = Query(default=None),
    q: str | None = Query(default=None, description="Substring match on loan_number"),
    due_within_days: int | None = Query(
        default=None,
        ge=0,
        le=3650,
        description="Only loans with an unpaid installment due within N days from today",
    ),
    sort: str | None = Query(default=None, pattern="^(loan_number|year|total|remaining)$"),
    sort_dir: str = Query(default="asc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> Page[LoanListItem]:
    return await list_loans(
        session,
        year=year,
        topic_ids=parse_int_csv(topic_ids) or None,
        status=status,
        borrower_id=borrower_id,
        lender_id=lender_id,
        liaison=liaison,
        q=q,
        due_within_days=due_within_days,
        sort=sort,
        sort_dir=sort_dir,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{loan_id}",
    response_model=LoanDetailResponse,
    summary="Loan detail: borrowers, lenders, installments",
)
async def detail(session: SessionDep, loan_id: int) -> LoanDetailResponse:
    out = await get_loan_detail(session, loan_id)
    if out is None:
        raise HTTPException(status_code=404, detail="loan not found")
    return out


@router.post(
    "/schedule-preview",
    response_model=SchedulePreview,
    summary="Generate a pro-rata installment schedule («همه متناسب»)",
)
async def schedule_preview(body: SchedulePreviewRequest) -> SchedulePreview:
    return preview_schedule(body)


@router.post("", response_model=CreatedResponse, status_code=201, summary="Create a loan")
async def create(session: SessionDep, user: CurrentUser, body: LoanCreate) -> CreatedResponse:
    loan = await create_loan(session, user, body)
    return CreatedResponse(id=loan.id)


@router.patch("/{loan_id}", response_model=LoanDetailResponse, summary="Edit loan details")
async def update(
    session: SessionDep, user: CurrentUser, loan_id: int, body: LoanUpdate
) -> LoanDetailResponse:
    if await update_loan(session, user, loan_id, body) is None:
        raise HTTPException(status_code=404, detail="loan not found")
    out = await get_loan_detail(session, loan_id)
    assert out is not None
    return out


@router.post(
    "/{loan_id}/payments/preview",
    response_model=PaymentPreview,
    summary="How a payment would be split over the schedule",
)
async def payment_preview(
    session: SessionDep, loan_id: int, body: PaymentPreviewRequest
) -> PaymentPreview:
    return await preview_payment(session, loan_id, body.amount)


@router.post(
    "/{loan_id}/payments",
    response_model=list[PaymentOut],
    status_code=201,
    summary="Record a payment (schedule order, or the admin's split)",
)
async def payment_create(
    session: SessionDep, user: CurrentUser, loan_id: int, body: PaymentCreate
) -> list[PaymentOut]:
    await record_payment(session, user, loan_id, body)
    return await list_payments(session, loan_id)


@router.get("/{loan_id}/payments", response_model=list[PaymentOut], summary="Payments on a loan")
async def payments(session: SessionDep, loan_id: int) -> list[PaymentOut]:
    return await list_payments(session, loan_id)


@router.put(
    "/{loan_id}/schedule",
    response_model=LoanDetailResponse,
    summary="Edit the installment schedule (paid money stays put)",
)
async def schedule_edit(
    session: SessionDep, user: CurrentUser, loan_id: int, body: ScheduleEdit
) -> LoanDetailResponse:
    await edit_schedule(session, user, loan_id, body)
    out = await get_loan_detail(session, loan_id)
    assert out is not None
    return out
