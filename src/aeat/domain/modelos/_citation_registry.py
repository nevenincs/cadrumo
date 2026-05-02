"""Blocklist of known-bad Spanish-tax legal citations.

Recurring review surfaced citation errors where a
``(source, article)`` pair was attributed the wrong role — e.g.,
``LIRPF art. 103`` cited for "cuota diferencial" when art. 103 is
actually "Liquidaciones provisionales". Each miscite shipped through
code review because :attr:`aeat.domain.modelos._citations.LegalCitation.quoted_text_es`
was internally self-consistent with the wrong article number; human
review caught the error only on a later external verification pass.

This module exposes :data:`_KNOWN_BAD_CITATIONS`, a closed table of
``(source, article, role-substring)`` triples that have been flagged
in the past, and :func:`find_known_bad`, the lookup helper invoked by
:meth:`aeat.domain.modelos._citations.LegalCitation._reject_known_bad_citations`
at construction time. A complementary positive-registry half
(enforcing that every ``(source, article)`` pair maps to a verified
BOE plain-text title) is intentionally deferred: adding it requires
pinning a title for every existing citation, which is itself subject
to the same error mode.

To extend the blocklist, append a new :class:`KnownBadCitation` row
to :data:`_KNOWN_BAD_CITATIONS`. Every row names:

- ``source``: the :class:`aeat.domain.modelos._categories.LegalCitationSource`
  enum value.
- ``article``: the article identifier as a string (matches
  :attr:`aeat.domain.modelos._citations.LegalCitation.article` verbatim).
- ``role_substring_es``: a lowercase Spanish word/phrase that
  characterises the wrong role-of-the-article. The validator matches
  if this substring appears in ``quoted_text_es.lower()``. Keep the
  substring narrow enough that legitimate historical references don't
  false-positive — prefer the role name alone, not the article number.
- ``audit_wave``: free-form provenance marker for the audit trail.
- ``reason``: prose explanation that points the reader at the correct
  article so the error can be fixed in place.
"""

from __future__ import annotations

import unicodedata
from typing import NamedTuple

from ._categories import LegalCitationSource


def _fold_diacritics(text: str) -> str:
    """Lowercase and strip diacritics for accent-insensitive matching.

    pdfplumber output and hand-typed ``quoted_text_es`` strings
    routinely drop diacritics; without this fold, a string like
    ``"cuota liquida"`` (no accent) would defeat a blocklist entry
    keyed on ``"cuota líquida"``. The function NFKD-decomposes the
    text into base + combining-diacritic pairs, then ASCII-encodes to
    drop the combining marks. The transformation is monotonic on
    existing substring matches — it never introduces false positives.

    Args:
        text: The string to fold.

    Returns:
        The lowercased, diacritic-stripped, ASCII-encoded form of
        ``text``.
    """
    return unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode("ascii")


class KnownBadCitation(NamedTuple):
    """One entry in the citation-error blocklist.

    Attributes:
        source: The :class:`aeat.domain.modelos._categories.LegalCitationSource`
            this entry blocks.
        article: The article identifier this entry blocks (matches
            :attr:`aeat.domain.modelos._citations.LegalCitation.article`
            verbatim).
        role_substring_es: Lowercase Spanish substring whose presence
            in ``quoted_text_es`` indicates the wrong role-of-the-article.
        audit_wave: Free-form provenance marker recording the audit
            that first flagged the miscite.
        reason: Prose explanation pointing the reader at the correct
            article so the offending citation can be fixed in place.
    """

    source: LegalCitationSource
    article: str
    role_substring_es: str
    audit_wave: str
    reason: str


_KNOWN_BAD_CITATIONS: tuple[KnownBadCitation, ...] = (
    KnownBadCitation(
        LegalCitationSource.LEY,
        "103",
        "cuota diferencial",
        " / corrected ",
        "LIRPF art. 103 is 'Liquidaciones provisionales' (AEAT "
        "administrative power); cuota diferencial lives in art. 79 "
        "with the pagos-a-cuenta subtraction hooking through art. 99.",
    ),
    KnownBadCitation(
        LegalCitationSource.LEY,
        "77",
        "cuota íntegra autonómica",
        " / corrected ",
        "LIRPF art. 77 is 'Cuota líquida autonómica total' "
        "(post-deduction); cuota íntegra autonómica is art. 73 with "
        "the tarifa in art. 74.",
    ),
    KnownBadCitation(
        LegalCitationSource.LEY,
        "67",
        "cuota íntegra estatal",
        " / corrected ",
        "LIRPF art. 67 is 'Cuota líquida estatal' (post-deduction); cuota íntegra estatal is art. 62.",
    ),
    KnownBadCitation(
        LegalCitationSource.LEY,
        "79",
        "cuota líquida",
        " / corrected ",
        "LIRPF art. 79 is 'Cuota diferencial'; cuota líquida is the "
        "combination of art. 67 (estatal) + art. 77 (autonómica).",
    ),
    KnownBadCitation(
        LegalCitationSource.LEY,
        "125",
        "cuota líquida",
        " / corrected ",
        "LIS art. 125 is 'Autoliquidación e ingreso de la deuda "
        "tributaria' (procedural); cuota líquida definition lives in "
        "LIS art. 30.",
    ),
    KnownBadCitation(
        LegalCitationSource.LEY,
        "125",
        "líquido a ingresar",
        "stream 4 / corrected ",
        "LIS art. 125 is procedural (declaración + ingreso + "
        "payment-in-kind via Patrimonio Histórico); the 'líquido a "
        "ingresar o devolver' arithmetic of Modelo 200 casilla 00611/"
        "00621 maps to LIS arts. 30 (cuota íntegra/líquida), 39.2 "
        "(abono deducciones I+D+i), and 125.3 narrowly for "
        "'incremento por pérdida de beneficios fiscales' only.",
    ),
    KnownBadCitation(
        LegalCitationSource.LEY,
        "71",
        "resumen anual",
        "stream 2 / corrected ",
        "LIVA (Ley 37/1992) art. 71 is 'Lugar de realización de las "
        "prestaciones de servicios' (place-of-supply rules). The "
        "resumen-anual obligation (Modelo 390) lives in RIVA "
        "(RD 1624/1992) art. 71.7 — different source type (REGLAMENTO).",
    ),
    KnownBadCitation(
        LegalCitationSource.REGLAMENTO,
        "100.3.a",
        "arrendamientos",
        " / corrected ",
        "RIRPF art. 100 has NO sub-letter structure in the BOE "
        "consolidated text (BOE-A-2007-6820). The 19% rate on "
        "arrendamientos urbanos lives in art. 100.1; art. 100.2 is "
        "the Ceuta/Melilla 60% reduction.",
    ),
    KnownBadCitation(
        LegalCitationSource.REGLAMENTO,
        "100.3.c",
        "ganancias",
        " / corrected ",
        "RIRPF art. 100 has NO sub-letter structure. The 19% rate on "
        "rendimientos gravados lives in art. 100.1; the pagos-a-cuenta "
        "obligation hook is art. 99.",
    ),
    KnownBadCitation(
        LegalCitationSource.REGLAMENTO,
        "105.1",
        "premios",
        " / corrected ",
        "RIRPF art. 105 covers 'Retenciones sobre las transmisiones "
        "o reembolsos de acciones y participaciones de IIC' — NOT "
        "premios en metálico. The 19% rate on premios derives from "
        "LIRPF art. 101.7 implemented via RIRPF art. 99.",
    ),
    KnownBadCitation(
        LegalCitationSource.REGLAMENTO,
        "110.2",
        "agrícolas",
        " / corrected (tests) + (ruleset)",
        "RIRPF art. 110.2 is the 60% reduction clause on the quarterly "
        "rendimiento. The 2% rate on actividades agrícolas/ganaderas/"
        "forestales/pesqueras lives in art. 110.1.c.",
    ),
    KnownBadCitation(
        LegalCitationSource.REGLAMENTO,
        "110.4",
        "módulos",
        " / corrected (tests) + (ruleset)",
        "RIRPF art. 110.4 is the minoración clause for low-income "
        "autónomos. The 4/3/2% rate on actividades en estimación "
        "objetiva (módulos) lives in art. 110.1.b.",
    ),
    KnownBadCitation(
        LegalCitationSource.REGLAMENTO,
        "100",
        "capital mobiliario",
        "stream 1 / corrected ",
        "RIRPF art. 100 is 'Importe de las retenciones sobre "
        "rendimientos del arrendamiento o subarrendamiento de bienes "
        "inmuebles urbanos' — arrendamientos ONLY (art. 100.1 rate "
        "19%, art. 100.2 Ceuta/Melilla reduction). Capital mobiliario "
        "retención lives in RIRPF art. 90.",
    ),
    KnownBadCitation(
        LegalCitationSource.LEY,
        "66",
        "cuota íntegra general",
        "stream 1 / corrected ",
        "LIRPF art. 66 is 'Tipos de gravamen del ahorro' (base del "
        "ahorro tarifa) — narrow scope. The entry point for the "
        "general cuota íntegra chapter is LIRPF art. 62 (Cuota "
        "íntegra estatal) + art. 73 (Cuota íntegra autonómica). "
        "Citations describing art. 66 as the start of liquidación or "
        "the general-base cuota íntegra confuse savings-tarifa with "
        "general-base tarifa.",
    ),
)


def find_known_bad(source: LegalCitationSource, article: str, quoted_text_es: str) -> KnownBadCitation | None:
    """Return the matching :class:`KnownBadCitation`, or ``None``.

    A match requires exact equality on ``source`` and ``article`` and
    that the blocklisted ``role_substring_es`` appears as a substring
    of ``quoted_text_es`` (after diacritic folding). The role-substring
    gate prevents false positives on citations that use the same
    article for a different, correctly-attributed role: e.g., a future
    citation of ``LIRPF art. 67`` for the actually-correct "cuota
    líquida estatal" role won't trip the blocklist entry keyed on
    "cuota íntegra estatal" because the wrong role-phrase isn't
    present.

    Args:
        source: The citation's :class:`aeat.domain.modelos._categories.LegalCitationSource`.
        article: The article identifier under inspection.
        quoted_text_es: The candidate Spanish quotation to scan for
            blocklisted role substrings.

    Returns:
        The matching :class:`KnownBadCitation` row, or ``None`` if the
        triple is not blocklisted.
    """
    folded = _fold_diacritics(quoted_text_es)
    for entry in _KNOWN_BAD_CITATIONS:
        if entry.source == source and entry.article == article and _fold_diacritics(entry.role_substring_es) in folded:
            return entry
    return None


__all__ = ["KnownBadCitation", "find_known_bad"]
