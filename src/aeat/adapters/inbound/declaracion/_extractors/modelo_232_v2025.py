"""Modelo 232 v2025 extractor — Operaciones vinculadas y paraísos fiscales.

Declaración informativa anual (mes 11 post-cierre, noviembre para el
ejercicio natural) que recoge operaciones con partes vinculadas por
encima de umbrales y cualquier operación con paraísos fiscales.

AEAT does NOT print numbered casilla IDs on the 232 summary — the form
is structured as three info blocks with named fields. The extractor
captures the three "Nº registros" counters that every 232 filing
prints at the end of the form via the named-field primitive.

Legal base: Orden HFP/816/2017 (BOE-A-2017-10042).
"""

from __future__ import annotations

from typing import ClassVar

from .._generic_extractor import GenericDeclaracionExtractor
from .._schema import TemplateRevision


class Modelo232V2025Extractor(GenericDeclaracionExtractor):
    """Named-field extractor for Modelo 232 (Operaciones vinculadas).

    Modelo 232 has no numbered casillas, so :attr:`casilla_ids` is empty
    and :attr:`named_field_patterns` carries one regex per "Nº
    registros" counter (operaciones vinculadas, intangibles art. 23
    LIS, operaciones con paraísos).

    Attributes:
        template_revision: Pinned to ``("232", 2025, "2025.01")``.
        casilla_ids: Empty.
        named_field_patterns: Label regex map keyed by canonical field
            name (``num_registros_vinculadas``,
            ``num_registros_intangibles``, ``num_registros_paraisos``).
    """

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="232",
        año=2025,
        revision="2025.01",
    )
    casilla_ids: ClassVar[tuple[str, ...]] = ()
    # Three "Nº registros" counters — one per info block (operaciones
    # vinculadas, intangibles art. 23 LIS, operaciones con paraísos).
    # line-anchored (?m)^. Each pattern matches on a single
    # line that mentions BOTH the block keyword AND an integer count,
    # in either order. A single outer capture group preserves
    # apply_label_regex's group(1) contract. Caveat: this regex was
    # derived from the BOE Orden structure (Orden HFP/816/2017) without
    # a real 232 PDF sample — tighten to AEAT's printed literals once
    # an L2 fixture is sourced.
    # Label-first ordering only (AEAT 232 summary always prints "Block
    # name ... count"). One capture group preserves the apply_label_regex
    # group(1) contract.
    named_field_patterns: ClassVar[dict[str, str]] = {
        "num_registros_vinculadas": r"(?m)^[^\n]*?vinculadas[^\n]*?(\d+)",
        "num_registros_intangibles": r"(?m)^[^\n]*?intangibles[^\n]*?(\d+)",
        "num_registros_paraisos": r"(?m)^[^\n]*?para[ií]sos[^\n]*?(\d+)",
    }


__all__ = ["Modelo232V2025Extractor"]
