"""Integration tests for the end-to-end importer runner."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.importer.runner import parse_workbook, run_import
from app.models import Import, Installment, Loan, LoanParty, LoanTopic, Person

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
async def session() -> AsyncSession:
    engine = create_async_engine(str(settings.database_url))
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async def wipe() -> None:
        async with engine.begin() as conn:
            for table in _WIPE_TABLES:
                await conn.exec_driver_sql(f"DELETE FROM {table}")

    await wipe()
    async with sessionmaker() as s:
        yield s
    await wipe()
    await engine.dispose()


# --- pure parser (no DB) ---


def test_parse_workbook_produces_expected_shapes(sample_xlsm_path: Path) -> None:
    result = parse_workbook(sample_xlsm_path)
    assert len(result.topics) == 17
    assert len(result.persons) == 21
    assert sorted(result.years_present) == [1404, 1405]
    assert len(result.loans) == 9  # 5 from 1404 + 4 from 1405


# --- full pipeline ---


@pytest.mark.asyncio
async def test_run_import_persists_everything(
    session: AsyncSession, sample_xlsm_path: Path
) -> None:
    outcome = await run_import(session, sample_xlsm_path)
    assert outcome.import_id > 0
    assert outcome.deduped is False
    assert outcome.loans == 9
    assert outcome.persons == 21
    assert outcome.years_imported == [1404, 1405]

    # The known sample-data flaw (loan 2501 lender vs installment mismatch)
    # surfaces as an error-severity DataIssue → outcome.error_count >= 1.
    assert outcome.error_count >= 1
    assert outcome.issues_by_severity.get("error", 0) >= 1

    # DB cross-checks
    n_imports = (await session.execute(select(func.count()).select_from(Import))).scalar_one()
    assert n_imports == 1
    n_loans = (await session.execute(select(func.count()).select_from(Loan))).scalar_one()
    assert n_loans == 9
    n_parties = (await session.execute(select(func.count()).select_from(LoanParty))).scalar_one()
    # 9 borrowers + count of lender parties (varies per loan)
    assert n_parties >= 9 + 9  # at least one lender per loan + borrowers
    n_installments = (
        await session.execute(select(func.count()).select_from(Installment))
    ).scalar_one()
    assert n_installments > 0
    n_topics = (await session.execute(select(func.count()).select_from(LoanTopic))).scalar_one()
    assert n_topics >= 17


@pytest.mark.asyncio
async def test_run_import_is_idempotent(session: AsyncSession, sample_xlsm_path: Path) -> None:
    first = await run_import(session, sample_xlsm_path)
    second = await run_import(session, sample_xlsm_path)
    # Same Import row returned; only one Import in DB.
    assert first.import_id == second.import_id
    assert second.deduped is True
    n_imports = (await session.execute(select(func.count()).select_from(Import))).scalar_one()
    assert n_imports == 1


@pytest.mark.asyncio
async def test_dry_run_writes_nothing(session: AsyncSession, sample_xlsm_path: Path) -> None:
    outcome = await run_import(session, sample_xlsm_path, dry_run=True)
    assert outcome.import_id == -1
    assert outcome.loans == 9
    n_imports = (await session.execute(select(func.count()).select_from(Import))).scalar_one()
    assert n_imports == 0
    n_loans = (await session.execute(select(func.count()).select_from(Loan))).scalar_one()
    assert n_loans == 0
    n_persons = (await session.execute(select(func.count()).select_from(Person))).scalar_one()
    assert n_persons == 0
