"""Modelo 349 (Operaciones intracomunitarias) extractor for tax year 2025.

Declaración recapitulativa de operaciones intracomunitarias. Monthly by
default; quarterly if the thresholds in art. 81 RIVA are not exceeded.
This extractor targets the "Resumen de la declaración" block printed at
the end of every PDF — operators count and total importe, split between
ordinary operations and rectifications. Per-operador detail lines are out
of scope.

Legal base: Orden EHA/769/2010 (BOE-A-2010-5098).
"""

from __future__ import annotations

from typing import ClassVar

from .._generic_extractor import GenericDeclaracionExtractor
from .._schema import TemplateRevision


class Modelo349V2025Extractor(GenericDeclaracionExtractor):
    """Concrete extractor for Modelo 349 tax year 2025.

    Captures the four summary casillas printed in the "Resumen de la
    declaración" block via the shared
    :class:`aeat.adapters.inbound.declaracion._generic_extractor.GenericDeclaracionExtractor`.

    Attributes:
        template_revision: Identifier (modelo ``"349"``, año ``2025``,
            revision ``"2025.01"``).
        casilla_ids: Ordered tuple of supported casillas — 01 (nº total
            operadores intracomunitarios), 02 (importe total operaciones),
            03 (nº operadores con rectificaciones), 04 (importe
            rectificaciones).
    """

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="349",
        año=2025,
        revision="2025.01",
    )
    casilla_ids: ClassVar[tuple[str, ...]] = (
        "01",  # nº total operadores intracomunitarios
        "02",  # importe total operaciones
        "03",  # nº operadores con rectificaciones
        "04",  # importe rectificaciones
    )


__all__ = ["Modelo349V2025Extractor"]
