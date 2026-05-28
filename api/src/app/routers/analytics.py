"""Analytics router."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.db import SessionDep
from app.schemas.analytics import MonthlyAnalyticsResponse
from app.services.analytics import get_monthly_analytics

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get(
    "/monthly",
    response_model=MonthlyAnalyticsResponse,
    summary="Monthly analytics (default = previous completed Jalali month)",
)
async def monthly(
    session: SessionDep,
    year: int | None = Query(default=None, ge=1300, le=1500),
    month: int | None = Query(default=None, ge=1, le=12),
) -> MonthlyAnalyticsResponse:
    return await get_monthly_analytics(session, year=year, month=month)
