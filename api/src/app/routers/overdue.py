"""Overdue installments router."""

from __future__ import annotations

import jdatetime
from fastapi import APIRouter, HTTPException, Query

from app.db import SessionDep
from app.schemas.overdue import OverdueInstallmentItem
from app.services.overdue import list_overdue
from app.services.query import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Page

router = APIRouter(prefix="/api/installments", tags=["overdue"])

JALALI_DATE = r"^\d{4}-\d{1,2}-\d{1,2}$"


def _jalali(value: str | None, name: str) -> tuple[int, int, int] | None:
    """`1405-07-01` → (1405, 7, 1); rejects impossible months/days."""
    if value is None:
        return None
    y, m, d = (int(p) for p in value.split("-"))
    try:
        jdatetime.date(y, m, d)
    except ValueError:
        raise HTTPException(
            status_code=422, detail=f"{name}: invalid Jalali date {value!r}"
        ) from None
    return (y, m, d)


@router.get(
    "/overdue",
    response_model=Page[OverdueInstallmentItem],
    summary="Lender-side unpaid installments past their due date",
)
async def overdue(
    session: SessionDep,
    min_days_overdue: int = Query(default=0, ge=0, le=10_000),
    year: int | None = Query(default=None, ge=1300, le=1500, description="Loan year"),
    due_from: str | None = Query(
        default=None, pattern=JALALI_DATE, description="Jalali YYYY-MM-DD"
    ),
    due_to: str | None = Query(default=None, pattern=JALALI_DATE, description="Jalali YYYY-MM-DD"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> Page[OverdueInstallmentItem]:
    return await list_overdue(
        session,
        min_days_overdue=min_days_overdue,
        year=year,
        due_from=_jalali(due_from, "due_from"),
        due_to=_jalali(due_to, "due_to"),
        page=page,
        page_size=page_size,
    )
