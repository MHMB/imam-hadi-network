"""Persons router — list (with search/filters) + detail."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.auth import CurrentUser
from app.db import SessionDep
from app.schemas.loan_write import CreatedResponse, PersonCreate
from app.schemas.person import (
    GuarantorOption,
    PersonDetailResponse,
    PersonListItem,
    PersonMerge,
    PersonUpdate,
)
from app.services.person import get_person_detail, list_guarantor_options, list_persons
from app.services.person_edit import create_person, update_person
from app.services.person_merge import merge_persons
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
    guarantor_id: int | None = Query(default=None, description="Member guarantor (main slot)"),
    sort: str | None = Query(default=None, pattern="^(name|lent|borrowed|net|overdue)$"),
    sort_dir: str = Query(default="asc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> Page[PersonListItem]:
    return await list_persons(
        session,
        q=q,
        verified_only=verified_only,
        has_debt=has_debt,
        has_receivable=has_receivable,
        guarantor_id=guarantor_id,
        sort=sort,
        sort_dir=sort_dir,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/guarantors",
    response_model=list[GuarantorOption],
    summary="Member guarantors for the persons-list filter",
)
async def guarantors(session: SessionDep) -> list[GuarantorOption]:
    return await list_guarantor_options(session)


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


@router.post("", response_model=CreatedResponse, status_code=201, summary="Add a member")
async def create(session: SessionDep, user: CurrentUser, body: PersonCreate) -> CreatedResponse:
    person = await create_person(session, user, body.full_name, body.phone)
    return CreatedResponse(id=person.id)


@router.patch(
    "/{person_id}",
    response_model=PersonDetailResponse,
    summary="Edit a person's profile (phone required); every change is audited",
)
async def update(
    session: SessionDep, user: CurrentUser, person_id: int, body: PersonUpdate
) -> PersonDetailResponse:
    if await update_person(session, user, person_id, body) is None:
        raise HTTPException(status_code=404, detail="person not found")
    out = await get_person_detail(session, person_id)
    assert out is not None
    return out


@router.post(
    "/{person_id}/merge",
    response_model=PersonDetailResponse,
    summary="Fold duplicate persons into this one; their names stay mapped here on import",
)
async def merge(
    session: SessionDep, user: CurrentUser, person_id: int, body: PersonMerge
) -> PersonDetailResponse:
    if await merge_persons(session, user, person_id, body) is None:
        raise HTTPException(status_code=404, detail="person not found")
    out = await get_person_detail(session, person_id)
    assert out is not None
    return out
