"""Tests for the year-1404 row-pair parser against the sample xlsm."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import openpyxl
import pytest

from app.importer.models import ParsedLoan, ParseResult
from app.importer.parsers.year_1404 import parse_year_1404
from app.models.enums import InstallmentStatus, LoanPartyRole


@pytest.fixture
def parsed(sample_xlsm_path: Path) -> ParseResult:
    wb = openpyxl.load_workbook(sample_xlsm_path, data_only=False, keep_vba=True)
    result = ParseResult()
    parse_year_1404(wb["سال 1404"], 1404, result)
    return result


def _loan(parsed: ParseResult, loan_number: str) -> ParsedLoan:
    matches = [loan for loan in parsed.loans if loan.loan_number == loan_number]
    assert len(matches) == 1, (
        f"expected exactly one loan #{loan_number}, got {len(matches)}: {[ln.loan_number for ln in parsed.loans]}"
    )
    return matches[0]


# --- structural ---


def test_parses_expected_loan_count(parsed: ParseResult) -> None:
    # Sample 1404 sheet contains 5 loan groups: 1500..1504.
    numbers = sorted(ln.loan_number for ln in parsed.loans)
    assert numbers == ["1500", "1501", "1502", "1503", "1504"], numbers


def test_every_loan_has_one_borrower_party_first(parsed: ParseResult) -> None:
    for loan in parsed.loans:
        assert loan.parties[0].role is LoanPartyRole.borrower
        assert loan.parties[0].display_order == 0
        lenders = [p for p in loan.parties[1:] if p.role is LoanPartyRole.lender]
        assert lenders, f"loan {loan.loan_number} has no lender parties"


def test_year_and_source_sheet_set(parsed: ParseResult) -> None:
    for loan in parsed.loans:
        assert loan.persian_year == 1404
        assert loan.source_sheet == "سال 1404"


# --- loan 1500: 1 borrower (نفر 1, 20) + 3 lenders (3+7+10=20) ---


def test_loan_1500_borrower_and_lenders(parsed: ParseResult) -> None:
    loan = _loan(parsed, "1500")
    assert loan.total_amount == Decimal(20)
    assert loan.topic_name == "درمان"
    assert loan.liaison_label == "سید"
    assert loan.channel_number == "901"
    assert loan.description == "آشنای علی"

    borrower = loan.parties[0]
    assert borrower.role is LoanPartyRole.borrower
    assert borrower.person_name == "نفر 1"
    assert borrower.amount == Decimal(20)

    lenders = [p for p in loan.parties if p.role is LoanPartyRole.lender]
    assert [ln.person_name for ln in lenders] == ["نفر 2", "نفر 3", "نفر 4"]
    assert [ln.amount for ln in lenders] == [Decimal(3), Decimal(7), Decimal(10)]
    assert sum((ln.amount for ln in lenders), Decimal(0)) == loan.total_amount


def test_loan_1500_lender_n2_installment_paid(parsed: ParseResult) -> None:
    loan = _loan(parsed, "1500")
    lender_n2 = next(p for p in loan.parties if p.person_name == "نفر 2")
    assert len(lender_n2.installments) == 1, lender_n2.installments
    inst = lender_n2.installments[0]
    assert inst.due_persian_year == 1404
    assert inst.due_persian_month == 6  # Shahrivar
    assert inst.due_day_of_month == 15
    assert inst.amount == Decimal(3)
    assert inst.status is InstallmentStatus.paid


# --- loan 1502: multi-installment schedule across multiple months ---


def test_loan_1502_lender_amounts_match_total(parsed: ParseResult) -> None:
    loan = _loan(parsed, "1502")
    assert loan.total_amount == Decimal(11)
    lenders = [p for p in loan.parties if p.role is LoanPartyRole.lender]
    # نفر 8 lent 5, نفر 4 lent 4, نفر 9 lent 2 → 11 total
    assert [ln.person_name for ln in lenders] == ["نفر 8", "نفر 4", "نفر 9"]
    assert sum((ln.amount for ln in lenders), Decimal(0)) == loan.total_amount


def test_loan_1502_lender_n8_full_schedule(parsed: ParseResult) -> None:
    loan = _loan(parsed, "1502")
    n8 = next(p for p in loan.parties if p.person_name == "نفر 8")
    # 5 monthly installments of 1 each (Shahrivar..Tir of next year), day 15.
    assert len(n8.installments) == 5
    assert sum((i.amount for i in n8.installments), Decimal(0)) == n8.amount
    assert {i.due_day_of_month for i in n8.installments} == {15}
    # The sample marks 4 of 5 as paid (green); the last (1405/04) is still unpaid.
    paid = sum(1 for i in n8.installments if i.status is InstallmentStatus.paid)
    unpaid = sum(1 for i in n8.installments if i.status is InstallmentStatus.unpaid)
    assert (paid, unpaid) == (4, 1), f"got paid={paid}, unpaid={unpaid}"


# --- loan 1503: half-amounts (5.5) preserved as Decimal ---


def test_loan_1503_fractional_amounts(parsed: ParseResult) -> None:
    loan = _loan(parsed, "1503")
    assert loan.total_amount == Decimal(11)
    n8 = next(p for p in loan.parties if p.person_name == "نفر 8")
    # 2 installments of 5.5 each
    assert sum((i.amount for i in n8.installments), Decimal(0)) == Decimal("11")
    assert all(i.amount == Decimal("5.5") for i in n8.installments)


# --- loan 1504: multiple lenders, multi-year schedule (1404→1405) ---


def test_loan_1504_schedule_spans_years(parsed: ParseResult) -> None:
    loan = _loan(parsed, "1504")
    n2 = next(p for p in loan.parties if p.person_name == "نفر 2")
    years = {i.due_persian_year for i in n2.installments}
    assert 1404 in years
    assert 1405 in years, f"expected 1405 installments for نفر 2, got years={years}"
    assert sum((i.amount for i in n2.installments), Decimal(0)) == n2.amount


# --- totals invariant ---


def test_all_loan_totals_equal_sum_of_lender_amounts(parsed: ParseResult) -> None:
    for loan in parsed.loans:
        lender_sum = sum(
            (p.amount for p in loan.parties if p.role is LoanPartyRole.lender),
            Decimal(0),
        )
        assert lender_sum == loan.total_amount, (
            f"loan {loan.loan_number}: lenders sum {lender_sum} != total {loan.total_amount}"
        )


def test_all_lender_amounts_equal_sum_of_installments(parsed: ParseResult) -> None:
    for loan in parsed.loans:
        for party in loan.parties:
            if party.role is LoanPartyRole.lender and party.installments:
                inst_sum = sum((i.amount for i in party.installments), Decimal(0))
                assert inst_sum == party.amount, (
                    f"loan {loan.loan_number} lender {party.person_name}:"
                    f" installments sum {inst_sum} != amount {party.amount}"
                )
