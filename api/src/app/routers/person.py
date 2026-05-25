"""Persons router — list (with search/filters) + detail."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.db import SessionDep
from app.schemas.person import PersonDetailResponse, PersonListItem
from app.services.person import get_person_detail, list_persons
from app.services.query import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Page

router = APIRouter(prefix="/api/persons", tags=["persons"])


@router.get(
    "",
    response_model=Page[PersonListItem],
    summary="Paginated person list with Persian-fuzzy search and filters",
)
async def list_(
    session: SessionDep,
    q: str | None = Query(default=None, description="Persian-fuzzy name + phone-substring"),
    verified_only: bool = Query(default=False),
    has_debt: bool = Query(default=False),
    has_receivable: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> Page[PersonListItem]:
    return await list_persons(
        session,
        q=q,
        verified_only=verified_only,
        has_debt=has_debt,
        has_receivable=has_receivable,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{person_id}",
    response_model=PersonDetailResponse,
    summary="Per-person profile",
)
async def detail(session: SessionDep, person_id: int) -> PersonDetailResponse:
    out = await get_person_detail(session, person_id)
    if out is None:
        raise HTTPException(status_code=404, detail="person not found")
    return out
