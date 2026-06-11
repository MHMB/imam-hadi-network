"""Tests for the topics + people sub-parsers against the sample xlsm."""

from __future__ import annotations

from pathlib import Path

import openpyxl
import pytest

from app.importer.models import ParseResult
from app.importer.names import placeholder_phone
from app.importer.parsers.people import parse_people
from app.importer.parsers.topics import parse_topics
from app.models.enums import GuarantorRole, IssueCategory, IssueSeverity


@pytest.fixture
def wb(sample_xlsm_path: Path) -> openpyxl.Workbook:
    return openpyxl.load_workbook(sample_xlsm_path, data_only=False, keep_vba=True)


# --------------------------------------------------------------------- topics


def test_parse_topics_finds_17_unique_names(wb: openpyxl.Workbook) -> None:
    result = ParseResult()
    parse_topics(wb["موضوعات"], result)
    assert len(result.topics) == 17, (
        f"expected 17 topics, got {len(result.topics)}: {result.topics}"
    )


def test_parse_topics_includes_canonical_names(wb: openpyxl.Workbook) -> None:
    result = ParseResult()
    parse_topics(wb["موضوعات"], result)
    # Spot check a few that the dashboard will surface as filters
    for must in ("درمان", "ازدواج", "خانه", "نامعلوم", "وسیله نقلیه"):
        assert must in result.topics


def test_parse_topics_no_duplicates_no_blanks(wb: openpyxl.Workbook) -> None:
    result = ParseResult()
    parse_topics(wb["موضوعات"], result)
    assert len(set(result.topics)) == len(result.topics)
    assert "" not in result.topics
    assert all(t.strip() == t for t in result.topics)


# --------------------------------------------------------------------- people


def test_parse_people_counts_match_sample(wb: openpyxl.Workbook) -> None:
    result = ParseResult()
    parse_people(wb["افراد"], result)
    # Sample has 21 named persons (نفر 1 .. نفر 21)
    names = [p.full_name for p in result.persons]
    assert len(names) == 21, f"expected 21 persons, got {len(names)}: {names}"
    assert "نفر 1" in names
    assert "نفر 21" in names


def test_parse_people_phone_placeholder_when_blank(wb: openpyxl.Workbook) -> None:
    result = ParseResult()
    parse_people(wb["افراد"], result)
    # All sample rows have blank phone → all should fall back to placeholders:
    # deterministic per name, marked with the +0__ prefix, and short enough
    # for the String(32) phone column regardless of name length.
    for p in result.persons:
        assert p.phone_canonical == placeholder_phone(p.full_name)
        assert p.phone_canonical.startswith("+0__"), f"unexpected phone {p.phone_canonical}"
        assert len(p.phone_canonical) <= 32
    # Distinct names must never collide on one placeholder.
    placeholders = [p.phone_canonical for p in result.persons]
    assert len(set(placeholders)) == len(placeholders)


def test_parse_people_emits_unknown_phone_warnings(wb: openpyxl.Workbook) -> None:
    result = ParseResult()
    parse_people(wb["افراد"], result)
    phone_issues = [i for i in result.issues if i.category is IssueCategory.unknown_phone_format]
    # One warning per sample person (all phones blank)
    assert len(phone_issues) == 21
    assert all(i.severity is IssueSeverity.warning for i in phone_issues)
    assert all(i.cell is not None and i.cell.startswith("افراد!C") for i in phone_issues)


def test_parse_people_resolves_guarantor_slots(wb: openpyxl.Workbook) -> None:
    result = ParseResult()
    parse_people(wb["افراد"], result)
    # Per the sample: نفر 6 has "تایید=1" and نفر 4 in the main guarantor slot.
    by_name = {p.full_name: p for p in result.persons}

    n4 = by_name["نفر 4"]
    assert any(
        link.role is GuarantorRole.main and link.guarantor_name == "نفر 4"
        for link in n4.guarantor_links
    ), f"نفر 4's guarantor links: {n4.guarantor_links}"

    # نفر 17 has slots filled across secondary_2, secondary_3, main per SPEC.md §2.2.
    n17 = by_name["نفر 17"]
    roles = {link.role for link in n17.guarantor_links}
    assert GuarantorRole.main in roles
    assert GuarantorRole.secondary_2 in roles
    assert GuarantorRole.secondary_3 in roles


def test_parse_people_verified_flag_set_for_marked_rows(wb: openpyxl.Workbook) -> None:
    result = ParseResult()
    parse_people(wb["افراد"], result)
    by_name = {p.full_name: p for p in result.persons}
    # Sample marks نفر 6 and نفر 12 as verified ('1' in تایید column)
    assert by_name["نفر 6"].is_verified is True
    assert by_name["نفر 12"].is_verified is True
    # And a row without the flag remains unverified
    assert by_name["نفر 1"].is_verified is False


def test_parse_people_flags_broken_ref_rollups(wb: openpyxl.Workbook) -> None:
    result = ParseResult()
    parse_people(wb["افراد"], result)
    broken = [i for i in result.issues if i.category is IssueCategory.broken_ref]
    # Sample has #REF! degradation on the rollup columns of rows 16..23 (نفر 14..21).
    # Each affected row contributes 1+ warnings; expect ≥1.
    assert broken, "expected at least one broken_ref warning from the sample's #REF! cells"
    assert all(i.severity is IssueSeverity.warning for i in broken)
