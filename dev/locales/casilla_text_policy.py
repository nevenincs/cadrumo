"""Existing casilla wording, content-token, and disclosure policy."""

from __future__ import annotations

import re
from typing import Final

SOURCE_LOCALE: Final = "es"


_FIELDS: Final = ("label", "help")


#: Help renderings generated from the label; they state nothing the label does not.
_DERIVED_HELP: Final = (
    re.compile(r"^Indique o revise «.*» para completar esta autoliquidación\.$", re.S),
    re.compile(r"^Consulte la información correspondiente a la casilla: .*$", re.S),
    re.compile(r"^Información fiscal sobre .*de la casilla .*$", re.S),
    re.compile(r"^Información de la casilla\b.*$", re.S),
    re.compile(r"^Dato del modelo \S+, ejercicio \S+.*$", re.S),
)


_REVISION_SCOPED: Final = re.compile(r"^modelo\.schema\.(?P<modelo>[^.]+)\.revision\.(?P<revision>[^.]+)\.")


#: Scaffold renderings standing in for a label that was never authored. Help text may
#: legitimately open with its box number, so only labels are judged.
_PLACEHOLDER: Final = re.compile(
    r"^(?:Casilla|Casella|Box)\s+\S+:\s|^Casella . informaci"
    r"|^(?:Casilla|Casella|Box)\b[^—]{0,40}—|^[^—]{0,40}\brovat\s+—"
    r"|^(?:Informació fiscal de la casella|Tax information for this field|Az űrlap adóadata)\.?$",
    re.IGNORECASE,
)


#: A value that a length limit cut mid-text and closed with an ellipsis.
_TRUNCATED: Final = re.compile(r"\S\s?(?:\.\.\.|…)\s*$")


#: "N por 100" and "N por ciento" state the rate "N%"; the words carry no content.
_PERCENT_WORDS: Final = re.compile(r"\s*por\s*(?:100|ciento)(?![0-9])", re.IGNORECASE)


#: An ordinal a translation spells out states the same number as the Spanish digit.
_SPELLED_NUMBERS: Final[dict[str, int]] = {
    # English
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
    "eleventh": 11,
    "twelfth": 12,
    # Catalan
    "primera": 1,
    "primer": 1,
    "segona": 2,
    "segon": 2,
    "tercera": 3,
    "tercer": 3,
    "quarta": 4,
    "quart": 4,
    "cinquena": 5,
    "cinquè": 5,
    "sisena": 6,
    "sisè": 6,
    "setena": 7,
    "setè": 7,
    "vuitena": 8,
    "vuitè": 8,
    "novena": 9,
    "novè": 9,
    "desena": 10,
    "desè": 10,
    # Hungarian
    "első": 1,
    "második": 2,
    "harmadik": 3,
    "negyedik": 4,
    "ötödik": 5,
    "hatodik": 6,
    "hetedik": 7,
    "nyolcadik": 8,
    "kilencedik": 9,
    "tizedik": 10,
    # Cardinals a translation writes as words for a count the Spanish gives as a digit.
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "un": 1,
    "dos": 2,
    "tres": 3,
    "quatre": 4,
    "cinc": 5,
    "sis": 6,
    "set": 7,
    "vuit": 8,
    "nou": 9,
    "deu": 10,
    "egy": 1,
    "kettő": 2,
    "két": 2,
    "három": 3,
    "négy": 4,
    "öt": 5,
    "hat": 6,
    "hét": 7,
    "nyolc": 8,
    "kilenc": 9,
    "tíz": 10,
    "tizenegy": 11,
    "tizenkettő": 12,
    "tizenhárom": 13,
    "tizennégy": 14,
    "tizenöt": 15,
    "tizenhat": 16,
    "tizenhét": 17,
    "tizennyolc": 18,
    "tizenkilenc": 19,
}


_WORD_TOKEN: Final = re.compile(r"[^\W\d_]+")


#: ">=" and "<=" write the comparison the Spanish sets with the symbol itself.
_ASCII_COMPARISON: Final[dict[str, str]] = {">=": "≥", "<=": "≤"}


#: A thousands separator is typography: 60.000, 60,000 and 60 000 state one amount.
_THOUSANDS: Final = re.compile(r"\b\d{1,3}(?:[.,\u00a0 ]\d{3})+\b")


#: The legal content a label states: box references, amounts and comparison symbols.
_CONTENT_TOKEN: Final = re.compile(r"\[[0-9][^\]]{0,11}\]|\d+|[≤≥]")


#: Repeated spaces, or whitespace opening or closing a value; line breaks are authored.
_IRREGULAR_WHITESPACE: Final = re.compile(r"[ \t]{2,}|^\s|\s$")


#: The words an official label loses when AEAT shortens it, which carry no legal meaning.
_SPANISH_FUNCTION_WORDS: Final[frozenset[str]] = frozenset(
    [
        "a",
        "al",
        "con",
        "de",
        "del",
        "el",
        "en",
        "la",
        "las",
        "los",
        "para",
        "por",
        "que",
        "se",
        "su",
        "sus",
        "un",
        "una",
        "y",
    ]
)


#: The separators AEAT composes a long label from: heading, regime, year, state of the amount.
#: A dash also subtracts one box from another, which :func:`_segments` keeps whole, and a full
#: stop also abbreviates a word, so a sentence break is read only between a word and a capital.
_SEGMENT: Final = re.compile(r"\s+-\s+|(?<=[^\W\dA-Z_])\.\s+(?=[A-ZÁÀÂÄÉÈÊËÍÏÎÓÒÔÖŐÚÙÛÜŰÑÇ])")


#: What tells a composed segment from an operand: a segment states words, an operand a box.
_SEGMENT_PROSE: Final = re.compile(r"[^\W\d_]{3,}")


#: Spanish texts whose official record design is itself cut short with an ellipsis;
#: the catalogue mirrors the source, and a translation of them may end the same way.
SOURCE_TRUNCATED_SPANISH: Final[frozenset[str]] = frozenset(
    {
        # Modelo 714 design, box [35].
        "Liquidación - Límite cuota íntegra - Parte cuotas íntegras IRPF, saldo positivo ganancias y pérdidas "
        "patrimoniales...",
        # Modelo 100 box [1908]: the design names a different annex in each edition
        # (B.8, B.9, B.11), so the completed text would differ between editions that
        # share this key. The registry refuses that divergence until a casilla
        # continuity evolution declares it, so the shared text stays cut short.
        "Por inversión en adquisición de acciones y participaciones sociales como consecuencia de acuerdos de "
        "constitución de sociedades o ampliación de capital en las sociedades mercantiles (importe de la ...",
    }
)


#: Per locale, the marks a word-by-word glossary pass leaves: Hungarian suffix
#: alternations standing alone, and Spanish function words left untranslated.
_GLOSSARY_ARTIFACT: Final[dict[str, re.Pattern[str]]] = {
    "hu": re.compile(
        r"-(?:ban/-ben|nak/-nek|ra/-re|ról/-ről|ba/-be|val/-vel|tól/-től|hoz/-hez|ból/-ből|ként)\b"
        r"|\ba\(z\) [a-záéíóöőúüű]+ -|\b(?:Aplicado|esta)\b"
    ),
    "en": re.compile(r"\b(?:Aplicado|esta|otros|otras|excepto|según|cuyo|cuya)\b"),
    "ca": re.compile(r"\b(?:Aplicado|esta|otros|otras|excepto|según|cuyo|cuya)\b"),
}


_EDITION_TEXT: Final = re.compile(r"^modelo\.schema\.(?P<modelo>[^.]+)\.revision\.[^.]+\.field\.label$")


#: Scaffold renderings standing in for revision or construct text that was never authored.
_EDITION_TEXT_PLACEHOLDER: Final = re.compile(r"^(?:Casilla|Casella)\s*—|—\s*(?:tax|informaci|adóügyi)")
