"""Merging duplicate persons: references move, names become aliases, re-import keeps it."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncConnection, async_sessionmaker, create_async_engine

from app.config import settings
from app.importer.runner import parse_workbook
from app.importer.writer import write_parse_result

pytestmark = pytest.mark.integration


async def _sql(query: str) -> list[tuple[object, ...]]:
    engine = create_async_engine(str(settings.database_url))
    async with engine.begin() as conn:
        rows = await _rows(conn, query)
    await engine.dispose()
    return rows


async def _rows(conn: AsyncConnection, query: str) -> list[tuple[object, ...]]:
    return [tuple(r) for r in (await conn.exec_driver_sql(query)).all()]


async def _parties(name: str) -> int:
    rows = await _sql(
        "SELECT count(*) FROM loan_party lp JOIN person p ON p.id = lp.person_id "
        f"WHERE p.full_name = '{name}'"
    )
    return int(rows[0][0])  # type: ignore[call-overload]


@pytest.mark.asyncio
async def test_merge_moves_loans_and_survives_reimport(
    seeded_client: AsyncClient, sample_xlsm_path: Path
) -> None:
    # Two borrowers that never share a loan in the same role.
    (keep_id, keep_name, drop_id, drop_name), *_ = await _sql(
        "SELECT a.id, a.full_name, b.id, b.full_name FROM person a, person b "
        "WHERE a.id < b.id "
        "AND EXISTS (SELECT 1 FROM loan_party WHERE person_id = a.id AND role = 'borrower') "
        "AND EXISTS (SELECT 1 FROM loan_party WHERE person_id = b.id AND role = 'borrower') "
        "AND NOT EXISTS (SELECT 1 FROM loan_party x JOIN loan_party y "
        "  ON x.loan_id = y.loan_id AND x.role = y.role "
        "  WHERE x.person_id = a.id AND y.person_id = b.id) LIMIT 1"
    )
    total = await _parties(str(keep_name)) + await _parties(str(drop_name))

    r = await seeded_client.post(
        f"/api/persons/{keep_id}/merge", json={"drop_ids": [drop_id], "full_name": "ادغام تست"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["person"]["full_name"] == "ادغام تست"
    assert (await seeded_client.get(f"/api/persons/{drop_id}")).status_code == 404
    assert await _parties("ادغام تست") == total
    history = (await seeded_client.get(f"/api/audit?entity=person&entity_id={keep_id}")).json()
    assert history[0]["action"] == "merge"
    assert history[0]["before"]["merged"] == drop_name

    # Re-import: both old names map to the kept person, nothing re-created.
    engine = create_async_engine(str(settings.database_url))
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        await write_parse_result(
            session,
            source_path=sample_xlsm_path,
            sha256="9" * 64,
            duration_ms=0,
            result=parse_workbook(sample_xlsm_path),
        )
    await engine.dispose()
    assert await _parties("ادغام تست") == total
    gone = await _sql(
        f"SELECT count(*) FROM person WHERE full_name IN ('{keep_name}', '{drop_name}')"
    )
    assert gone[0][0] == 0


@pytest.mark.asyncio
async def test_merge_refuses_self_unknown_and_same_loan_role(seeded_client: AsyncClient) -> None:
    (pid,), *_ = await _sql("SELECT person_id FROM loan_party LIMIT 1")
    r = await seeded_client.post(f"/api/persons/{pid}/merge", json={"drop_ids": [pid]})
    assert r.status_code == 422
    r = await seeded_client.post(f"/api/persons/{pid}/merge", json={"drop_ids": [999_999_999]})
    assert r.status_code == 422
    r = await seeded_client.post("/api/persons/999999999/merge", json={"drop_ids": [pid]})
    assert r.status_code == 404

    (a, b), *_ = await _sql(
        "SELECT x.person_id, y.person_id FROM loan_party x JOIN loan_party y "
        "ON x.loan_id = y.loan_id AND x.role = y.role AND x.person_id < y.person_id LIMIT 1"
    )
    r = await seeded_client.post(f"/api/persons/{a}/merge", json={"drop_ids": [b]})
    assert r.status_code == 422
