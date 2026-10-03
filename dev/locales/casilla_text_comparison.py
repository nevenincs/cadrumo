"""Casilla wording normalization and legal content comparison."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

from .casilla_text_policy import (
    _ASCII_COMPARISON,
    _CONTENT_TOKEN,
    _DERIVED_HELP,
    _PERCENT_WORDS,
    _SEGMENT,
    _SEGMENT_PROSE,
    _SPANISH_FUNCTION_WORDS,
    _SPELLED_NUMBERS,
    _THOUSANDS,
    _WORD_TOKEN,
)


def _normalised(text: str) -> str:
    """Fold case, accents and punctuation so only a wording change counts."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    letters = "".join(character for character in decomposed if not unicodedata.combining(character))
    return " ".join(re.sub(r"[^\w]+", " ", letters).split())


def _content_tokens(text: str, *, spelled: bool = False) -> Counter[str]:
    """Return the numbers, box references and comparison symbols a label states.

    Compared across languages, so a rendering difference is not a difference in
    content: "25 por 100" and "25%" state one rate, a date is reordered, and the
    separators inside a number or between the parts of a citation vary. With
    ``spelled``, a number written as a word counts as that number, which is how
    a translation may render a digit the Spanish wrote; the Spanish side never
    reads words, because its own prose says "un" and "dos" as articles.
    """
    found: Counter[str] = Counter()
    grouped = _PERCENT_WORDS.sub("%", text)
    for ascii_form, symbol in _ASCII_COMPARISON.items():
        grouped = grouped.replace(ascii_form, symbol)
    plain = _THOUSANDS.sub(lambda match: re.sub(r"[^0-9]", "", match.group()), grouped)
    for token in _CONTENT_TOKEN.findall(plain):
        cleaned = re.sub(r"\s+", "", token)
        found[cleaned.lstrip("0") or "0" if cleaned.isdigit() else cleaned] += 1
    if spelled:
        _collect_spelled_content_numbers(text, found)
    return found


def _segments(text: str) -> tuple[str, ...]:
    """Split a composed label into its segments, leaving arithmetic whole.

    ``" - "`` both joins the segments of a label and subtracts one box from
    another. A subtraction is written inside its parentheses and its operands
    are box references rather than prose, so a split is read only outside
    brackets and only when every segment states words.
    """
    depth = 0
    parts: list[str] = []
    start = 0
    for match in re.finditer(rf"[()\[\]]|{_SEGMENT.pattern}", text):
        bracket = match.group()
        if bracket in "([":
            depth += 1
        elif bracket in ")]":
            depth = max(0, depth - 1)
        elif depth == 0:
            parts.append(text[start : match.start()])
            start = match.end()
    parts.append(text[start:])
    if len(parts) < 2 or not all(_SEGMENT_PROSE.search(part) for part in parts):
        return (text,)
    return tuple(parts)


def _plain_wording(text: str) -> str:
    """Return text stripped to its letters and digits, so case and punctuation do not distinguish it."""
    unmarked = "".join(ch for ch in unicodedata.normalize("NFD", text) if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]", "", unmarked.casefold())


def _abbreviated_wording(text: str) -> str:
    """Return a wording without the words AEAT drops when it shortens a label.

    An official label is written out in one edition and abbreviated in the
    next, losing its prepositions and articles: ``IVA deducible en
    importaciones de bienes corrientes`` becomes ``IVA deducible importaciones
    bienes corrientes``. The two state one thing, so they may share one
    rendering; a difference in the remaining words may not.
    """
    unmarked = "".join(ch for ch in unicodedata.normalize("NFD", text) if not unicodedata.combining(ch))
    words = (match.group() for match in re.finditer(r"[a-z0-9+]+", unmarked.casefold()))
    return " ".join(word for word in words if word not in _SPANISH_FUNCTION_WORDS)


def _is_derived_help(key: str, value: str) -> bool:
    return key.endswith(".help") and any(pattern.match(value) for pattern in _DERIVED_HELP)


def _collect_spelled_content_numbers(text: str, found: Counter[str]) -> None:
    """Collect spelled content numbers."""
    for word in _WORD_TOKEN.findall(text):
        plain_word = word.casefold()
        number = _SPELLED_NUMBERS.get(plain_word)
        if number is None:
            # Hungarian builds a compound around the numeral: two children is kétgyermekes.
            number = next(
                (value for numeral, value in _SPELLED_NUMBERS.items() if plain_word.startswith(numeral)),
                None,
            )
        if number is not None:
            found[str(number)] += 1
