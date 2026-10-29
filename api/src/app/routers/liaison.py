"""رابط labels and their links to people."""

from __future__ import annotations

from fastapi import APIRouter

from app.auth import CurrentUser
from app.db import SessionDep
from app.schemas.person import LiaisonLink, LiaisonRow
from app.services.liaison import link_liaison, list_liaisons

router = APIRouter(prefix="/api/liaisons", tags=["liaisons"])


@router.get("", response_model=list[LiaisonRow], summary="Every رابط label and its person")
async def liaisons(session: SessionDep) -> list[LiaisonRow]:
    return await list_liaisons(session)


@router.put("", response_model=list[LiaisonRow], summary="Link a رابط label to a person (or none)")
async def link(session: SessionDep, user: CurrentUser, body: LiaisonLink) -> list[LiaisonRow]:
    await link_liaison(session, user, body)
    return await list_liaisons(session)
