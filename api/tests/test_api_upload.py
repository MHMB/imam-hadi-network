"""Integration tests for ``POST /api/imports`` upload + background task."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.main import app
from app.models import Import

pytestmark = pytest.mark.integration

_WIPE_TABLES = (
    "data_issue",
    "installment",
    "loan_party",
    "loan",
    "import",
    "person_guarantor",
    "person",
)


@pytest.fixture
async def client_with_clean_db() -> AsyncIterator[AsyncClient]:
    engine = create_async_engine(str(settings.database_url))

    async def wipe() -> None:
        async with engine.begin() as conn:
            for t in _WIPE_TABLES:
                await conn.exec_driver_sql(f"DELETE FROM {t}")

    await wipe()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await wipe()
    await engine.dispose()


async def _poll_terminal(
    client: AsyncClient, import_id: int, timeout: float = 10.0
) -> dict[str, object]:
    """Poll /api/imports/{id} until status is success or failed."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        r = await client.get(f"/api/imports/{import_id}")
        if r.status_code == 200:
            body = r.json()
            if body["status"] in ("success", "failed"):
                return body
        await asyncio.sleep(0.1)
    raise AssertionError(f"import {import_id} did not reach terminal status within {timeout}s")


@pytest.mark.asyncio
async def test_upload_xlsm_creates_pending_import_then_succeeds(
    client_with_clean_db: AsyncClient,
    sample_xlsm_path: Path,
) -> None:
    with sample_xlsm_path.open("rb") as fh:
        files = [("files", (sample_xlsm_path.name, fh, "application/octet-stream"))]
        r = await client_with_clean_db.post("/api/imports", files=files)
    assert r.status_code == 202, r.text
    body = r.json()
    assert isinstance(body, list)
    assert len(body) == 1
    item = body[0]
    # Initial state: row exists, status pending OR success (if BG ran very fast).
    assert item["status"] in ("pending", "running", "success")
    import_id = item["id"]

    final = await _poll_terminal(client_with_clean_db, import_id)
    assert final["status"] == "success"
    # 9 loans / 21 persons from the sample
    assert final["report"]["loans"] == 9
    assert final["report"]["persons"] == 21
    assert sorted(final["years_imported"]) == [1404, 1405]


@pytest.mark.asyncio
async def test_upload_same_file_twice_is_deduped(
    client_with_clean_db: AsyncClient,
    sample_xlsm_path: Path,
) -> None:
    async def upload() -> dict[str, object]:
        with sample_xlsm_path.open("rb") as fh:
            files = [("files", (sample_xlsm_path.name, fh, "application/octet-stream"))]
            r = await client_with_clean_db.post("/api/imports", files=files)
        body = r.json()
        return body[0]

    first = await upload()
    await _poll_terminal(client_with_clean_db, first["id"])
    second = await upload()
    # Same row, no new Import.
    assert second["id"] == first["id"]
    # Both processing paths agree the file landed.
    assert second["status"] == "success"

    # Only one Import row in the DB.
    engine = create_async_engine(str(settings.database_url))
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    async with sessionmaker() as s:
        rows = (await s.execute(select(Import))).scalars().all()
    await engine.dispose()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_upload_rejects_non_xlsm(
    client_with_clean_db: AsyncClient,
) -> None:
    files = [("files", ("notes.txt", b"hello", "text/plain"))]
    r = await client_with_clean_db.post("/api/imports", files=files)
    assert r.status_code == 415, r.text


@pytest.mark.asyncio
async def test_upload_zero_files_400(client_with_clean_db: AsyncClient) -> None:
    r = await client_with_clean_db.post("/api/imports", files=[])
    # FastAPI may return 422 (validation) or our 400 — accept either.
    assert r.status_code in (400, 422)


@pytest.mark.asyncio
async def test_upload_failed_status_when_corrupt(
    client_with_clean_db: AsyncClient,
) -> None:
    # Bytes that openpyxl can't parse → background task marks status=failed
    # without re-raising; client sees an error_message on the Import row.
    files = [("files", ("broken.xlsm", b"not really an xlsm", "application/octet-stream"))]
    r = await client_with_clean_db.post("/api/imports", files=files)
    assert r.status_code == 202, r.text
    import_id = r.json()[0]["id"]
    final = await _poll_terminal(client_with_clean_db, import_id)
    assert final["status"] == "failed"
    assert isinstance(final["error_message"], str)
    assert final["error_message"], "expected non-empty error_message"


@pytest.mark.asyncio
async def test_imports_list_reflects_uploaded_row(
    client_with_clean_db: AsyncClient,
    sample_xlsm_path: Path,
) -> None:
    with sample_xlsm_path.open("rb") as fh:
        files = [("files", (sample_xlsm_path.name, fh, "application/octet-stream"))]
        r = await client_with_clean_db.post("/api/imports", files=files)
    import_id = r.json()[0]["id"]
    await _poll_terminal(client_with_clean_db, import_id)

    listing = (await client_with_clean_db.get("/api/imports")).json()
    assert listing["total"] == 1
    assert listing["items"][0]["id"] == import_id
    assert listing["items"][0]["status"] == "success"
