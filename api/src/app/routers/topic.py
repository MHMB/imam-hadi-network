"""Topics router — GET /api/topics?year=NNNN."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.db import SessionDep
from app.schemas.topic import TopicSummary
from app.services.topic import list_topics

router = APIRouter(prefix="/api", tags=["topics"])


@router.get(
    "/topics",
    response_model=list[TopicSummary],
    summary="Loan topics with per-year counts + outstanding",
)
async def topics(
    session: SessionDep,
    year: int | None = Query(default=None, ge=1300, le=1500, description="Filter by Jalali year"),
) -> list[TopicSummary]:
    return await list_topics(session, year=year)
