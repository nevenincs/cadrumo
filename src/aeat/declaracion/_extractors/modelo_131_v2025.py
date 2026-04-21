"""Modelo 131 v2025 extractor — IRPF pago fraccionado (estimación objetiva).

Modelo 131 is the quarterly IRPF pre-payment form for autónomos under
the módulos régimen (estimación objetiva), mirroring Modelo 130 for
the direct-estimation cousin. 15 liquidación casillas cover module
coefficients, trimestre payment, volumen ventas adjustment, retenciones,
compensación de negativos anteriores, and final resultado a ingresar.

Legal base: Orden EHA/672/2007 (BOE-A-2007-6032); yearly refresh per
BOE Sede AEAT instructions.
"""

from __future__ import annotations

from typing import ClassVar

from .._generic_extractor import GenericDeclaracionExtractor
from .._schema import TemplateRevision


class Modelo131V2025Extractor(GenericDeclaracionExtractor):
    """Concrete extractor for Modelo 131 tax year 2025 (quarterly)."""

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="131",
        año=2025,
        revision="2025.01",
    )
    casilla_ids: ClassVar[tuple[str, ...]] = (
        "01",  # suma rendimientos netos módulos
        "02",  # pago fraccionado del trimestre
        "03",  # volumen ventas (actividades sin datos-base)
        "04",  # 2% s/casilla 03
        "05",  # volumen ingresos agrícolas/forestales
        "06",  # 2% s/casilla 05
        "07",  # total (02+04+06)
        "08",  # retenciones e ingresos a cuenta del trimestre
        "09",  # minoración por rendimientos netos año anterior
        "10",  # resultado (07-08-09)
        "11",  # resultados negativos trimestres anteriores
        "12",  # deducción por adquisición vivienda habitual
        "13",  # resultado (10-11-12)
        "14",  # a deducir declaración complementaria
        "15",  # resultado a ingresar
    )


__all__ = ["Modelo131V2025Extractor"]
