"""Known-bad citation blocklist (EPIC #305 wave 69).

Six consecutive audit waves (59c, 61a, 63a, 65a, 67a, 68) surfaced
Spanish-tax citation errors where a ``(source, article)`` pair was
attributed the wrong role — e.g., `LIRPF art. 103` cited for "cuota
diferencial" (art. 103 is actually "Liquidaciones provisionales").
Each miscite shipped through code review because `quoted_text_es`
was internally self-consistent with the wrong article number; human
review caught the error only on a later external verification pass.

This module implements the blocklist half of the wave-68 stream-3
recommendation: an import-time ``ValueError`` for any
``(source, article, role-substring)`` triple matching a prior miscite.
The complementary positive-registry half (enforcing that every
``(source, article)`` pair maps to a verified BOE plain-text title)
is deferred as a larger structural change tracked under EPIC #305 —
adding it requires pinning a title for every existing citation,
which is itself subject to the same error mode.

## How to extend

When a future audit surfaces a new citation error, add one row to
``_KNOWN_BAD_CITATIONS``. Every row names:

- ``source``: the ``LegalCitationSource`` enum value.
- ``article``: the article identifier as a string (matches
  ``LegalCitation.article`` verbatim).
- ``role_substring_es``: a lowercase Spanish word/phrase that
  characterises the wrong role-of-the-article. The validator matches
  if this substring appears in ``quoted_text_es.lower()``. Keep the
  substring narrow enough that legitimate historical references
  (e.g., "wave 63a corrected the art. 103 / cuota diferencial miscite")
  don't false-positive — prefer the role name alone, not the article
  number.
- ``audit_wave``: the first wave that flagged the miscite, for
  audit-trail provenance.

## References

- ``.vault/audit/2026-04-22-real-pdf-import-wave-64-exhaustive-audit.md`` (5 miscites)
- ``.vault/audit/2026-04-22-real-pdf-import-wave-66-exhaustive-audit.md`` (4 more miscites)
- ``.vault/audit/2026-04-22-real-pdf-import-wave-68-exhaustive-audit.md`` (RIRPF 100.3.a)
- Wave 68 stream 3 recommendation for a hybrid registry+blocklist.
"""

from __future__ import annotations

import unicodedata
from typing import NamedTuple

from ._categories import LegalCitationSource


def _fold_diacritics(text: str) -> str:
    """Normalise a string for accent-insensitive substring matching.

    Wave 73b L2 closure (wave 70 stream 1 caution): pdfplumber and
    hand-typed ``quoted_text_es`` routinely drop diacritics. Without
    this fold, ``"cuota liquida"`` (no accent) would defeat the
    blocklist entry keyed on ``"cuota líquida"``. ``unicodedata.
    normalize("NFKD", ...)`` decomposes accented characters into a
    base + combining-diacritic pair; ASCII-encoding drops the
    diacritics. Monotonic on existing matches — no false-positives
    added.
    """
    return unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode("ascii")


class KnownBadCitation(NamedTuple):
    """One entry in the citation-error blocklist."""

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
        "wave 59c / corrected wave 63a",
        "LIRPF art. 103 is 'Liquidaciones provisionales' (AEAT "
        "administrative power); cuota diferencial lives in art. 79 "
        "with the pagos-a-cuenta subtraction hooking through art. 99.",
    ),
    KnownBadCitation(
        LegalCitationSource.LEY,
        "77",
        "cuota íntegra autonómica",
        "wave 63a / corrected wave 65a",
        "LIRPF art. 77 is 'Cuota líquida autonómica total' "
        "(post-deduction); cuota íntegra autonómica is art. 73 with "
        "the tarifa in art. 74.",
    ),
    KnownBadCitation(
        LegalCitationSource.LEY,
        "67",
        "cuota íntegra estatal",
        "wave 65a / corrected wave 67a",
        "LIRPF art. 67 is 'Cuota líquida estatal' (post-deduction); cuota íntegra estatal is art. 62.",
    ),
    KnownBadCitation(
        LegalCitationSource.LEY,
        "79",
        "cuota líquida",
        "wave 65a / corrected wave 67a",
        "LIRPF art. 79 is 'Cuota diferencial'; cuota líquida is the "
        "combination of art. 67 (estatal) + art. 77 (autonómica).",
    ),
    KnownBadCitation(
        LegalCitationSource.LEY,
        "125",
        "cuota líquida",
        "wave 61a / corrected wave 67a",
        "LIS art. 125 is 'Autoliquidación e ingreso de la deuda "
        "tributaria' (procedural); cuota líquida definition lives in "
        "LIS art. 30.",
    ),
    KnownBadCitation(
        LegalCitationSource.LEY,
        "125",
        "líquido a ingresar",
        "wave 70 stream 4 / corrected wave 71c",
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
        "wave 70 stream 2 / corrected wave 71d",
        "LIVA (Ley 37/1992) art. 71 is 'Lugar de realización de las "
        "prestaciones de servicios' (place-of-supply rules). The "
        "resumen-anual obligation (Modelo 390) lives in RIVA "
        "(RD 1624/1992) art. 71.7 — different source type (REGLAMENTO).",
    ),
    KnownBadCitation(
        LegalCitationSource.REGLAMENTO,
        "100.3.a",
        "arrendamientos",
        "wave 29 / corrected wave 67g",
        "RIRPF art. 100 has NO sub-letter structure in the BOE "
        "consolidated text (BOE-A-2007-6820). The 19% rate on "
        "arrendamientos urbanos lives in art. 100.1; art. 100.2 is "
        "the Ceuta/Melilla 60% reduction.",
    ),
    KnownBadCitation(
        LegalCitationSource.REGLAMENTO,
        "100.3.c",
        "ganancias",
        "wave 57b / corrected wave 67a",
        "RIRPF art. 100 has NO sub-letter structure. The 19% rate on "
        "rendimientos gravados lives in art. 100.1; the pagos-a-cuenta "
        "obligation hook is art. 99.",
    ),
    KnownBadCitation(
        LegalCitationSource.REGLAMENTO,
        "105.1",
        "premios",
        "wave 57b / corrected wave 67a",
        "RIRPF art. 105 covers 'Retenciones sobre las transmisiones "
        "o reembolsos de acciones y participaciones de IIC' — NOT "
        "premios en metálico. The 19% rate on premios derives from "
        "LIRPF art. 101.7 implemented via RIRPF art. 99.",
    ),
    KnownBadCitation(
        LegalCitationSource.REGLAMENTO,
        "110.2",
        "agrícolas",
        "wave 57b / corrected wave 65a (tests) + wave 68a (ruleset)",
        "RIRPF art. 110.2 is the 60% reduction clause on the quarterly "
        "rendimiento. The 2% rate on actividades agrícolas/ganaderas/"
        "forestales/pesqueras lives in art. 110.1.c.",
    ),
    KnownBadCitation(
        LegalCitationSource.REGLAMENTO,
        "110.4",
        "módulos",
        "wave 57b / corrected wave 65a (tests) + wave 68a (ruleset)",
        "RIRPF art. 110.4 is the minoración clause for low-income "
        "autónomos. The 4/3/2% rate on actividades en estimación "
        "objetiva (módulos) lives in art. 110.1.b.",
    ),
)


def find_known_bad(source: LegalCitationSource, article: str, quoted_text_es: str) -> KnownBadCitation | None:
    """Return a :class:`KnownBadCitation` if the triple matches the blocklist.

    A match requires:
    - Exact equality on ``source`` AND ``article``.
    - The blocklisted ``role_substring_es`` appears as a substring
      of ``quoted_text_es.lower()``.

    The role-substring match prevents false positives on citations
    that use the same article for a different (correctly-attributed)
    role. E.g., if a future citation uses ``LIRPF art. 67`` for the
    actually-correct "cuota líquida estatal" role, the blocklist's
    ``"cuota íntegra estatal"`` substring won't match because the
    wrong role-phrase isn't present.
    """
    folded = _fold_diacritics(quoted_text_es)
    for entry in _KNOWN_BAD_CITATIONS:
        if entry.source == source and entry.article == article and _fold_diacritics(entry.role_substring_es) in folded:
            return entry
    return None


__all__ = ["KnownBadCitation", "find_known_bad"]
