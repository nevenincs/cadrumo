"""Diacritic-loss detection for the delta-keyed Modelo casilla catalogue.

Casilla labels were first captured from sources that folded accents away
("anios", "regimen", "szemely"). The generic spelling signal does not read these
leaves, because their presence is governed by delta keying rather than by key
parity. This check reads every stored value and reports each word the pinned
Hunspell dictionary rejects while accepting a form with diacritics restored.

A restoration is a candidate, not a verdict: a word can be a Spanish name inside
a translation or a correct unaccented inflection. Reviewed false positives are
listed in :data:`REVIEWED_UNACCENTED_WORDS`, keyed by locale and exact word.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import combinations, product
from typing import TYPE_CHECKING, Final

from ._paths import REPO_ROOT
from ._spelling import load_dictionaries

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping

    from .modelo_casilla_catalogue import Values

__all__ = ["REVIEWED_UNACCENTED_WORDS", "UnaccentedWord", "unaccented_words"]

#: Per locale, the diacritic each plain letter may have lost.
_RESTORABLE: Final[dict[str, dict[str, str]]] = {
    "es": {"a": "á", "e": "é", "i": "í", "o": "ó", "u": "úü", "n": "ñ"},
    "ca": {"a": "à", "e": "éè", "i": "íï", "o": "óò", "u": "úü", "c": "ç"},
    "hu": {"a": "á", "e": "é", "i": "í", "o": "óöő", "u": "úüű"},
}
_FOREIGN_DICTIONARIES: Final = ("en", "es")
_DIACRITICS: Final = frozenset("".join(chars for table in _RESTORABLE.values() for chars in table.values()))
_WORD: Final = re.compile(r"[^\W\d_]+")
_MIN_LENGTH: Final = 4
_MAX_RESTORED: Final = 3

#: Words a review found correct as stored, per locale.
REVIEWED_UNACCENTED_WORDS: Final[dict[str, frozenset[str]]] = {}


@dataclass(frozen=True)
class UnaccentedWord:
    """One stored word the dictionary accepts only with diacritics restored."""

    locale: str
    key: str
    word: str
    candidates: tuple[str, ...]


def _restorations(word: str, table: Mapping[str, str], known: Callable[[str], bool]) -> tuple[str, ...]:
    bases = [word]
    if "n" in table and "ni" in word:
        bases.append(word.replace("ni", "ñ"))
    for base in bases:
        found = {base} if base != word and known(base) else set()
        positions = [index for index, char in enumerate(base) if char.lower() in table]
        for size in range(1, _MAX_RESTORED + 1):
            for chosen in combinations(positions, size):
                for marks in product(*(table[base[index].lower()] for index in chosen)):
                    letters = list(base)
                    for index, mark in zip(chosen, marks, strict=True):
                        letters[index] = mark.upper() if base[index].isupper() else mark
                    candidate = "".join(letters)
                    if known(candidate):
                        found.add(candidate)
        if found:
            return tuple(sorted(found))
    return ()


def unaccented_words(
    values: Values,
    reviewed: Mapping[str, frozenset[str]] = REVIEWED_UNACCENTED_WORDS,
) -> Iterator[UnaccentedWord]:
    """Yield every stored casilla word that has lost its diacritics, in key order."""
    dictionaries = load_dictionaries(REPO_ROOT)
    for locale, table in _RESTORABLE.items():
        dictionary = dictionaries[locale]
        foreign = [dictionaries[code] for code in _FOREIGN_DICTIONARIES if code != locale]
        accepted = reviewed.get(locale, frozenset())
        verdicts: dict[str, tuple[str, ...]] = {}
        for key, value in sorted(values.get(locale, {}).items()):
            if value is None:
                continue
            for word in sorted(set(_WORD.findall(value))):
                if len(word) < _MIN_LENGTH or word.isupper() or word in accepted or _DIACRITICS & set(word.lower()):
                    continue
                if word not in verdicts:
                    plain = dictionary.lookup(word) or any(other.lookup(word) for other in foreign)
                    verdicts[word] = () if plain else _restorations(word, table, dictionary.lookup)
                if verdicts[word]:
                    yield UnaccentedWord(locale, key, word, verdicts[word])
