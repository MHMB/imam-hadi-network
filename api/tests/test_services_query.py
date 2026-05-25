"""Tests for ``app.services.query`` — pagination + Persian normalize + CSV."""

from __future__ import annotations

import pytest

from app.services.query import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    normalize_persian_name,
    page_bounds,
    parse_int_csv,
)

# --- pagination ---


@pytest.mark.parametrize(
    ("page", "size", "expected"),
    [
        (1, 50, (0, 50)),
        (2, 50, (50, 50)),
        (3, 20, (40, 20)),
        # Clamp page < 1 to 1
        (0, 10, (0, 10)),
        (-7, 10, (0, 10)),
        # Clamp page_size > MAX
        (1, MAX_PAGE_SIZE + 100, (0, MAX_PAGE_SIZE)),
        # Clamp page_size < 1
        (1, 0, (0, 1)),
    ],
)
def test_page_bounds(page: int, size: int, expected: tuple[int, int]) -> None:
    assert page_bounds(page, size) == expected


def test_default_page_size_matches_design() -> None:
    assert DEFAULT_PAGE_SIZE == 50
    assert MAX_PAGE_SIZE == 500


# --- Persian normalisation ---


def test_normalize_arabic_yeh_and_kaf_to_persian() -> None:
    assert normalize_persian_name("علي اكبر") == normalize_persian_name("علی اکبر")


def test_normalize_persian_and_arabic_digits_to_ascii() -> None:
    assert normalize_persian_name("نفر ۱") == "نفر 1"
    assert normalize_persian_name("نفر ٢") == "نفر 2"


def test_normalize_strips_zwnj_and_rlm() -> None:
    # ZWNJ between characters
    raw = "نام‌خانوادگی"
    assert normalize_persian_name(raw) == "نامخانوادگی"


def test_normalize_collapses_whitespace_and_trims() -> None:
    assert normalize_persian_name("  محمد   رضا  ") == "محمد رضا"


def test_normalize_none_and_empty() -> None:
    assert normalize_persian_name(None) == ""
    assert normalize_persian_name("") == ""
    assert normalize_persian_name("   ") == ""


# --- CSV parser ---


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, []),
        ("", []),
        ("1", [1]),
        ("1,2,3", [1, 2, 3]),
        # Whitespace tolerated
        (" 4 , 5 ,6 ", [4, 5, 6]),
        # Bad tokens silently dropped (no exception, no zeros)
        ("1,foo,3", [1, 3]),
        # Repeated separators give empty tokens, also dropped
        ("1,,2", [1, 2]),
    ],
)
def test_parse_int_csv(raw: str | None, expected: list[int]) -> None:
    assert parse_int_csv(raw) == expected
