"""Phone-number canonicalisation.

Goal: turn a raw cell value from the legacy xlsm into a single canonical
form (``+98XXXXXXXXXX``) so each person has exactly one identity key in
the database.  Bad / unfamiliar inputs are kept in ``phone_raw`` and the
importer emits an ``unknown_phone_format`` warning rather than crashing.

We don't reject anything — the dashboard is read-only and surfaces
problems for admins to fix in the source xlsm.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

import phonenumbers

from app.models.enums import IssueCategory

# Persian / Arabic digit characters that need to fold to ASCII before
# phonenumbers parses anything.
_PERSIAN_DIGITS: Final[dict[int, int]] = {
    ord(p): ord(a) for p, a in zip("۰۱۲۳۴۵۶۷۸۹", "0123456789", strict=True)
}
_ARABIC_DIGITS: Final[dict[int, int]] = {
    ord(p): ord(a) for p, a in zip("٠١٢٣٤٥٦٧٨٩", "0123456789", strict=True)
}

# Whitespace, ASCII separators, plus Unicode ZERO WIDTH NON-JOINER (U+200C)
# and RIGHT-TO-LEFT MARK (U+200F) which often appear in Persian-input cells.
# Use explicit \u escapes so the literal control characters don't sit in
# the source file (ruff PLE2502).
_SEPARATORS_RE: Final = re.compile("[" + "\\s\\-()" + chr(0x200C) + chr(0x200F) + "]+")


@dataclass(frozen=True, slots=True)
class CanonicalPhone:
    """Result of canonicalising a raw phone string.

    Attributes:
        canonical: E.164 form (e.g. ``+989121234567``) — empty string only
            if input was unparseable and fallback also failed.
        raw:       Input verbatim (trimmed of NBSP / direction marks but
            otherwise preserved) for storage in ``person.phone_raw``.
        issue:     ``None`` if parsing was confident; otherwise the
            ``IssueCategory`` the importer should emit.
    """

    canonical: str
    raw: str
    issue: IssueCategory | None


def _fold_to_ascii(s: str) -> str:
    """Convert Persian + Arabic digits to ASCII; collapse separators."""
    s = s.translate(_PERSIAN_DIGITS).translate(_ARABIC_DIGITS)
    return _SEPARATORS_RE.sub("", s).strip()


def canonicalize(value: object, *, default_region: str = "IR") -> CanonicalPhone:
    """Return a canonical phone for ``value`` (which may be ``None`` or numeric).

    Strategy:
        1. Coerce to ``str``, fold Persian/Arabic digits → ASCII, strip
           whitespace and direction marks.
        2. Try ``phonenumbers.parse`` with ``IR`` as the default region —
           accepts ``+98...``, ``0098...``, ``09...``, etc.
        3. If valid → return E.164 form, no issue.
        4. If parseable but not valid (e.g. wrong length for IR) → return
           the parsed form + ``unknown_phone_format`` warning.
        5. If unparseable → return ``""`` + warning, keep raw string so
           the importer can still create a Person with a placeholder key.
    """
    raw = "" if value is None else str(value).strip()
    if not raw:
        return CanonicalPhone(canonical="", raw="", issue=IssueCategory.unknown_phone_format)

    cleaned = _fold_to_ascii(raw)
    if not cleaned:
        return CanonicalPhone(canonical="", raw=raw, issue=IssueCategory.unknown_phone_format)

    try:
        parsed = phonenumbers.parse(cleaned, default_region)
    except phonenumbers.NumberParseException:
        return CanonicalPhone(canonical="", raw=raw, issue=IssueCategory.unknown_phone_format)

    if not phonenumbers.is_valid_number(parsed):
        e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        return CanonicalPhone(canonical=e164, raw=raw, issue=IssueCategory.unknown_phone_format)

    canonical = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    return CanonicalPhone(canonical=canonical, raw=raw, issue=None)
