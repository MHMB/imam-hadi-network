"""Tests for the year-1405+ row-major parser against the sample xlsm."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import openpyxl
import pytest

from app.importer.models import ParsedLoan, ParseResult
from app.importer.parsers.year_1405 import parse_year_1405
from app.models.enums import InstallmentStatus, LoanPartyRole


@pytest.fixture
def parsed(sample_xlsm_path: Path) -> ParseResult:
    wb = openpyxl.load_workbook(sample_xlsm_path, data_only=False, keep_vba=True)
    result = ParseResult()
    parse_year_1405(wb["سال 1405"], 1405, result)
    return result


def _loan(parsed: ParseResult, loan_number: str) -> ParsedLoan:
    matches = [loan for loan in parsed.loans if loan.loan_number == loan_number]
    assert len(matches) == 1, (
        f"expected one loan #{loan_number}, got {len(matches)}:"
        f" {[ln.loan_number for ln in parsed.loans]}"
    )
    return matches[0]


# --- structural ---


def test_parses_expected_loan_count(parsed: ParseResult) -> None:
    # Sample 1405 sheet has 4 loan groups: 2500..2503.
    numbers = sorted(ln.loan_number for ln in parsed.loans)
    assert numbers == ["2500", "2501", "2502", "2503"], numbers


def test_every_loan_has_borrower_first_then_lenders(parsed: ParseResult) -> None:
    for loan in parsed.loans:
        assert loan.parties[0].role is LoanPartyRole.borrower
        assert loan.parties[0].display_order == 0
        lenders = [p for p in loan.parties[1:] if p.role is LoanPartyRole.lender]
        assert lenders


def test_per_loan_guarantor_set_when_present(parsed: ParseResult) -> None:
    # 1405 finally populates ضامن on the loan row; sample sets it for all 4.
    assert all(loan.guarantor_name for loan in parsed.loans)


def test_year_and_source_sheet(parsed: ParseResult) -> None:
    for loan in parsed.loans:
        assert loan.persian_year == 1405
        assert loan.source_sheet == "سال 1405"


# --- loan 2500: borrower نفر 12 (10) + 2 lenders ---


def test_loan_2500_shape(parsed: ParseResult) -> None:
    loan = _loan(parsed, "2500")
    assert loan.total_amount == Decimal(10)
    assert loan.topic_name == "کار فرهنگی"
    assert loan.parties[0].role is LoanPartyRole.borrower
    assert loan.parties[0].person_name == "نفر 12"
    assert loan.guarantor_name == "نفر 20"
    assert loan.channel_number == "1158"
    lenders = [p for p in loan.parties if p.role is LoanPartyRole.lender]
    assert [ln.person_name for ln in lenders] == ["نفر 13", "نفر 4"]
    assert [ln.amount for ln in lenders] == [Decimal(5), Decimal(5)]


def test_loan_2500_lender_installments(parsed: ParseResult) -> None:
    loan = _loan(parsed, "2500")
    n13 = next(p for p in loan.parties if p.person_name == "نفر 13")
    assert len(n13.installments) == 1
    inst = n13.installments[0]
    assert (inst.due_persian_year, inst.due_persian_month, inst.due_day_of_month) == (1405, 1, 31)
    assert inst.amount == Decimal(5)

    n4 = next(p for p in loan.parties if p.person_name == "نفر 4")
    inst = n4.installments[0]
    assert (inst.due_persian_year, inst.due_persian_month, inst.due_day_of_month) == (1405, 2, 31)
    assert inst.amount == Decimal(5)


# --- loan 2502: 4 lenders summing to 22 ---


def test_loan_2502_multi_lender(parsed: ParseResult) -> None:
    loan = _loan(parsed, "2502")
    assert loan.total_amount == Decimal(22)
    lenders = [p for p in loan.parties if p.role is LoanPartyRole.lender]
    assert [ln.person_name for ln in lenders] == ["نفر 16", "نفر 4", "نفر 7", "نفر 11"]
    assert [ln.amount for ln in lenders] == [Decimal(5), Decimal(7), Decimal("4.5"), Decimal("5.5")]
    assert sum((ln.amount for ln in lenders), Decimal(0)) == loan.total_amount


def test_loan_2502_lender_n11_schedule(parsed: ParseResult) -> None:
    """نفر 11 lent 5.5 — split into a 3-on-Mordad-04 + 2.5-on-Aban-04."""
    loan = _loan(parsed, "2502")
    n11 = next(p for p in loan.parties if p.person_name == "نفر 11")
    schedule = [
        (i.due_persian_year, i.due_persian_month, i.due_day_of_month, i.amount)
        for i in n11.installments
    ]
    assert schedule == [
        (1405, 5, 4, Decimal(3)),
        (1405, 8, 4, Decimal("2.5")),
    ]
    assert sum((i.amount for i in n11.installments), Decimal(0)) == n11.amount


# --- payment status (green fill) ---


def test_paid_installments_marked_from_green_fill(parsed: ParseResult) -> None:
    """Sample sheet marks two amount cells green: سال 1405!N3 (نفر 13 / 2500)
    and سال 1405!P6 (نفر 16 / 2502).  Every other installment is unpaid."""
    n13_2500 = next(
        p
        for p in _loan(parsed, "2500").parties
        if p.role is LoanPartyRole.lender and p.person_name == "نفر 13"
    )
    assert n13_2500.installments[0].status is InstallmentStatus.paid

    n16_2502 = next(
        p
        for p in _loan(parsed, "2502").parties
        if p.role is LoanPartyRole.lender and p.person_name == "نفر 16"
    )
    assert n16_2502.installments[0].status is InstallmentStatus.paid

    # Everything else is unpaid in the sample.
    paid_cells = []
    for loan in parsed.loans:
        for p in loan.parties:
            if p.role is LoanPartyRole.lender:
                for inst in p.installments:
                    if inst.status is InstallmentStatus.paid:
                        paid_cells.append(inst.cell)
    assert sorted(paid_cells) == ["سال 1405!N3", "سال 1405!P10", "سال 1405!P6"]


# --- invariants ---


def test_loan_totals_equal_sum_of_lenders(parsed: ParseResult) -> None:
    for loan in parsed.loans:
        lender_sum = sum(
            (p.amount for p in loan.parties if p.role is LoanPartyRole.lender),
            Decimal(0),
        )
        assert lender_sum == loan.total_amount, (
            f"loan {loan.loan_number}: lenders sum {lender_sum} != total {loan.total_amount}"
        )


def test_lender_amounts_equal_sum_of_installments_when_consistent(parsed: ParseResult) -> None:
    """Most loans satisfy Σ installments == lender amount.

    Loan 2501 is the one exception in the sample — لender نفر 13 lent 32 but
    only 30 of installments are scheduled (20 + 10 on Ordibehesht / Tir).
    That is a real flaw in the source workbook; the validation layer (P2.7)
    will emit a total_mismatch issue for it.  We assert here that every
    *other* loan is internally consistent.
    """
    for loan in parsed.loans:
        if loan.loan_number == "2501":
            continue
        for party in loan.parties:
            if party.role is LoanPartyRole.lender and party.installments:
                inst_sum = sum((i.amount for i in party.installments), Decimal(0))
                assert inst_sum == party.amount, (
                    f"loan {loan.loan_number} lender {party.person_name}:"
                    f" installments sum {inst_sum} != amount {party.amount}"
                )


def test_loan_2501_is_internally_inconsistent_in_sample(parsed: ParseResult) -> None:
    """The known sample-data flaw — recorded here so the regression is explicit."""
    loan = _loan(parsed, "2501")
    n13 = next(p for p in loan.parties if p.person_name == "نفر 13")
    inst_sum = sum((i.amount for i in n13.installments), Decimal(0))
    assert n13.amount == Decimal(32)
    assert inst_sum == Decimal(30)
