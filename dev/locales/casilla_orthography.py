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

from dev._paths import REPO_ROOT

from ._spelling import load_dictionaries

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping

    from .modelo_casilla_catalogue import Values

__all__ = [
    "REVIEWED_SPANISH_TERMS",
    "REVIEWED_UNACCENTED_WORDS",
    "SpanishLeftover",
    "UnaccentedWord",
    "spanish_leftovers",
    "unaccented_words",
]

#: Per locale, the diacritic each plain letter may have lost.
_RESTORABLE: Final[dict[str, dict[str, str]]] = {
    "es": {"a": "á", "e": "é", "i": "í", "o": "ó", "u": "úü", "n": "ñ"},
    "ca": {"a": "à", "e": "éè", "i": "íï", "o": "óò", "u": "úü", "c": "ç"},
    "hu": {"a": "á", "e": "é", "i": "í", "o": "óöő", "u": "úüű"},
}
#: Translations quote Spanish form terms and English loanwords; the Spanish source quotes neither.
_FOREIGN_DICTIONARIES: Final[dict[str, tuple[str, ...]]] = {"es": (), "ca": ("en", "es"), "hu": ("en", "es")}
_DIACRITICS: Final = frozenset("".join(chars for table in _RESTORABLE.values() for chars in table.values()))
_WORD: Final = re.compile(r"[^\W\d_]+")
#: Registry identifiers quoted in help text, and words cut short by an ellipsis, are not prose.
_NOT_PROSE: Final = re.compile(r"[\w-]+(?:\.[\w-]+)+|\b[a-z]\d+(?:-[\w]+)+|\w+(?=\.\.\.|…)")
_MIN_LENGTH: Final = 4
_MAX_RESTORED: Final = 3

#: Words a review found correct as stored, per locale.
REVIEWED_UNACCENTED_WORDS: Final[dict[str, frozenset[str]]] = {
    # English product text and the abbreviation "impon." of "imponible";
    # "super" only occurs bound in the official rate name "super-reducido".
    # "inter vivos" is Latin, and "bitcoin" is the asset name.
    # Casilla text plus the interface domains: Latin and asset names, and words that
    # are transport tokens, field ids or English terms rather than Spanish prose.
    "es": frozenset(
        {
            "Coin",
            "Comic",
            "Console",
            "Name",
            "bitcoin",
            "codigo",
            "domiciliacion",
            "economica",
            "impon",
            "inter",
            "modificacion",
            "name",
            "operacion",
            "pais",
            "prestacion",
            "razon",
            "record",
            "records",
            "retencion",
            "revision",
            "super",
            "value",
            "vehiculo",
        }
    ),
    # Proper names (Sorolla, Illes Balears, Tokio) and correct inflections:
    # "sorok" (rows), "egyenleget" (accusative), "nekik" (to them).
    "hu": frozenset(
        {
            "Alkulcs",
            "Illes",
            "Ollama",
            "Sorok",
            "Sorolla",
            "Tokio",
            "adatsorokat",
            "egyenleget",
            "forfait",
            "konyvelom",
            "neked",
            "nekik",
            "nyelven",
            "nyelvet",
            "operacion",
            "razon",
            "rendszeren",
            "retencion",
            "retmar",
            "sorok",
            "sorokat",
            "sorokhoz",
            "soron",
            "szektorokat",
            "szektorokban",
            "szkriptel",
            "szkriptelt",
            "variacion",
        }
    ),
    # Catalan: an identifier fragment, a CLI example field, and an indicative verb form.
    "ca": frozenset({"economica", "oblides", "pais"}),
}


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
        found: set[str] = {base} if base != word and known(base) else set()
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
        foreign = [dictionaries[code] for code in _FOREIGN_DICTIONARIES[locale]]
        accepted = reviewed.get(locale, frozenset())
        verdicts: dict[str, tuple[str, ...]] = {}
        for key, value in sorted(values.get(locale, {}).items()):
            if value is None:
                continue
            prose = _NOT_PROSE.sub(" ", _CODE_SPAN.sub(" ", value))
            for word in sorted(set(_WORD.findall(prose))):
                if len(word) < _MIN_LENGTH or word.isupper() or word in accepted or _DIACRITICS & set(word.lower()):
                    continue
                if word not in verdicts:
                    plain = dictionary.lookup(word) or any(other.lookup(word) for other in foreign)
                    verdicts[word] = () if plain else _restorations(word, table, dictionary.lookup)
                if verdicts[word]:
                    yield UnaccentedWord(locale, key, word, verdicts[word])


#: Spanish tax vocabulary every locale keeps untranslated, and registry identifier stems.
_KEPT_SPANISH: Final = frozenset({"modelo", "modelos", "contraparte", "importe"})
#: Per locale, Spanish words a translation keeps on purpose: Latin ("inter vivos"), the
#: names of official programmes and deductions, registry and form field identifiers, and
#: terms the product states in Spanish everywhere ("perceptor", "recargo de equivalencia").
REVIEWED_SPANISH_TERMS: Final[dict[str, frozenset[str]]] = {
    "en": frozenset(
        {
            "deportivo",
            "ejercicio",
            "equivalencia",
            "favor",
            "perceptor",
            "periodo",
            "rata",
            "recargo",
            "tecnológica",
            "tipo",
            "vivos",
        }
    ),
    "ca": frozenset(
        {
            "batea",
            "cross",
            "deportivo",
            "ejercicio",
            "holding",
            "liar",
            "memoria",
            "operación",
            "periodo",
            "tecnológica",
            "tipo",
            "vinculación",
            "vivos",
        }
    ),
    "hu": frozenset(
        {
            "deportivo",
            "ejercicio",
            "foral",
            "interno",
            "periodo",
            "tecnológica",
            "tipo",
            "vinculada",
            "vivos",
        }
    ),
}
_QUOTED: Final = re.compile(r"«[^»]*»|\"[^\"]*\"|“[^”]*”|„[^”]*”|\([^)]*\)")
#: Code spans and interpolation the interface domains carry; the casilla surface has none.
_CODE_SPAN: Final = re.compile(r"`[^`]*`|%\{[^}]*\}|\{[^}]*\}")
#: What a parenthesis holds when it is not prose: a legal citation, a form or an acronym.
_CITED: Final = re.compile(r"art|ley|lis|liva|rd|da|dt|mod|cap|tit|apartado|decreto", re.IGNORECASE)
#: Two words of four letters or more make a parenthesis prose rather than a reference.
_PARENTHESISED_PROSE: Final = re.compile(r"[^\W\d_]{4,}", re.UNICODE)


def _blank_unless_prose(match: re.Match[str]) -> str:
    """Keep a parenthesis or quotation for judgement only when it states prose.

    A quotation carries an official name and a parenthesis usually carries a
    citation, a form number or an acronym, none of which a locale translates.
    A parenthesis that states words of its own is ordinary text and is read
    like the rest of the label, so Spanish cannot hide inside it.
    """
    group = match.group()
    if not group.startswith("("):
        return " "
    words = _PARENTHESISED_PROSE.findall(group)
    if len(words) < 2 or _CITED.fullmatch(words[0]):
        return " "
    return group


_TRANSLATED_LOCALES: Final = ("en", "ca", "hu")
_MIN_LEFTOVERS: Final = 1
_MIN_VERBATIM_RUN: Final = 3


@dataclass(frozen=True)
class SpanishLeftover:
    """A translation still carrying untranslated Spanish words outside quotations."""

    locale: str
    key: str
    words: tuple[str, ...]


def _verbatim_runs(text: str, sources: frozenset[str]) -> str:
    """Blank every capitalised or numbered run of words the translation copies verbatim from its Spanish source.

    An official Spanish name (a programme, a deduction, a body) is carried
    untranslated on purpose; a glossary pass instead interleaves single words.
    """
    words = text.split()
    kept = [True] * len(words)
    source_texts = [f" {' '.join(source.split())} " for source in sources]
    start = 0
    while start < len(words):
        end = start
        if words[start][:1].isupper() or words[start][:1].isdigit():
            while end < len(words) and any(
                f" {' '.join(words[start : end + 1])} " in source for source in source_texts
            ):
                end += 1
        if end - start >= _MIN_VERBATIM_RUN:
            kept[start:end] = [False] * (end - start)
            start = end
        else:
            start += 1
    return " ".join(word for word, keep in zip(words, kept, strict=True) if keep)


def spanish_leftovers(
    values: Values,
    sources: Mapping[str, Mapping[str, frozenset[str]]],
) -> Iterator[SpanishLeftover]:
    """Yield translations with Spanish words the target dictionary rejects, in key order.

    ``sources[locale][key]`` holds the Spanish texts the key renders. Only
    lowercase words count, quoted or parenthesised text is skipped, and so is a
    capitalised run copied verbatim from the source, because official names are
    carried untranslated.
    """
    dictionaries = load_dictionaries(REPO_ROOT)
    spanish = dictionaries["es"]
    for locale in _TRANSLATED_LOCALES:
        target = dictionaries[locale]
        kept = REVIEWED_SPANISH_TERMS.get(locale, frozenset())
        verdicts: dict[str, bool] = {}
        for key, value in sorted(values.get(locale, {}).items()):
            if value is None:
                continue
            leftovers: list[str] = []
            judged = _QUOTED.sub(_blank_unless_prose, value)
            prose = _verbatim_runs(judged, sources.get(locale, {}).get(key, frozenset()))
            for word in _WORD.findall(_NOT_PROSE.sub(" ", prose)):
                if len(word) < _MIN_LENGTH or not word.islower() or word in _KEPT_SPANISH or word in kept:
                    continue
                if word not in verdicts:
                    verdicts[word] = bool(spanish.lookup(word)) and not target.lookup(word)
                if verdicts[word]:
                    leftovers.append(word)
            if len(leftovers) >= _MIN_LEFTOVERS:
                yield SpanishLeftover(locale, key, tuple(leftovers))
