"""Tests for ``app.importer.phone.canonicalize``."""

from __future__ import annotations

import pytest

from app.importer.phone import canonicalize
from app.models.enums import IssueCategory


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Iranian mobile, leading zero
        ("09121234567", "+989121234567"),
        # With spaces and dashes
        ("0912-123-4567", "+989121234567"),
        ("0912 123 4567", "+989121234567"),
        # Already E.164
        ("+989121234567", "+989121234567"),
        # International access prefix
        ("00989121234567", "+989121234567"),
        # No leading zero
        ("9121234567", "+989121234567"),
    ],
)
def test_valid_iranian_mobile_variants(raw: str, expected: str) -> None:
    result = canonicalize(raw)
    assert result.canonical == expected
    assert result.issue is None
    assert result.raw == raw


def test_persian_digits_fold_to_ascii() -> None:
    result = canonicalize("۰۹۱۲۱۲۳۴۵۶۷")
    assert result.canonical == "+989121234567"
    assert result.issue is None
    assert result.raw == "۰۹۱۲۱۲۳۴۵۶۷"  # raw preserved


def test_arabic_indic_digits_fold_to_ascii() -> None:
    result = canonicalize("٠٩١٢١٢٣٤٥٦٧")
    assert result.canonical == "+989121234567"
    assert result.issue is None


def test_none_and_empty_string() -> None:
    for value in (None, "", "   "):
        result = canonicalize(value)
        assert result.canonical == ""
        assert result.issue is IssueCategory.unknown_phone_format


def test_garbage_input() -> None:
    result = canonicalize("not-a-number-at-all")
    assert result.canonical == ""
    assert result.issue is IssueCategory.unknown_phone_format
    assert result.raw == "not-a-number-at-all"


def test_parseable_but_too_short_is_flagged() -> None:
    # Right country code, wrong length — phonenumbers parses but rejects validity.
    result = canonicalize("+98912123")
    assert result.issue is IssueCategory.unknown_phone_format
    # Whatever E.164 phonenumbers produces, it should at least carry the prefix.
    assert result.canonical.startswith("+98")


def test_numeric_cell_value_accepted() -> None:
    # openpyxl may hand us a number, not a string, if the cell was typed as numeric.
    result = canonicalize(9121234567)
    assert result.canonical == "+989121234567"
    assert result.issue is None


def test_raw_preserves_original_for_audit() -> None:
    raw = "  ۰۹۱۲-۱۲۳-۴۵۶۷  "
    result = canonicalize(raw)
    assert result.canonical == "+989121234567"
    assert (
        result.raw == "۰۹۱۲-۱۲۳-۴۵۶۷"
    )  # stripped of surrounding whitespace, but otherwise verbatim


def test_default_region_override() -> None:
    # Same number, parsed as US — would be invalid (only 10 digits expected from US, leading 0).
    result = canonicalize("09121234567", default_region="US")
    # Either fails to parse or marks invalid; in both cases issue should be set.
    assert result.issue is IssueCategory.unknown_phone_format
