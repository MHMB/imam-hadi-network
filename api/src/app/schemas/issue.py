"""Response shapes for /api/issues and /api/imports."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import ImportStatus, IssueCategory, IssueSeverity


class DataIssueItem(BaseModel):
    id: int
    import_id: int
    severity: IssueSeverity
    category: IssueCategory
    message: str
    sheet: str | None = None
    cell: str | None = None
    context: dict[str, Any] | None = None


class ImportListItem(BaseModel):
    id: int
    uploaded_at: datetime
    source_filename: str
    source_sha256: str
    years_imported: list[int]
    status: ImportStatus
    duration_ms: int | None = None
    error_message: str | None = None
    issue_count: int = Field(ge=0)
    error_count: int = Field(ge=0)


class ImportDetailResponse(ImportListItem):
    report: dict[str, Any]
