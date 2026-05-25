"""KPI router — single endpoint at ``GET /api/kpi``."""

from __future__ import annotations

from fastapi import APIRouter

from app.db import SessionDep
from app.schemas.kpi import KPIResponse
from app.services.kpi import get_kpi

router = APIRouter(prefix="/api", tags=["kpi"])


@router.get("/kpi", response_model=KPIResponse, summary="Dashboard KPIs")
async def kpi(session: SessionDep) -> KPIResponse:
    """Top-level counts and amounts for the home page (DESIGN.md §6.2.1)."""
    return await get_kpi(session)
