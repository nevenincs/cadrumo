"""Derive structural lookup keys from legal catalogue citations."""

from __future__ import annotations

import re
from typing import Final

from cadrumo.core.text_fold import normalise_corpus_text

#: Latin ordinals name an article; they are part of its identity and are
#: concatenated into the anchor. Anything else trailing a number is scope (an
#: apartado) or a vintage year, and narrows WITHIN the article.
_LATIN_ORDINALS: Final = frozenset(
    {
        "bis",
        "ter",
        "quater",
        "quinquies",
        "sexies",
        "septies",
        "octies",
        "nonies",
        "decies",
        "undecies",
        "duodecies",
        "terdecies",
        "quaterdecies",
        "quinquiesdecies",
        "sexiesdecies",
        "septiesdecies",
        "octiesdecies",
        "noniesdecies",
        "vicies",
        "unvicies",
        "duovicies",
        "tervicies",
        "quatervicies",
        "quinvicies",
        "sexvicies",
        "septvicies",
        "octovicies",
        "novovicies",
        "tricies",
    }
)

_HEADING_SPLIT: Final = re.compile(r"[.:]")
_NON_ALNUM: Final = re.compile(r"[^a-z0-9]")
_ARTICLE_PREFIX: Final = re.compile(r"^(?:articulos?|arts?)(?=\d)")

_UNITS_FEMININE: Final = (
    "",
    "primera",
    "segunda",
    "tercera",
    "cuarta",
    "quinta",
    "sexta",
    "septima",
    "octava",
    "novena",
)
_UNITS_MASCULINE: Final = (
    "",
    "primero",
    "segundo",
    "tercero",
    "cuarto",
    "quinto",
    "sexto",
    "septimo",
    "octavo",
    "noveno",
)
_TENS_FEMININE: Final = (
    "",
    "decima",
    "vigesima",
    "trigesima",
    "cuadragesima",
    "quincuagesima",
    "sexagesima",
    "septuagesima",
    "octogesima",
    "nonagesima",
)
_TENS_MASCULINE: Final = (
    "",
    "decimo",
    "vigesimo",
    "trigesimo",
    "cuadragesimo",
    "quincuagesimo",
    "sexagesimo",
    "septuagesimo",
    "octogesimo",
    "nonagesimo",
)
_IRREGULAR_FEMININE: Final = {11: "undecima", 12: "duodecima"}
_IRREGULAR_MASCULINE: Final = {11: "undecimo", 12: "duodecimo"}

#: Structural families whose units BOE titles with a written ordinal rather
#: than a number, keyed by the token the catalogue uses.
_FAMILIES: Final = {
    "da": ("Disposicion adicional", "da"),
    "dt": ("Disposicion transitoria", "dt"),
    "df": ("Disposicion final", "df"),
    "dd": ("Disposicion derogatoria", "dd"),
}


def ordinal_spellings(number: int, *, feminine: bool) -> tuple[str, ...]:
    """Return the written Spanish ordinals BOE plausibly uses for ``number``.

    Several spellings are returned rather than one, because BOE is not
    self-consistent: the same corpus carries "vigésima primera" and "vigésimo
    primera" for the twenty-first disposición, and elides the doubled vowel in
    "decimoctava". A candidate ladder absorbs that variation, where committing
    to one spelling would silently drop an entry out of the comparison.

    Args:
        number: The ordinal position, from 1 to 99.
        feminine: Whether the family takes feminine agreement (disposiciones
            do; an orden's numbered apartados take masculine).

    Returns:
        Distinct spellings in preference order, empty when out of range.
    """
    if not 1 <= number <= 99:
        return ()
    units = _UNITS_FEMININE if feminine else _UNITS_MASCULINE
    tens = _TENS_FEMININE if feminine else _TENS_MASCULINE
    other_tens = _TENS_MASCULINE if feminine else _TENS_FEMININE
    irregular = _IRREGULAR_FEMININE if feminine else _IRREGULAR_MASCULINE
    if number < 10:
        return (units[number],)
    ten, unit = divmod(number, 10)
    if unit == 0:
        return (tens[ten],)
    spellings = []
    if number in irregular:
        spellings.append(irregular[number])
    spellings.extend(
        (
            f"{tens[ten]} {units[unit]}",
            tens[ten] + units[unit],
            f"{other_tens[ten]} {units[unit]}",
            other_tens[ten] + units[unit],
        )
    )
    if ten == 1:
        # "decimoctava", not "decimaoctava": BOE elides the doubled vowel.
        spellings.append(tens[1][:-1] + units[unit])
        spellings.append(_TENS_MASCULINE[1] + units[unit])
    return tuple(dict.fromkeys(spellings))


def candidate_keys(citation_token: str) -> tuple[str, ...]:
    """Return lookup keys for the provision a catalogue citation token names.

    The token is the part of an entry id after the colon -- ``art-81``,
    ``art-163-octiesdecies``, ``art-68-1``, ``da-18``, ``df-unica``,
    ``apartado-3``. Keys are returned in preference order and are consumed by
    the canonical anchor resolver, which accepts an anchor OR a structural
    heading; this function never selects a unit itself.

    Args:
        citation_token: The catalogue's own citation token.

    Returns:
        Distinct keys in preference order, empty when the token is not a
        recognised structural citation.
    """
    parts = [part for part in re.split(r"[-_.]", citation_token.strip().lower()) if part]
    if not parts:
        return ()
    head, rest = parts[0], parts[1:]

    if head in {"art", "arts", "articulo", "articulos"}:
        return _article_keys(rest)
    if _is_numbered_section(head, rest):
        keys = [word.capitalize() for word in ordinal_spellings(int(rest[0]), feminine=False)]
        keys.append(rest[0])
        return tuple(dict.fromkeys(keys))
    if head == "anexo" and rest:
        return (f"Anexo {' '.join(rest)}", "an" + "".join(rest))
    family = _FAMILIES.get(head)
    if family is not None:
        return _family_keys(family, rest)
    return ()


def _article_keys(rest: list[str]) -> tuple[str, ...]:
    if not rest:
        return ()
    if not rest[0].isdigit():
        # "Artículo único" and its kin: no number to concatenate an ordinal to.
        return ("Articulo " + " ".join(rest), "a" + "".join(rest))
    number = rest[0]
    named: list[str] = []
    for part in rest[1:]:
        if part not in _LATIN_ORDINALS:
            break
        named.append(part)
    keys: list[str] = []
    if named:
        keys.append(f"Articulo {number} {' '.join(named)}")
        keys.append("a" + number + "".join(named))
    # A trailing apartado digit or vintage year narrows within the article; the
    # consolidated file carries the whole article, so both are simply dropped.
    # A hyphenated ``a68-1`` key is deliberately NOT emitted: canonicalisation
    # strips the hyphen, so it silently collides with article 681.
    keys.append(f"Articulo {number}")
    keys.append("a" + number)
    return tuple(dict.fromkeys(keys))


def _family_keys(family: tuple[str, str], rest: list[str]) -> tuple[str, ...]:
    heading, prefix = family
    if not rest or rest[0] in {"unica", "unico"}:
        return (f"{heading} unica", prefix)
    if rest[0].isdigit():
        keys = [f"{heading} {word}" for word in ordinal_spellings(int(rest[0]), feminine=True)]
        keys.append(f"{prefix}{rest[0]}")
        return tuple(dict.fromkeys(keys))
    return (f"{heading} {' '.join(rest)}", prefix + "".join(rest))


def structural_key(text: str) -> str:
    """Return a comparison key for a unit heading, ignoring its caption prose."""
    heading = _HEADING_SPLIT.split(text, maxsplit=1)[0]
    folded = _NON_ALNUM.sub("", normalise_corpus_text(heading))
    return _ARTICLE_PREFIX.sub("a", folded, count=1)


def _is_numbered_section(head: str, rest: list[str]) -> bool:
    """Recognize the existing numbered apartado citation without broadening its keys."""
    return head == "apartado" and bool(rest) and rest[0].isdigit()
