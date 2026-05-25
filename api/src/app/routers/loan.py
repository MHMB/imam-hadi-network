"""Loans router — list with filters + detail."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.db import SessionDep
from app.schemas.loan import LoanDetailResponse, LoanListItem
from app.services.loan import get_loan_detail, list_loans
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
