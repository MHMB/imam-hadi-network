"""Imports + data-quality issues routers (read-only).

Write side (POST /api/imports for xlsm upload) lands in P6.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, UploadFile

from app.db import SessionDep
from app.models.enums import IssueCategory, IssueSeverity
from app.schemas.issue import DataIssueItem, ImportDetailResponse, ImportListItem
from app.services.issue import get_import_detail, list_imports, list_issues
from app.services.query import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Page
from app.services.upload import (
    NotAnXlsm,
    UploadTooLarge,
    process_pending_import,
    save_upload_and_register,
)

router = APIRouter(prefix="/api", tags=["imports"])

# Annotated query types — module-level so ruff B008 doesn't trip on
# Query(...) in function defaults.
PageQ = Annotated[int, Query(ge=1)]
PageSizeQ = Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)]
SeverityQ = Annotated[IssueSeverity | None, Query()]
CategoryQ = Annotated[IssueCategory | None, Query()]


@router.post(
    "/imports",
    response_model=list[ImportListItem],
    status_code=202,
    summary="Upload one or more xlsm files; processed in background",
)
async def imports_upload(
    session: SessionDep,
    background: BackgroundTasks,
    files: Annotated[list[UploadFile], File(description="One or more .xlsm files")],
) -> list[ImportListItem]:
    """Multipart upload endpoint.

    For each uploaded file:
    - Compute sha256.  If a successful Import already has this sha, return it
      (deduped) without touching disk again or scheduling work.
    - Otherwise persist the file under ``upload_dir/<sha>.xlsm`` and create
      a fresh Import row with ``status=pending``.  Background task does the
      actual parse + validate + write.

    Returns 202 with the (possibly mixed dedup + pending) list of Import
    rows; client polls ``/api/imports/{id}`` until terminal status.
    """
    if not files:
        raise HTTPException(status_code=400, detail="no files uploaded")

    out: list[ImportListItem] = []
    for upload in files:
        try:
            row, deduped, path = await save_upload_and_register(session, upload)
        except UploadTooLarge as exc:
            raise HTTPException(status_code=413, detail=str(exc)) from exc
        except NotAnXlsm as exc:
            raise HTTPException(status_code=415, detail=str(exc)) from exc

        await session.commit()  # persist the Import row before scheduling the task

        if not deduped and path is not None:
            background.add_task(process_pending_import, row.id, path)

        out.append(
            ImportListItem(
                id=row.id,
                uploaded_at=row.uploaded_at,
                source_filename=row.source_filename,
                source_sha256=row.source_sha256,
                years_imported=list(row.years_imported),
                status=row.status,
                duration_ms=row.duration_ms,
                error_message=row.error_message,
                issue_count=0,
                error_count=0,
            )
        )
    return out


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
