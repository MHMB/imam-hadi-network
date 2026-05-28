"""Overdue installments router."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.db import SessionDep
from app.schemas.overdue import OverdueInstallmentItem
from app.services.overdue import list_overdue
from app.services.query import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Page

router = APIRouter(prefix="/api/installments", tags=["overdue"])


@router.get(
    "/overdue",
    response_model=Page[OverdueInstallmentItem],
    summary="Lender-side unpaid installments past their due date",
)
async def overdue(
    session: SessionDep,
    min_days_overdue: int = Query(default=0, ge=0, le=10_000),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> Page[OverdueInstallmentItem]:
    return await list_overdue(
        session,
        min_days_overdue=min_days_overdue,
        page=page,
        page_size=page_size,
    )
