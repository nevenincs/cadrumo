"""Modelo 193 v2025 extractor — Resumen anual retenciones capital mobiliario.

Annual summary of the monthly/quarterly Modelo 123 filings: all perceptor
lines plus the header totals. MVP targets the "Resumen de los datos
incluidos en la declaración" block at the end of the form — the three
totals that every 193 PDF prints regardless of perceptor count. Per-line
perceptor detail lands in sub-EPIC #305-Modelo-193-full.

Legal base: Orden EHA/3377/2011 (BOE-A-2011-19396).
"""

from __future__ import annotations

from typing import ClassVar

from .._generic_extractor import GenericDeclaracionExtractor
from .._schema import TemplateRevision


class Modelo193V2025Extractor(GenericDeclaracionExtractor):
    """Concrete extractor for Modelo 193 tax year 2025 (período 0A)."""

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="193",
        año=2025,
        revision="2025.01",
    )
    casilla_ids: ClassVar[tuple[str, ...]] = (
        "01",  # nº total de perceptores
        "02",  # base retenciones total
        "03",  # retenciones e ingresos a cuenta total
    )


__all__ = ["Modelo193V2025Extractor"]
