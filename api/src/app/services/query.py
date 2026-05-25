"""Shared query helpers used by every read endpoint.

- ``Page[T]`` / ``paginate(...)`` for cursor-less offset pagination.
- ``normalize_persian_name(...)`` — folds the variations admins type
  (Arabic ye/kaf, leading zero-width joiners, double spaces) into a
  canonical form for fuzzy search.
- ``parse_int_csv(...)`` for ``?id=1,2,3`` style query params.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Final

from pydantic import BaseModel, Field

# --------------------------------------------------------------------- pagination


# Defaults match DESIGN.md §5.3 (paginate everything, default 50, max 500).
DEFAULT_PAGE_SIZE: Final = 50
MAX_PAGE_SIZE: Final = 500
MIN_PAGE: Final = 1


class Page[T](BaseModel):
    """Generic paginated response envelope (PEP 695 type parameter syntax)."""

    items: list[T]
    total: int = Field(ge=0)
    page: int = Field(ge=MIN_PAGE)
    page_size: int = Field(ge=1, le=MAX_PAGE_SIZE)


def page_bounds(page: int, page_size: int) -> tuple[int, int]:
    """``(offset, limit)`` for SQL, clamped to safe ranges."""
    page = max(MIN_PAGE, page)
    page_size = max(1, min(MAX_PAGE_SIZE, page_size))
    return ((page - 1) * page_size, page_size)


# --------------------------------------------------------------------- Persian normalization

# Persian text routinely mixes Arabic and Persian forms of the same letter.
# Admins typing search queries will not type the canonical form every time, so
# we normalise the *query* and the stored *full_name* the same way before
# trigram comparison.

_ARABIC_TO_PERSIAN: Final[dict[int, int]] = {
    ord("ي"): ord("ی"),  # Arabic YEH → Persian YEH
    ord("ك"): ord("ک"),  # Arabic KAF → Persian KAF
    ord("ى"): ord("ی"),  # Alef maksura → Persian YEH
}
_PERSIAN_DIGITS_TO_ASCII: Final[dict[int, int]] = {
    ord(p): ord(a) for p, a in zip("۰۱۲۳۴۵۶۷۸۹", "0123456789", strict=True)
}
_ARABIC_DIGITS_TO_ASCII: Final[dict[int, int]] = {
    ord(p): ord(a) for p, a in zip("٠١٢٣٤٥٦٧٨٩", "0123456789", strict=True)
}
# Zero-width joiner / non-joiner / direction marks
_DROP_CHARS: Final[dict[int, None]] = {
    0x200B: None,  # ZWSP
    0x200C: None,  # ZWNJ
    0x200D: None,  # ZWJ
    0x200E: None,  # LRM
    0x200F: None,  # RLM
    0xFEFF: None,  # BOM
}
_MULTI_WHITESPACE_RE: Final = re.compile(r"\s+")


def normalize_persian_name(value: str | None) -> str:
    """Canonicalise a name for fuzzy search.

    - NFC normalize.
    - Fold Arabic forms of YEH and KAF to their Persian counterparts.
    - Fold Persian and Arabic-Indic digits to ASCII.
    - Strip zero-width / direction marks.
    - Collapse runs of whitespace.
    - Lowercase (no-op for Persian script but harmless on mixed input).
    - Strip surrounding whitespace.
    """
    if not value:
        return ""
    s = unicodedata.normalize("NFC", value)
    s = s.translate(_ARABIC_TO_PERSIAN)
    s = s.translate(_PERSIAN_DIGITS_TO_ASCII)
    s = s.translate(_ARABIC_DIGITS_TO_ASCII)
    s = s.translate(_DROP_CHARS)
    s = _MULTI_WHITESPACE_RE.sub(" ", s)
    return s.strip().lower()


# --------------------------------------------------------------------- CSV params


def parse_int_csv(value: str | None) -> list[int]:
    """``"1,2,3"`` → ``[1,2,3]``.  Empty / None → ``[]``.  Bad tokens skipped."""
    if not value:
        return []
    out: list[int] = []
    for raw in value.split(","):
        s = raw.strip()
        if not s:
            continue
        try:
            out.append(int(s))
        except ValueError:
            continue
    return out
