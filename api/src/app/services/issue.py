"""Imports + data-quality issue queries."""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DataIssue, Import
from app.models.enums import IssueCategory, IssueSeverity
from app.schemas.issue import DataIssueItem, ImportDetailResponse, ImportListItem
from app.services.query import Page, page_bounds


async def list_imports(
    session: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 50,
) -> Page[ImportListItem]:
    # Per-import (issue_count, error_count) via FILTER aggregate — Postgres
    # supports COUNT(*) FILTER (WHERE ...) natively.
    issue_counts_sq = (
        select(
            DataIssue.import_id.label("import_id"),
            func.count().label("issue_count"),
            func.count().filter(DataIssue.severity == IssueSeverity.error).label("error_count"),
        )
        .group_by(DataIssue.import_id)
        .subquery()
    )

    base = (
        select(
            Import,
            func.coalesce(issue_counts_sq.c.issue_count, 0).label("issue_count"),
            func.coalesce(issue_counts_sq.c.error_count, 0).label("error_count"),
        )
        .select_from(Import)
        .join(issue_counts_sq, issue_counts_sq.c.import_id == Import.id, isouter=True)
        .order_by(Import.uploaded_at.desc(), Import.id.desc())
    )

    total = (await session.execute(select(func.count()).select_from(Import))).scalar_one()
    offset, limit = page_bounds(page, page_size)
    rows = (await session.execute(base.offset(offset).limit(limit))).all()

    items = [_to_list_item(imp, issue_count, error_count) for imp, issue_count, error_count in rows]
    return Page[ImportListItem](items=items, total=total, page=page, page_size=limit)


async def get_import_detail(
    session: AsyncSession, import_id: int
) -> ImportDetailResponse | None:
    row = (
        await session.execute(
            select(
                Import,
                func.count(DataIssue.id).label("issue_count"),
                func.count(DataIssue.id)
                .filter(DataIssue.severity == IssueSeverity.error)
                .label("error_count"),
            )
            .select_from(Import)
            .join(DataIssue, DataIssue.import_id == Import.id, isouter=True)
            .where(Import.id == import_id)
            .group_by(Import.id)
        )
    ).first()
    if row is None:
        return None
    imp, issue_count, error_count = row
    list_item = _to_list_item(imp, issue_count, error_count)
    return ImportDetailResponse(**list_item.model_dump(), report=cast(dict[str, Any], imp.report))


async def list_issues(
    session: AsyncSession,
    *,
    import_id: int | None = None,
    severity: IssueSeverity | None = None,
    category: IssueCategory | None = None,
    page: int = 1,
    page_size: int = 50,
) -> Page[DataIssueItem]:
    """Filter + paginate DataIssue rows.

    ``import_id=None`` defaults to the latest successful import — the
    Data Quality page (P7) hits this without specifying an id.
    """
    if import_id is None:
        latest_row = (
            await session.execute(
                select(Import.id).order_by(Import.uploaded_at.desc()).limit(1)
            )
        ).first()
        if latest_row is None:
            return Page[DataIssueItem](items=[], total=0, page=page, page_size=page_size)
        import_id = latest_row[0]

    filters: list[Any] = [DataIssue.import_id == import_id]
    if severity is not None:
        filters.append(DataIssue.severity == severity)
    if category is not None:
        filters.append(DataIssue.category == category)

    total = (
        await session.execute(
            select(func.count()).select_from(DataIssue).where(*filters)
        )
    ).scalar_one()

    offset, limit = page_bounds(page, page_size)
    rows = (
        await session.execute(
            select(DataIssue)
            .where(*filters)
            .order_by(DataIssue.severity, DataIssue.category, DataIssue.id)
            .offset(offset)
            .limit(limit)
        )
    ).scalars().all()

    items = [
        DataIssueItem(
            id=row.id,
            import_id=row.import_id,
            severity=row.severity,
            category=row.category,
            message=row.message,
            sheet=row.sheet,
            cell=row.cell,
            context=row.context,
        )
        for row in rows
    ]
    return Page[DataIssueItem](items=items, total=total, page=page, page_size=limit)


def _to_list_item(imp: Import, issue_count: int, error_count: int) -> ImportListItem:
    return ImportListItem(
        id=imp.id,
        uploaded_at=imp.uploaded_at,
        source_filename=imp.source_filename,
        source_sha256=imp.source_sha256,
        years_imported=list(imp.years_imported),
        status=imp.status,
        duration_ms=imp.duration_ms,
        error_message=imp.error_message,
        issue_count=issue_count or 0,
        error_count=error_count or 0,
    )
