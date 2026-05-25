"""Imports + data-quality issues routers (read-only).

Write side (POST /api/imports for xlsm upload) lands in P6.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.db import SessionDep
from app.models.enums import IssueCategory, IssueSeverity
from app.schemas.issue import DataIssueItem, ImportDetailResponse, ImportListItem
from app.services.issue import get_import_detail, list_imports, list_issues
from app.services.query import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Page

router = APIRouter(prefix="/api", tags=["imports"])

# Annotated query types — module-level so ruff B008 doesn't trip on
# Query(...) in function defaults.
PageQ = Annotated[int, Query(ge=1)]
PageSizeQ = Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)]
SeverityQ = Annotated[IssueSeverity | None, Query()]
CategoryQ = Annotated[IssueCategory | None, Query()]


@router.get("/imports", response_model=Page[ImportListItem], summary="Imports history")
async def imports_list(
    session: SessionDep,
    page: PageQ = 1,
    page_size: PageSizeQ = DEFAULT_PAGE_SIZE,
) -> Page[ImportListItem]:
    return await list_imports(session, page=page, page_size=page_size)


@router.get("/imports/{import_id}", response_model=ImportDetailResponse, summary="One import")
async def imports_detail(session: SessionDep, import_id: int) -> ImportDetailResponse:
    out = await get_import_detail(session, import_id)
    if out is None:
        raise HTTPException(status_code=404, detail="import not found")
    return out


@router.get(
    "/issues",
    response_model=Page[DataIssueItem],
    summary="DataIssue rows (defaults to latest import)",
)
async def issues_list(
    session: SessionDep,
    import_id: int | None = None,
    severity: SeverityQ = None,
    category: CategoryQ = None,
    page: PageQ = 1,
    page_size: PageSizeQ = DEFAULT_PAGE_SIZE,
) -> Page[DataIssueItem]:
    return await list_issues(
        session,
        import_id=import_id,
        severity=severity,
        category=category,
        page=page,
        page_size=page_size,
    )
