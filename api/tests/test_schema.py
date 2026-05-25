"""Schema round-trip and structural checks.

Requires a live Postgres reachable via ``DATABASE_URL``.  CI provides
the ``postgres`` service; locally, ``make db.up`` is enough.

What this test asserts:

1. ``alembic upgrade head`` → ``downgrade base`` → ``upgrade head`` is
   clean (no leftover tables, no migration errors).
2. After the second upgrade, every model table from ``Base.metadata``
   exists in the DB.
3. The non-trivial structural pieces are present:
   - ``pg_trgm`` extension
   - GIN trigram index ``ix_person_full_name_trgm``
   - Partial index ``ix_installment_unpaid_due`` predicated on
     ``status='unpaid'``
   - All FKs have the right ON DELETE rule
   - The 17 seed topics are loaded
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.models import Base

pytestmark = pytest.mark.integration

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def _alembic_cfg() -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(ALEMBIC_INI.parent / "src/app/alembic"))
    cfg.set_main_option("sqlalchemy.url", str(settings.database_url))
    return cfg


async def _list_tables() -> set[str]:
    engine = create_async_engine(str(settings.database_url))
    try:
        async with engine.connect() as conn:

            def fetch(sync_conn: object) -> set[str]:
                insp = inspect(sync_conn)
                return set(insp.get_table_names())

            return await conn.run_sync(fetch)
    finally:
        await engine.dispose()


async def _alembic(direction: str, target: str) -> None:
    """Run an Alembic command in a worker thread.

    ``env.py`` calls ``asyncio.run(...)`` internally, which forbids being
    invoked from inside an already-running event loop (i.e. the pytest-
    asyncio test loop).  ``to_thread`` gives Alembic its own thread, with
    its own loop, sidestepping the nesting prohibition.
    """
    cfg = _alembic_cfg()
    fn = command.upgrade if direction == "up" else command.downgrade
    await asyncio.to_thread(fn, cfg, target)


@pytest.mark.asyncio
async def test_migrations_roundtrip() -> None:
    # Reset to a clean state, then exercise the full roundtrip.
    await _alembic("down", "base")
    assert (await _list_tables()) == {"alembic_version"}  # only alembic's bookkeeping

    await _alembic("up", "head")
    tables_after_up = await _list_tables()
    expected = set(Base.metadata.tables.keys()) | {"alembic_version"}
    assert tables_after_up == expected, (
        f"missing: {expected - tables_after_up}; extra: {tables_after_up - expected}"
    )

    await _alembic("down", "base")
    assert (await _list_tables()) == {"alembic_version"}

    await _alembic("up", "head")
    assert (await _list_tables()) == expected


@pytest.mark.asyncio
async def test_pg_trgm_extension_present() -> None:
    engine = create_async_engine(str(settings.database_url))
    try:
        async with engine.connect() as conn:
            row = (
                await conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'"))
            ).first()
            assert row is not None, "pg_trgm extension missing — 0001_init did not create it"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_trigram_gin_index_on_person_full_name() -> None:
    engine = create_async_engine(str(settings.database_url))
    try:
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT indexdef FROM pg_indexes "
                        "WHERE indexname = 'ix_person_full_name_trgm'"
                    )
                )
            ).first()
            assert row is not None, "ix_person_full_name_trgm missing"
            indexdef = row[0].lower()
            assert "gin" in indexdef
            assert "gin_trgm_ops" in indexdef
            assert "full_name" in indexdef
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_partial_unpaid_due_index_predicate() -> None:
    engine = create_async_engine(str(settings.database_url))
    try:
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT indexdef FROM pg_indexes "
                        "WHERE indexname = 'ix_installment_unpaid_due'"
                    )
                )
            ).first()
            assert row is not None, "ix_installment_unpaid_due missing"
            indexdef = row[0].lower()
            assert "where" in indexdef
            assert "unpaid" in indexdef
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_fk_ondelete_rules() -> None:
    """Spot-check the ON DELETE rules that protect data integrity."""
    engine = create_async_engine(str(settings.database_url))
    expected = {
        # (table, column) → ON DELETE action (Postgres letter)
        # c=CASCADE, r=RESTRICT, n=NO ACTION, a=SET NULL/DEFAULT, etc.
        ("loan_party", "loan_id"): "c",
        ("loan_party", "person_id"): "r",
        ("installment", "loan_party_id"): "c",
        ("loan", "import_id"): "r",
        ("loan", "topic_id"): "r",
        ("loan", "guarantor_id"): "r",
        ("data_issue", "import_id"): "c",
        ("person_guarantor", "person_id"): "c",
        ("person_guarantor", "guarantor_id"): "r",
    }
    try:
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        """
                        SELECT conrelid::regclass::text AS table_name,
                               a.attname AS column_name,
                               confdeltype AS on_delete
                        FROM pg_constraint c
                        JOIN pg_attribute a
                          ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
                        WHERE c.contype = 'f'
                          AND c.conrelid::regclass::text IN (
                              'loan_party', 'installment', 'loan',
                              'data_issue', 'person_guarantor'
                          )
                        """
                    )
                )
            ).all()
            got = {(r[0], r[1]): r[2] for r in rows}
            for key, action in expected.items():
                assert got.get(key) == action, f"FK {key} expected {action}, got {got.get(key)}"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_seed_topics_loaded() -> None:
    engine = create_async_engine(str(settings.database_url))
    try:
        async with engine.connect() as conn:
            n = (await conn.execute(text("SELECT count(*) FROM loan_topic"))).scalar_one()
            assert n >= 17, f"expected ≥17 seeded topics, found {n}"

            row = (
                await conn.execute(text("SELECT legacy_num FROM loan_topic WHERE name = 'نامعلوم'"))
            ).first()
            assert row is not None, "نامعلوم topic missing"
            assert row[0] == 0, "نامعلوم must have legacy_num=0"
    finally:
        await engine.dispose()
