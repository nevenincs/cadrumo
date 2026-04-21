"""Modelo 200 v2025 extractor — Impuesto sobre Sociedades anual.

Annual IS self-assessment for limited companies (S.L., S.A., etc.) and
IRNR establecimientos permanentes. Form runs to ~2000+ casillas across
30+ pages; the MVP targets page 14 — the liquidación block that every
Modelo 200 filing prints: base imponible, ajustes, cuota íntegra,
deducciones, pagos fraccionados, and líquido a ingresar/devolver.

AEAT prints these casillas as five-digit zero-padded IDs (00550, 00592,
etc.). The :class:`GenericDeclaracionExtractor` ``casilla_width`` ClassVar
handles the wider prefix.

Legal base: renewed annually; current form per Orden HAC/495/2024
(ejercicio 2023, BOE) applied equivalently to ejercicio 2024/2025
until superseded. Per-casilla detail beyond page 14 lands in sub-EPIC
#305-Modelo-200-full.
"""

from __future__ import annotations

from typing import ClassVar

from .._generic_extractor import GenericDeclaracionExtractor
from .._schema import TemplateRevision


class Modelo200V2025Extractor(GenericDeclaracionExtractor):
    """Concrete extractor for Modelo 200 tax year 2025 (período 0A)."""

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="200",
        año=2025,
        revision="2025.01",
    )
    casilla_width: ClassVar[int] = 5
    casilla_ids: ClassVar[tuple[str, ...]] = (
        "00550",  # base imponible previa
        "01032",  # reducción reserva capitalización
        "00547",  # compensación BINs
        "00552",  # base imponible
        "00558",  # tipo de gravamen
        "00560",  # cuota íntegra previa
        "00562",  # cuota íntegra
        "00582",  # cuota íntegra ajustada positiva
        "00592",  # cuota líquida positiva
        "00599",  # retenciones e ingresos a cuenta
        "00601",  # pago fraccionado 1P
        "00603",  # pago fraccionado 2P
        "00605",  # pago fraccionado 3P
        "00611",  # cuota diferencial
        "00621",  # líquido a ingresar o devolver
    )


__all__ = ["Modelo200V2025Extractor"]
