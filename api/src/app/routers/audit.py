"""Current user + per-entity change history."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.auth import CurrentUser
from app.db import SessionDep
from app.schemas.audit import AuditEntry, MeResponse
from app.services.audit import history

router = APIRouter(prefix="/api", tags=["audit"])


@router.get("/me", response_model=MeResponse, summary="Who is signed in")
async def me(user: CurrentUser, session: SessionDep) -> MeResponse:
    await session.commit()  # persist a first-seen user
    return MeResponse(username=user.username, role="admin")


@router.get("/audit", response_model=list[AuditEntry], summary="Change history of one entity")
async def audit(
    session: SessionDep,
    entity: str = Query(pattern="^(loan|person|payment|installment|liaison|import)$"),
    entity_id: int = Query(ge=1),
) -> list[AuditEntry]:
    return await history(session, entity, entity_id)
