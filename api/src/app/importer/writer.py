"""DB writer for a parsed workbook.

Contract:

- One ``Import`` row per file invocation, keyed by ``source_sha256``.
- Sha-deduplication: re-uploading the exact same xlsm (same content
  hash) short-circuits to the existing ``Import`` row — never re-imports.
- Per-year scoped replace: ``DELETE`` then ``INSERT`` of loans /
  contributions / installments for **only** the years present in the
  file.  Persons and topics are upserted (never deleted) — they are
  global to the dashboard.
- Single transaction per import.  Either everything for that import
  lands, or nothing.  ``DataIssue`` rows are written in the same tx.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.importer.models import ParsedLoan, ParsedPerson, ParseResult
from app.models import (
    DataIssue,
    Import,
    Installment,
    Loan,
    LoanParty,
    LoanTopic,
    Person,
    PersonGuarantor,
)
from app.models.enums import ImportStatus


def sha256_of_file(path: Path) -> str:
    """Streaming sha256 — large xlsm files don't blow up RAM."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


async def _existing_import_for(session: AsyncSession, sha: str) -> Import | None:
    """Return the persisted Import row with this sha, if any."""
    row = await session.execute(select(Import).where(Import.source_sha256 == sha))
    return row.scalar_one_or_none()


async def write_parse_result(
    session: AsyncSession,
    *,
    source_path: Path,
    sha256: str,
    duration_ms: int,
    result: ParseResult,
) -> Import:
    """Persist a parsed workbook in one transaction.

    Caller already ran ``validate(result)``; this function does the
    sha-dedup short-circuit and the per-year-scoped replace.  Returns
    the persisted (or pre-existing) ``Import`` row.
    """
    # --- sha-dedup ---
    existing = await _existing_import_for(session, sha256)
    if existing is not None and existing.status is ImportStatus.success:
        return existing

    years = sorted({loan.persian_year for loan in result.loans})
    import_row = Import(
        source_sha256=sha256,
        source_filename=source_path.name,
        years_imported=years,
        status=ImportStatus.success,
        duration_ms=duration_ms,
        report=_summary(result),
    )
    session.add(import_row)
    await session.flush()  # need import_row.id for FK on loans + issues

    # --- upsert topics ---
    topic_id_by_name = await _upsert_topics(session, result.topics)

    # --- upsert persons (incl. resolving guarantor links) ---
    person_id_by_name = await _upsert_persons(session, result.persons)

    # --- per-year replace of loans / parties / installments ---
    if years:
        await _delete_year_scoped(session, years)
    await _insert_loans(
        session,
        result.loans,
        import_id=import_row.id,
        topic_ids=topic_id_by_name,
        person_ids=person_id_by_name,
    )

    # --- DataIssue rows linked to this Import ---
    for issue in result.issues:
        session.add(
            DataIssue(
                import_id=import_row.id,
                severity=issue.severity,
                category=issue.category,
                message=issue.message,
                sheet=issue.sheet,
                cell=issue.cell,
                context=issue.context,
            )
        )

    await session.commit()
    return import_row


# --------------------------------------------------------------------- internals


def _summary(result: ParseResult) -> dict[str, object]:
    """Compact counts blob persisted on the Import row."""
    by_severity: dict[str, int] = {}
    by_category: dict[str, int] = {}
    for issue in result.issues:
        by_severity[issue.severity.value] = by_severity.get(issue.severity.value, 0) + 1
        by_category[issue.category.value] = by_category.get(issue.category.value, 0) + 1
    return {
        "topics": len(result.topics),
        "persons": len(result.persons),
        "loans": len(result.loans),
        "issues": len(result.issues),
        "issues_by_severity": by_severity,
        "issues_by_category": by_category,
    }


async def _upsert_topics(session: AsyncSession, names: list[str]) -> dict[str, int]:
    """Insert any topic names not already present; return name → id."""
    if not names:
        return {}
    existing = await session.execute(select(LoanTopic).where(LoanTopic.name.in_(names)))
    out: dict[str, int] = {t.name: t.id for t in existing.scalars()}
    for name in names:
        if name in out:
            continue
        row = LoanTopic(name=name)
        session.add(row)
        await session.flush()
        out[name] = row.id
    return out


async def _upsert_persons(
    session: AsyncSession,
    parsed: list[ParsedPerson],
) -> dict[str, int]:
    """Insert / refresh persons by phone (canonical); return name → id."""
    if not parsed:
        return {}

    phones = [p.phone_canonical for p in parsed if p.phone_canonical]
    existing = await session.execute(select(Person).where(Person.phone.in_(phones)))
    by_phone: dict[str, Person] = {row.phone: row for row in existing.scalars()}

    by_name: dict[str, int] = {}
    for parsed_p in parsed:
        row = by_phone.get(parsed_p.phone_canonical)
        if row is None:
            row = Person(
                phone=parsed_p.phone_canonical,
                full_name=parsed_p.full_name,
                phone_raw=parsed_p.phone_raw,
                messenger=parsed_p.messenger,
                is_verified=parsed_p.is_verified,
            )
            session.add(row)
            await session.flush()
        else:
            # Refresh descriptive fields; never demote verification.
            row.full_name = parsed_p.full_name
            row.phone_raw = parsed_p.phone_raw or row.phone_raw
            row.messenger = parsed_p.messenger or row.messenger
            if parsed_p.is_verified:
                row.is_verified = True
        by_name[parsed_p.full_name] = row.id

    # --- guarantor links: drop and re-insert per person ---
    # Use synchronize_session=False so SQLAlchemy doesn't try to reconcile the
    # delete with already-tracked Person.guarantor_links relationship state
    # (it would try to NULL the PK person_guarantor.person_id otherwise).
    for parsed_p in parsed:
        pid = by_name[parsed_p.full_name]
        await session.execute(
            delete(PersonGuarantor)
            .where(PersonGuarantor.person_id == pid)
            .execution_options(synchronize_session=False)
        )
    await session.flush()  # commit the deletes before re-inserting
    for parsed_p in parsed:
        pid = by_name[parsed_p.full_name]
        for link in parsed_p.guarantor_links:
            guarantor_id = by_name.get(link.guarantor_name)
            if guarantor_id is None or guarantor_id == pid:
                # Unresolved guarantor (or self-reference) — silently skip; the
                # validation layer already emits an unresolved_person warning
                # when this matters.
                continue
            session.add(PersonGuarantor(person_id=pid, role=link.role, guarantor_id=guarantor_id))

    return by_name


async def _delete_year_scoped(session: AsyncSession, years: list[int]) -> None:
    """Delete loans (and cascaded parties + installments) for the given years."""
    await session.execute(delete(Loan).where(Loan.persian_year.in_(years)))


async def _insert_loans(
    session: AsyncSession,
    parsed_loans: list[ParsedLoan],
    *,
    import_id: int,
    topic_ids: dict[str, int],
    person_ids: dict[str, int],
) -> None:
    for parsed_loan in parsed_loans:
        topic_id = topic_ids.get(parsed_loan.topic_name)
        if topic_id is None:
            # Topic was missing — surfaced by validate(); skip so the import
            # still lands the rest of the data.
            continue
        guarantor_id = (
            person_ids.get(parsed_loan.guarantor_name) if parsed_loan.guarantor_name else None
        )
        loan_row = Loan(
            persian_year=parsed_loan.persian_year,
            loan_number=parsed_loan.loan_number,
            total_amount=parsed_loan.total_amount,
            topic_id=topic_id,
            import_id=import_id,
            channel_number=parsed_loan.channel_number,
            guarantor_id=guarantor_id,
            liaison_label=parsed_loan.liaison_label,
            description=parsed_loan.description,
        )
        session.add(loan_row)
        await session.flush()

        for parsed_party in parsed_loan.parties:
            party_pid = person_ids.get(parsed_party.person_name)
            if party_pid is None:
                # Lender / borrower name doesn't resolve; skip the party but
                # don't fail the import — the issue is already in the report.
                continue
            party_row = LoanParty(
                loan_id=loan_row.id,
                person_id=party_pid,
                role=parsed_party.role,
                amount=parsed_party.amount,
                display_order=parsed_party.display_order,
            )
            session.add(party_row)
            await session.flush()

            for inst in parsed_party.installments:
                session.add(
                    Installment(
                        loan_party_id=party_row.id,
                        due_persian_year=inst.due_persian_year,
                        due_persian_month=inst.due_persian_month,
                        due_day_of_month=inst.due_day_of_month,
                        amount=inst.amount,
                        status=inst.status,
                    )
                )
