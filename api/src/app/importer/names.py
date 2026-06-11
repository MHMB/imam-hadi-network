"""Person/topic name normalisation and identity keys.

The legacy workbook references people by free-typed Persian names, and the
same human shows up under several spellings across sheets and years:

- spacing variants — ``سیدساجدموسوی`` (سال 1401) vs ``سیدساجد موسوی`` (افراد);
- Arabic vs Persian codepoints — ``ي``/``ك`` vs ``ی``/``ک``;
- zero-width joiners pasted in from other apps;
- the fund's own name written three ways — ``صندوق امام هادی(ع)`` (افراد),
  ``صندوق امام هادی`` (سال 1403), bare ``صندوق`` (سال 1405).

``match_key`` collapses all of those to one identity string.  Removing *all*
whitespace is deliberate: two distinct people whose names differ only in
spacing are far less likely than one person typed twice, and the dashboard
treats names as identity (no phones exist in the real data).

``ALIASES`` handles the cases normalisation can't — distinct surface names
that admins confirmed mean the same entity.  Keys and values are raw
display strings; lookups go through ``match_key`` so spacing never matters.
"""

from __future__ import annotations

import hashlib
import unicodedata

_ZWNJ = "‌"
_ARABIC_TO_PERSIAN = str.maketrans({"ي": "ی", "ك": "ک", "ۀ": "ه", "ة": "ه"})

# Known same-entity surface forms → canonical display name.  The canonical
# spelling should be the one in the افراد master sheet when present.
ALIASES: dict[str, str] = {
    "صندوق امام هادی": "صندوق امام هادی(ع)",
    "صندوق": "صندوق امام هادی(ع)",
}


def normalize_display(value: object) -> str:
    """NFC + trim + collapse internal whitespace runs to single spaces."""
    if value is None:
        return ""
    text = unicodedata.normalize("NFC", str(value)).strip()
    return " ".join(text.split())


def match_key(name: object) -> str:
    """Identity key: normalised, Persian-codepoint, whitespace-free."""
    text = normalize_display(name).translate(_ARABIC_TO_PERSIAN)
    return text.replace(_ZWNJ, "").replace(" ", "")


_ALIAS_KEYS: dict[str, str] = {match_key(src): dst for src, dst in ALIASES.items()}


def canonical_name(name: object) -> str:
    """Alias-resolved display name (or the cleaned input when not aliased)."""
    display = normalize_display(name)
    return _ALIAS_KEYS.get(match_key(display), display)


def resolve_key(name: object) -> str:
    """Identity key after alias resolution — the writer's person-lookup key."""
    return match_key(canonical_name(name))


def placeholder_phone(name: object) -> str:
    """Synthetic unique phone for persons that have none in the workbook.

    Person identity in the DB is the phone column; the real data carries no
    phones at all, so every person gets a deterministic placeholder derived
    from their identity key.  Hashing keeps it inside ``String(32)`` for
    arbitrarily long Persian names; the ``+0__`` prefix is the established
    marker the issues page and the duplicate-phone check pattern-match on.
    """
    digest = hashlib.sha256(resolve_key(name).encode("utf-8")).hexdigest()[:16]
    return f"+0__{digest}"
