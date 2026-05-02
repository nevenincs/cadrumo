"""Modelo 200 v2025 extractor — Impuesto sobre Sociedades anual.

Annual IS self-assessment for limited companies (S.L., S.A., etc.) and
IRNR establecimientos permanentes. The form runs to ~2000+ casillas
across 30+ pages; the current scope targets page 14 — the liquidación
block that every Modelo 200 filing prints: base imponible, ajustes,
cuota íntegra, deducciones, pagos fraccionados, and líquido a
ingresar/devolver.

AEAT prints these casillas as five-digit zero-padded IDs (``00550``,
``00592``, etc.). The
:attr:`aeat.adapters.inbound.declaracion._generic_extractor.GenericDeclaracionExtractor.casilla_width`
ClassVar handles the wider prefix.

Legal base: Modelo 200 is renewed annually by its own BOE Orden; the
2024 filing (ejercicio 2024 results) is governed by **Orden
HAC/657/2025** (BOE-A-2025-12818, 24-jun-2025), which introduced the
**autoliquidación rectificativa** block on page 14. The casilla set
below is the liquidación subset that feeds into casilla 00621
(líquido a ingresar o devolver); rectificativa casillas and
per-deducción itemisation are out of scope.

Labels cross-checked against AEAT Manual Sociedades 2024.
"""

from __future__ import annotations

from typing import ClassVar

from .._generic_extractor import GenericDeclaracionExtractor
from .._schema import TemplateRevision


class Modelo200V2025Extractor(GenericDeclaracionExtractor):
    """Concrete extractor for Modelo 200 tax year 2025 (período 0A).

    Targets the page-14 liquidación block — base imponible, cuota
    íntegra, bonificaciones y deducciones doble imposición
    internacional, cuota líquida, retenciones, the three pago
    fraccionado payments, and the cuota diferencial / líquido a
    ingresar finals.

    Casilla 01032 (reducción reserva capitalización) is printed on a
    different page and is intentionally absent — including it here would
    risk false-positive label matches against any other page that
    happens to print "01032".

    Attributes:
        template_revision: Pinned to ``("200", 2025, "2025.01")``.
        casilla_width: Five — Modelo 200 prints zero-padded five-digit
            casilla IDs.
        casilla_ids: Tuple of every casilla parsed by the extractor.
    """

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="200",
        año=2025,
        revision="2025.01",
    )
    casilla_width: ClassVar[int] = 5
    # Page-14 liquidación block only. casilla 01032 (reducción reserva
    # capitalización) is printed on a different page of the form;
    # leaving it out here avoids false-positive label matches against
    # any other page that happens to print "01032".
    casilla_ids: ClassVar[tuple[str, ...]] = (
        "00547",  # compensación bases imponibles negativas de períodos anteriores
        "00550",  # base imponible antes de reserva capitalización + compensación BINs
        "00552",  # base imponible
        "00558",  # tipo de gravamen
        "00560",  # cuota íntegra previa
        "00562",  # cuota íntegra
        # 00582 is "bonificaciones y deducciones doble imposición
        # internacional" per AEAT Manual Sociedades 2024. The
        # "cuota íntegra ajustada positiva" label actually belongs to 00592.
        "00582",  # bonificaciones y deducciones doble imposición internacional
        "00592",  # cuota líquida
        "00599",  # retenciones e ingresos a cuenta
        "00601",  # pago fraccionado 1P
        "00603",  # pago fraccionado 2P
        "00605",  # pago fraccionado 3P
        "00615",  # abono de deducciones (feeds 00621)
        "00619",  # incremento por pérdida beneficios fiscales (feeds 00621)
        "00611",  # cuota diferencial
        "00621",  # líquido a ingresar o devolver
    )


__all__ = ["Modelo200V2025Extractor"]
