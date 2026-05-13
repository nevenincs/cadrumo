"""Known-bad Spanish-tax legal citation guardrails for registry validation."""

from __future__ import annotations

import unicodedata
from typing import Literal, NamedTuple

from ....core.i18n import Translatable as tr  # noqa: N813

CitationSource = Literal["ley", "real_decreto", "orden", "reglamento", "manual", "instruction"]


def _fold_diacritics(text: str) -> str:
    return unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode("ascii")


class KnownBadCitation(NamedTuple):
    source: CitationSource
    article: str
    role_substring: tr
    reason: str


_KNOWN_BAD_CITATIONS: tuple[KnownBadCitation, ...] = (
    KnownBadCitation(
        "ley",
        "103",
        tr("cuota diferencial"),
        "LIRPF art. 103 is 'Liquidaciones provisionales'; cuota diferencial lives in art. 79.",
    ),
    KnownBadCitation(
        "ley",
        "77",
        tr("cuota íntegra autonómica"),
        "LIRPF art. 77 is 'Cuota líquida autonómica total'; cuota íntegra autonómica is art. 73.",
    ),
    KnownBadCitation(
        "ley",
        "67",
        tr("cuota íntegra estatal"),
        "LIRPF art. 67 is 'Cuota líquida estatal'; cuota íntegra estatal is art. 62.",
    ),
    KnownBadCitation(
        "ley",
        "79",
        tr("cuota líquida"),
        "LIRPF art. 79 is 'Cuota diferencial'; cuota líquida is art. 67 plus art. 77.",
    ),
    KnownBadCitation(
        "ley",
        "125",
        tr("cuota líquida"),
        "LIS art. 125 is procedural; cuota líquida definition lives in LIS art. 30.",
    ),
    KnownBadCitation(
        "ley",
        "125",
        tr("líquido a ingresar"),
        "LIS art. 125 is procedural; Modelo 200 final amount arithmetic needs LIS arts. 30 and 39.2.",
    ),
    KnownBadCitation(
        "ley",
        "71",
        tr("resumen anual"),
        "LIVA art. 71 is place-of-supply; Modelo 390 annual-summary obligation is RIVA art. 71.7.",
    ),
    KnownBadCitation(
        "reglamento",
        "100.3.a",
        tr("arrendamientos"),
        "RIRPF art. 100 has no sub-letter structure; the 19% rate is in art. 100.1.",
    ),
    KnownBadCitation(
        "reglamento",
        "100.3.c",
        tr("ganancias"),
        "RIRPF art. 100 has no sub-letter structure; pagos-a-cuenta obligation hook is art. 99.",
    ),
    KnownBadCitation(
        "reglamento",
        "105.1",
        tr("premios"),
        "RIRPF art. 105 covers IIC transfers, not cash prizes.",
    ),
    KnownBadCitation(
        "reglamento",
        "110.2",
        tr("agrícolas"),
        "RIRPF art. 110.2 is the reduction clause; agricultural rates live in art. 110.1.c.",
    ),
    KnownBadCitation(
        "reglamento",
        "110.4",
        tr("módulos"),
        "RIRPF art. 110.4 is the low-income reduction clause; module rates live in art. 110.1.b.",
    ),
    KnownBadCitation(
        "reglamento",
        "100",
        tr("capital mobiliario"),
        "RIRPF art. 100 covers urban rentals; capital income withholding is RIRPF art. 90.",
    ),
    KnownBadCitation(
        "ley",
        "66",
        tr("cuota íntegra general"),
        "LIRPF art. 66 is the savings-base tariff; general cuota íntegra starts at arts. 62 and 73.",
    ),
)


def find_known_bad(source: CitationSource, article: str, role_text: str) -> KnownBadCitation | None:
    folded = _fold_diacritics(role_text)
    for entry in _KNOWN_BAD_CITATIONS:
        if entry.source == source and entry.article == article and _fold_diacritics(entry.role_substring) in folded:
            return entry
    return None


__all__ = ["CitationSource", "KnownBadCitation", "find_known_bad"]
