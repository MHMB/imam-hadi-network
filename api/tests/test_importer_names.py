"""Unit tests for person-name identity keys and placeholders."""

from __future__ import annotations

from app.importer.names import (
    canonical_name,
    match_key,
    normalize_display,
    placeholder_phone,
    resolve_key,
)


def test_normalize_display_collapses_whitespace() -> None:
    assert normalize_display("  علی   رضایی ") == "علی رضایی"
    assert normalize_display(None) == ""


def test_match_key_ignores_spacing() -> None:
    # Real variants observed across year sheets vs the افراد master.
    assert match_key("سیدساجدموسوی") == match_key("سیدساجد موسوی")


def test_match_key_normalises_arabic_codepoints_and_zwnj() -> None:
    assert match_key("علي") == match_key("علی")  # Arabic yeh
    assert match_key("كاظم") == match_key("کاظم")  # Arabic kaf
    assert match_key("سیف‌الله بهرامی") == match_key("سیف الله بهرامی")


def test_fund_aliases_resolve_to_master_spelling() -> None:
    canonical = "صندوق امام هادی(ع)"
    # Identity: every observed surface form keys to the master row.
    for variant in ("صندوق امام هادی", "صندوق", "صندوق امام هادی (ع)"):
        assert resolve_key(variant) == resolve_key(canonical)
    # Display: the aliased shorthands canonicalise to the master spelling
    # (the spaced (ع) variant already key-matches, no alias entry needed).
    for variant in ("صندوق امام هادی", "صندوق"):
        assert canonical_name(variant) == canonical


def test_non_aliased_names_pass_through() -> None:
    assert canonical_name("مامانجون") == "مامانجون"


def test_placeholder_phone_is_stable_short_and_variant_invariant() -> None:
    a = placeholder_phone("سیدساجد موسوی")
    assert a == placeholder_phone("سیدساجدموسوی")  # same identity → same phone
    assert a.startswith("+0__")
    assert len(a) <= 32
    # Long names must still fit String(32).
    long_name = "سیدبهاالدین حسینی دوست علی خسروی"
    assert len(placeholder_phone(long_name)) <= 32
    assert placeholder_phone(long_name) != a
