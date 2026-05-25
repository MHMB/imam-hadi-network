"""Validation-layer tests.

Tests fall into two groups:

1. Pure unit tests against synthetic ParseResult objects — fast, targeted
   coverage of each rule.
2. One integration test against the sample fixture: parse everything,
   run validate(), assert the expected mix of issues (including the
   known loan 2501 total_mismatch from year-1405).
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import openpyxl
import pytest

from app.importer.models import (
    ParsedInstallment,
    ParsedLoan,
    ParsedParty,
    ParsedPerson,
    ParseResult,
)
from app.importer.parsers.people import parse_people
from app.importer.parsers.topics import parse_topics
from app.importer.parsers.year_1404 import parse_year_1404
from app.importer.parsers.year_1405 import parse_year_1405
from app.importer.validation import validate
from app.models.enums import InstallmentStatus, IssueCategory, IssueSeverity, LoanPartyRole

# --------------------------------------------------------------------- builders


def _person(name: str, phone: str = "") -> ParsedPerson:
    return ParsedPerson(full_name=name, phone_canonical=phone, phone_raw=None)


def _loan(
    *,
    number: str,
    total: Decimal,
    topic: str,
    borrower: ParsedParty,
    lenders: list[ParsedParty],
    guarantor: str | None = None,
) -> ParsedLoan:
    return ParsedLoan(
        persian_year=1404,
        loan_number=number,
        total_amount=total,
        topic_name=topic,
        parties=(borrower, *lenders),
        guarantor_name=guarantor,
        source_sheet="سال 1404",
    )


def _lender(
    name: str, amount: Decimal, installments: tuple[ParsedInstallment, ...] = ()
) -> ParsedParty:
    return ParsedParty(
        role=LoanPartyRole.lender,
        person_name=name,
        amount=amount,
        display_order=1,
        installments=installments,
    )


def _borrower(name: str, amount: Decimal) -> ParsedParty:
    return ParsedParty(
        role=LoanPartyRole.borrower,
        person_name=name,
        amount=amount,
        display_order=0,
    )


def _inst(year: int, month: int, day: int, amount: Decimal) -> ParsedInstallment:
    return ParsedInstallment(
        due_persian_year=year,
        due_persian_month=month,
        due_day_of_month=day,
        amount=amount,
        status=InstallmentStatus.unpaid,
        sheet="سال 1404",
        cell=f"سال 1404!X{day}",
    )


# --------------------------------------------------------------------- pure rule tests


def test_clean_input_produces_no_issues() -> None:
    result = ParseResult(
        topics=["درمان"],
        persons=[_person("A"), _person("B")],
        loans=[
            _loan(
                number="1500",
                total=Decimal(10),
                topic="درمان",
                borrower=_borrower("A", Decimal(10)),
                lenders=[_lender("B", Decimal(10), (_inst(1404, 6, 15, Decimal(10)),))],
            )
        ],
    )
    validate(result)
    assert result.issues == []


def test_borrower_sum_mismatch_emits_error() -> None:
    result = ParseResult(
        topics=["درمان"],
        persons=[_person("A"), _person("B")],
        loans=[
            _loan(
                number="1500",
                total=Decimal(10),
                topic="درمان",
                borrower=_borrower("A", Decimal(5)),  # 5 vs total 10
                lenders=[_lender("B", Decimal(10))],
            )
        ],
    )
    validate(result)
    cats = {(i.severity, i.category) for i in result.issues}
    assert (IssueSeverity.error, IssueCategory.total_mismatch) in cats


def test_lender_sum_mismatch_emits_error() -> None:
    result = ParseResult(
        topics=["درمان"],
        persons=[_person("A"), _person("B"), _person("C")],
        loans=[
            _loan(
                number="1500",
                total=Decimal(10),
                topic="درمان",
                borrower=_borrower("A", Decimal(10)),
                lenders=[_lender("B", Decimal(3)), _lender("C", Decimal(4))],  # 7 vs 10
            )
        ],
    )
    validate(result)
    mismatches = [
        i
        for i in result.issues
        if i.category is IssueCategory.total_mismatch and i.context and "lender_sum" in i.context
    ]
    assert mismatches, f"expected lender_sum mismatch, got {result.issues}"


def test_installment_sum_mismatch_emits_error() -> None:
    result = ParseResult(
        topics=["درمان"],
        persons=[_person("A"), _person("B")],
        loans=[
            _loan(
                number="1500",
                total=Decimal(10),
                topic="درمان",
                borrower=_borrower("A", Decimal(10)),
                lenders=[
                    _lender(
                        "B",
                        Decimal(10),
                        (
                            _inst(1404, 6, 15, Decimal(4)),
                            _inst(1404, 7, 15, Decimal(4)),  # sum 8 != 10
                        ),
                    )
                ],
            )
        ],
    )
    validate(result)
    msg_hits = [
        i
        for i in result.issues
        if i.category is IssueCategory.total_mismatch and "اقساط" in i.message
    ]
    assert msg_hits


def test_unknown_topic_emits_warning() -> None:
    result = ParseResult(
        topics=["درمان"],
        persons=[_person("A"), _person("B")],
        loans=[
            _loan(
                number="1500",
                total=Decimal(10),
                topic="ناشناس",
                borrower=_borrower("A", Decimal(10)),
                lenders=[_lender("B", Decimal(10))],
            )
        ],
    )
    validate(result)
    assert any(
        i.category is IssueCategory.unknown_topic and i.severity is IssueSeverity.warning
        for i in result.issues
    )


def test_unresolved_person_for_borrower_lender_and_guarantor() -> None:
    result = ParseResult(
        topics=["درمان"],
        persons=[_person("A")],
        loans=[
            _loan(
                number="1500",
                total=Decimal(10),
                topic="درمان",
                borrower=_borrower("A", Decimal(10)),
                lenders=[_lender("ghost", Decimal(10))],
                guarantor="phantom",
            )
        ],
    )
    validate(result)
    unresolved = [i for i in result.issues if i.category is IssueCategory.unresolved_person]
    names = {i.context["name"] for i in unresolved if i.context}
    assert names == {"ghost", "phantom"}


def test_duplicate_phone_emits_error() -> None:
    result = ParseResult(
        topics=[],
        persons=[
            _person("A", "+989121234567"),
            _person("B", "+989121234567"),
        ],
        loans=[],
    )
    validate(result)
    assert any(i.category is IssueCategory.duplicate_phone for i in result.issues)


def test_placeholder_phones_not_flagged_as_duplicates() -> None:
    """+0__name__ placeholders are name-unique by construction; never duplicate."""
    result = ParseResult(
        topics=[],
        persons=[
            _person("A", "+0__A__"),
            _person("B", "+0__B__"),
        ],
        loans=[],
    )
    validate(result)
    assert not any(i.category is IssueCategory.duplicate_phone for i in result.issues)


def test_bad_day_emits_warning() -> None:
    bad = _inst(1404, 6, 99, Decimal(10))  # day 99 invalid
    result = ParseResult(
        topics=["درمان"],
        persons=[_person("A"), _person("B")],
        loans=[
            _loan(
                number="1500",
                total=Decimal(10),
                topic="درمان",
                borrower=_borrower("A", Decimal(10)),
                lenders=[_lender("B", Decimal(10), (bad,))],
            )
        ],
    )
    validate(result)
    assert any(i.category is IssueCategory.bad_day for i in result.issues)


# --------------------------------------------------------------------- integration


@pytest.fixture
def full_parsed(sample_xlsm_path: Path) -> ParseResult:
    wb = openpyxl.load_workbook(sample_xlsm_path, data_only=False, keep_vba=True)
    result = ParseResult()
    parse_topics(wb["موضوعات"], result)
    parse_people(wb["افراد"], result)
    parse_year_1404(wb["سال 1404"], 1404, result)
    parse_year_1405(wb["سال 1405"], 1405, result)
    return result


def test_full_parse_then_validate_flags_known_2501_mismatch(full_parsed: ParseResult) -> None:
    validate(full_parsed)
    mismatch_for_2501 = [
        i
        for i in full_parsed.issues
        if i.category is IssueCategory.total_mismatch
        and i.context
        and i.context.get("loan_number") == "2501"
    ]
    assert mismatch_for_2501, "validation must report loan 2501's lender vs installment mismatch"


def test_full_parse_then_validate_all_other_loans_pass(full_parsed: ParseResult) -> None:
    validate(full_parsed)
    other_mismatches = [
        i
        for i in full_parsed.issues
        if i.category is IssueCategory.total_mismatch
        and i.context
        and i.context.get("loan_number") != "2501"
    ]
    assert other_mismatches == [], "no total_mismatch expected outside loan 2501, got: " + str(
        [(i.message, i.context) for i in other_mismatches]
    )
