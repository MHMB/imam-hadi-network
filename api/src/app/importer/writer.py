"""DB writer for a parsed workbook.

Contract:

- One ``Import`` row per file invocation, keyed by ``source_sha256``.
- Sha-deduplication: re-uploading the exact same xlsm (same content
  hash) short-circuits to the existing ``Import`` row — never re-imports.
- Per-year scoped replace: ``DELETE`` then ``INSERT`` of loans /
  contributions / installments for **only** the years present in the
  file.  Persons and topics are upserted (never deleted) — they are
  global to the dashboard.
- The workbook is the source of truth: person names referenced by loans
  but missing from the افراد master are **auto-created** (identity =
  normalised name key, see :mod:`app.importer.names`), and topic names
  missing from موضوعات are auto-created too.  Nothing is dropped for
  being unlisted; validation still surfaces every such case as an issue.
- The same person lending to one loan on several rows (separate dated
  contributions) is **merged into one ``LoanParty``** — amounts summed,
  installments concatenated — satisfying the one-row-per-(loan, role,
  person) schema invariant without losing any repayment detail.
- Single transaction per import.  Either everything for that import
  lands, or nothing.  ``DataIssue`` rows are written in the same tx.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.importer.models import ParsedInstallment, ParsedLoan, ParsedPerson, ParseResult
from app.importer.names import canonical_name, placeholder_phone, resolve_key
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
from app.models.enums import ImportStatus, LoanPartyRole


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
) -> tuple[Import, bool]:
    """Persist a parsed workbook in one transaction.

    Caller already ran ``validate(result)``; this function does the
    sha-dedup short-circuit and the per-year-scoped replace.  Returns
    the persisted (or pre-existing) ``Import`` row plus a ``deduped``
    flag — ``True`` when the sha short-circuit fired and nothing was
    written.
    """
    # --- sha-dedup ---
    existing = await _existing_import_for(session, sha256)
    if existing is not None and existing.status is ImportStatus.success:
        return existing, True

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
    await _apply_parse_result(session, import_row, result)
    await session.commit()
    return import_row, False


async def apply_to_existing_import(
    session: AsyncSession,
    import_row: Import,
    result: ParseResult,
    *,
    duration_ms: int,
) -> Import:
    """Fill an existing pending Import row with parsed data.

    Used by the HTTP upload background task — the row was created up-front
    by the API endpoint (with status=pending) so the client gets an id back
    immediately for polling.  We mutate years_imported / report / duration
    / status here and write all loans+parties+installments+issues in one
    transaction.
    """
    years = sorted({loan.persian_year for loan in result.loans})
    import_row.years_imported = years
    import_row.duration_ms = duration_ms
    import_row.report = _summary(result)
    import_row.status = ImportStatus.success
    await session.flush()
    await _apply_parse_result(session, import_row, result)
    await session.commit()
    return import_row


async def _apply_parse_result(
    session: AsyncSession,
    import_row: Import,
    result: ParseResult,
) -> None:
    """Shared body: topics + persons upsert, year-scoped replace, issues.

    Caller has already created/loaded ``import_row`` (with ``id`` populated)
    and is responsible for the surrounding transaction (``session.commit``).
    """
    # Topics: the موضوعات catalog plus any name a loan actually references —
    # year sheets are authoritative, so an uncatalogued topic is created,
    # not a reason to drop the loan.
    topic_names = list(result.topics)
    for loan in result.loans:
        if loan.topic_name and loan.topic_name not in topic_names:
            topic_names.append(loan.topic_name)
    topic_id_by_name = await _upsert_topics(session, topic_names)

    person_id_by_key = await _upsert_persons(session, result.persons)
    await _ensure_referenced_persons(session, result.loans, person_id_by_key)

    years = sorted({loan.persian_year for loan in result.loans})
    if years:
        await _delete_year_scoped(session, years)
    await _insert_loans(
        session,
        result.loans,
        import_id=import_row.id,
        topic_ids=topic_id_by_name,
        person_ids=person_id_by_key,
    )

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
    """Insert / refresh the افراد master persons; return identity-key → id.

    Person rows are matched by canonical phone (real numbers and the
    hash-derived placeholders are both stable), but the *returned* mapping
    is keyed by :func:`app.importer.names.resolve_key` so loan references
    in any spelling variant resolve to the right row.
    """
    if not parsed:
        return {}

    phones = [p.phone_canonical for p in parsed if p.phone_canonical]
    existing = await session.execute(select(Person).where(Person.phone.in_(phones)))
    by_phone: dict[str, Person] = {row.phone: row for row in existing.scalars()}

    by_key: dict[str, int] = {}
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
            # Register the insert: the master sheet itself can list one person
            # twice under spelling variants (same identity key → same
            # placeholder phone); the second occurrence must refresh, not
            # double-insert.
            by_phone[parsed_p.phone_canonical] = row
        else:
            # Refresh descriptive fields; never demote verification.
            row.full_name = parsed_p.full_name
            row.phone_raw = parsed_p.phone_raw or row.phone_raw
            row.messenger = parsed_p.messenger or row.messenger
            if parsed_p.is_verified:
                row.is_verified = True
        by_key[resolve_key(parsed_p.full_name)] = row.id

    # --- guarantor links: drop and re-insert per person ---
    # Use synchronize_session=False so SQLAlchemy doesn't try to reconcile the
    # delete with already-tracked Person.guarantor_links relationship state
    # (it would try to NULL the PK person_guarantor.person_id otherwise).
    for parsed_p in parsed:
        pid = by_key[resolve_key(parsed_p.full_name)]
        await session.execute(
            delete(PersonGuarantor)
            .where(PersonGuarantor.person_id == pid)
            .execution_options(synchronize_session=False)
        )
    await session.flush()  # commit the deletes before re-inserting
    for parsed_p in parsed:
        pid = by_key[resolve_key(parsed_p.full_name)]
        for link in parsed_p.guarantor_links:
            guarantor_id = by_key.get(resolve_key(link.guarantor_name))
            if guarantor_id is None or guarantor_id == pid:
                # Unresolved guarantor (or self-reference) — silently skip; the
                # validation layer already emits an unresolved_person warning
                # when this matters.
                continue
            session.add(PersonGuarantor(person_id=pid, role=link.role, guarantor_id=guarantor_id))

    return by_key


async def _ensure_referenced_persons(
    session: AsyncSession,
    parsed_loans: list[ParsedLoan],
    person_ids: dict[str, int],
) -> None:
    """Auto-create persons the year sheets reference but افراد doesn't list.

    The workbook is the source of truth — a borrower / lender / guarantor
    name that resolves to no master row still names a real party, so it
    becomes a Person with a placeholder phone.  Spelling variants collapse
    onto one row via the identity key; the first-seen (alias-canonicalised)
    spelling is kept as the display name.  Validation has already flagged
    every such name as an ``unresolved_person`` warning for admin follow-up.
    """
    missing: dict[str, str] = {}  # key → display name
    for loan in parsed_loans:
        names = [loan.guarantor_name] + [p.person_name for p in loan.parties]
        for name in names:
            if not name:
                continue
            key = resolve_key(name)
            if not key or key in person_ids or key in missing:
                continue
            missing[key] = canonical_name(name)

    # Re-imports find previously auto-created rows by their stable
    # placeholder phone (a hash of the identity key).
    if not missing:
        return
    placeholder_by_key = {key: placeholder_phone(name) for key, name in missing.items()}
    existing = await session.execute(
        select(Person).where(Person.phone.in_(list(placeholder_by_key.values())))
    )
    phone_to_person = {row.phone: row for row in existing.scalars()}

    for key, name in missing.items():
        row = phone_to_person.get(placeholder_by_key[key])
        if row is None:
            row = Person(
                phone=placeholder_by_key[key],
                full_name=name,
                phone_raw=None,
                messenger=None,
                is_verified=False,
            )
            session.add(row)
            await session.flush()
        person_ids[key] = row.id


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
            # Unreachable after the referenced-topic upsert; kept as a guard
            # so a future regression skips one loan instead of crashing the
            # whole transaction.
            continue
        guarantor_id = (
            person_ids.get(resolve_key(parsed_loan.guarantor_name))
            if parsed_loan.guarantor_name
            else None
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

        for person_id, role, amount, display_order, installments in _merged_parties(
            parsed_loan, person_ids
        ):
            party_row = LoanParty(
                loan_id=loan_row.id,
                person_id=person_id,
                role=role,
                amount=amount,
                display_order=display_order,
            )
            session.add(party_row)
            await session.flush()

            for inst in installments:
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


@dataclass(slots=True)
class _PartyAccumulator:
    """Mutable per-(person, role) rollup used by ``_merged_parties``."""

    amount: Decimal
    display_order: int
    installments: list[ParsedInstallment]


def _merged_parties(
    parsed_loan: ParsedLoan,
    person_ids: dict[str, int],
) -> list[tuple[int, LoanPartyRole, Decimal, int, tuple[ParsedInstallment, ...]]]:
    """Collapse a loan's parties onto unique (person, role) slots.

    The ledgers record one row per *contribution*, and the same lender
    often contributed to one loan several times (the pooled loans reach
    74 rows for a single lender).  The schema's ``unique_role_person``
    means one party per (loan, role, person): amounts are summed and the
    dated installments concatenated, so no repayment detail is lost.

    Parties whose name doesn't resolve (blank lender cells — the engine
    already issued a warning) or whose merged amount isn't positive (DB
    ``CHECK amount > 0``) are skipped.
    """
    merged: dict[tuple[int, LoanPartyRole], _PartyAccumulator] = {}
    for party in parsed_loan.parties:
        person_id = person_ids.get(resolve_key(party.person_name)) if party.person_name else None
        if person_id is None:
            continue
        slot = (person_id, party.role)
        acc = merged.get(slot)
        if acc is None:
            merged[slot] = _PartyAccumulator(
                amount=party.amount,
                display_order=party.display_order,
                installments=list(party.installments),
            )
            continue
        acc.amount += party.amount
        acc.display_order = min(acc.display_order, party.display_order)
        acc.installments.extend(party.installments)

    return [
        (person_id, role, acc.amount, acc.display_order, tuple(acc.installments))
        for (person_id, role), acc in merged.items()
        if acc.amount > 0
    ]
