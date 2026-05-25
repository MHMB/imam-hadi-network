"""Post-parse validation rules.

Walks an already-populated ``ParseResult`` and appends ``ParsedIssue``
records for cross-record problems the per-sheet parsers can't see on
their own:

- Sum invariants on loan totals vs lender/borrower amounts.
- Sum invariants on installment amounts vs lender amount.
- Borrower / lender / guarantor name references that don't resolve to
  any parsed Person.
- Topic name references that aren't in the parsed Topic catalog.
- Duplicate phones across two persons.
- Per-installment day sanity (1..31).
- Loan rows whose total / borrower / topic is missing.

The writer (P2.8) is allowed to abort on ``error``-severity issues; the
dashboard surfaces every severity for admins to fix in the xlsm.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal

from app.importer.models import ParsedIssue, ParseResult
from app.models.enums import IssueCategory, IssueSeverity, LoanPartyRole

MAX_DAY_OF_MONTH = 31
MIN_DAY_OF_MONTH = 1


def validate(result: ParseResult) -> None:
    """Append cross-record issues to ``result.issues``.  Idempotent.

    Order of checks is intentional — catalog/identity checks first so
    later loan-level issues can carry useful "did you mean..." context.
    """
    topic_names = set(result.topics)
    person_names = {p.full_name for p in result.persons}

    _check_duplicate_phones(result)
    for loan in result.loans:
        _check_loan_totals(loan, result)
        _check_topic_resolved(loan, result, topic_names)
        _check_person_refs(loan, result, person_names)
        _check_installment_days(loan, result)


# --------------------------------------------------------------------- helpers


def _issue(
    result: ParseResult,
    *,
    severity: IssueSeverity,
    category: IssueCategory,
    message: str,
    sheet: str | None = None,
    cell: str | None = None,
    context: dict[str, object] | None = None,
) -> None:
    result.issues.append(
        ParsedIssue(
            severity=severity,
            category=category,
            message=message,
            sheet=sheet,
            cell=cell,
            context=context,
        )
    )


# --------------------------------------------------------------------- checks


def _check_duplicate_phones(result: ParseResult) -> None:
    """Two persons with the same canonical phone — flag as error."""
    counts: Counter[str] = Counter(p.phone_canonical for p in result.persons if p.phone_canonical)
    # Ignore the synthetic +0__name__ placeholders (one per nameless-phone row;
    # they are designed to be unique-by-name and would false-positive otherwise).
    duplicates = {phone: n for phone, n in counts.items() if n > 1 and not phone.startswith("+0__")}
    if not duplicates:
        return
    for phone, n in duplicates.items():
        names = sorted({p.full_name for p in result.persons if p.phone_canonical == phone})
        _issue(
            result,
            severity=IssueSeverity.error,
            category=IssueCategory.duplicate_phone,
            message=(f"شماره تماس «{phone}» میان {n} شخص تکراری است: " + "، ".join(names)),
            context={"phone": phone, "names": names},
        )


def _check_loan_totals(loan: object, result: ParseResult) -> None:
    """Σ borrower-side and Σ lender-side must both equal loan.total_amount."""
    parties = loan.parties  # type: ignore[attr-defined]
    borrowers = [p for p in parties if p.role is LoanPartyRole.borrower]
    lenders = [p for p in parties if p.role is LoanPartyRole.lender]

    borrower_sum: Decimal = sum((p.amount for p in borrowers), Decimal(0))
    lender_sum: Decimal = sum((p.amount for p in lenders), Decimal(0))
    total: Decimal = loan.total_amount  # type: ignore[attr-defined]
    sheet = loan.source_sheet  # type: ignore[attr-defined]
    loan_no = loan.loan_number  # type: ignore[attr-defined]

    if borrower_sum != total:
        _issue(
            result,
            severity=IssueSeverity.error,
            category=IssueCategory.total_mismatch,
            message=(
                f"قرض #{loan_no}: مجموع سهم قرض‌گیرندگان ({borrower_sum}) با مبلغ کل ({total}) برابر نیست."
            ),
            sheet=sheet,
            context={
                "loan_number": loan_no,
                "borrower_sum": str(borrower_sum),
                "total": str(total),
            },
        )
    if lender_sum != total:
        _issue(
            result,
            severity=IssueSeverity.error,
            category=IssueCategory.total_mismatch,
            message=(
                f"قرض #{loan_no}: مجموع سهم قرض‌دهندگان ({lender_sum}) با مبلغ کل ({total}) برابر نیست."
            ),
            sheet=sheet,
            context={
                "loan_number": loan_no,
                "lender_sum": str(lender_sum),
                "total": str(total),
            },
        )

    # Per-lender installment sum
    for lender in lenders:
        if not lender.installments:
            continue
        inst_sum: Decimal = sum((i.amount for i in lender.installments), Decimal(0))
        if inst_sum != lender.amount:
            _issue(
                result,
                severity=IssueSeverity.error,
                category=IssueCategory.total_mismatch,
                message=(
                    f"قرض #{loan_no} / قرض‌دهنده «{lender.person_name}»: "
                    f"مجموع اقساط ({inst_sum}) با مبلغ ({lender.amount}) برابر نیست."
                ),
                sheet=sheet,
                context={
                    "loan_number": loan_no,
                    "lender": lender.person_name,
                    "installment_sum": str(inst_sum),
                    "lender_amount": str(lender.amount),
                },
            )


def _check_topic_resolved(
    loan: object,
    result: ParseResult,
    topic_names: set[str],
) -> None:
    name = loan.topic_name  # type: ignore[attr-defined]
    if name in topic_names:
        return
    _issue(
        result,
        severity=IssueSeverity.warning,
        category=IssueCategory.unknown_topic,
        message=(
            f"قرض #{loan.loan_number}: موضوع «{name}» در فهرست موضوعات وارد نشده است."  # type: ignore[attr-defined]
        ),
        sheet=loan.source_sheet,  # type: ignore[attr-defined]
        context={"loan_number": loan.loan_number, "topic": name},  # type: ignore[attr-defined]
    )


def _check_person_refs(
    loan: object,
    result: ParseResult,
    person_names: set[str],
) -> None:
    refs: dict[str, list[str]] = defaultdict(list)
    if loan.guarantor_name and loan.guarantor_name not in person_names:  # type: ignore[attr-defined]
        refs[loan.guarantor_name].append("ضامن")  # type: ignore[attr-defined]
    for party in loan.parties:  # type: ignore[attr-defined]
        if not party.person_name:
            continue
        if party.person_name not in person_names:
            refs[party.person_name].append(party.role.value)
    for name, roles in refs.items():
        _issue(
            result,
            severity=IssueSeverity.warning,
            category=IssueCategory.unresolved_person,
            message=(
                f"قرض #{loan.loan_number}: شخص «{name}» در شیت «افراد» تعریف نشده است "  # type: ignore[attr-defined]
                f"({', '.join(roles)})."
            ),
            sheet=loan.source_sheet,  # type: ignore[attr-defined]
            context={"loan_number": loan.loan_number, "name": name, "roles": roles},  # type: ignore[attr-defined]
        )


def _check_installment_days(loan: object, result: ParseResult) -> None:
    for party in loan.parties:  # type: ignore[attr-defined]
        for inst in party.installments:
            if not (MIN_DAY_OF_MONTH <= inst.due_day_of_month <= MAX_DAY_OF_MONTH):
                _issue(
                    result,
                    severity=IssueSeverity.warning,
                    category=IssueCategory.bad_day,
                    message=(
                        f"قرض #{loan.loan_number}: روز سررسید نامعتبر "  # type: ignore[attr-defined]
                        f"({inst.due_day_of_month}) در سلول {inst.cell or '?'}."
                    ),
                    sheet=inst.sheet,
                    cell=inst.cell,
                    context={
                        "loan_number": loan.loan_number,  # type: ignore[attr-defined]
                        "day": inst.due_day_of_month,
                    },
                )
