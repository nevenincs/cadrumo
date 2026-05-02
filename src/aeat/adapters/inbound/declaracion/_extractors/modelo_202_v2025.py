"""Modelo 202 v2025 extractor — IS pago fraccionado.

Installment filings in April / October / December (períodos 1P / 2P / 3P)
for limited companies and IRNR EP with INCN ≥ 6M€ or modalidad base
opt-in. Computes the installment from either prior-year cuota (art. 40.2
LIS) or running current-year base (art. 40.3 LIS), applying the
micropyme/pyme rate boxes introduced by Orden HAC/262/2025.

Legal base: Orden HFP/227/2017 (BOE-A-2017-2778); modified by Orden
HFP/312/2023 and Orden HAC/262/2025 (BOE-A-2025-5407).

Casilla 34 ("Cantidad a ingresar — mayor de claves [32] y [33]") is
verified against the 2025 form per BOE-A-2025-5407 Anexo I pág. 36465
(liquidación block 4) and the ``Ingreso (8)`` block on the same page
which references ``Importe (casilla [34] ó [03])``.
"""

from __future__ import annotations

from typing import ClassVar

from .._generic_extractor import GenericDeclaracionExtractor
from .._schema import TemplateRevision


class Modelo202V2025Extractor(GenericDeclaracionExtractor):
    """Concrete extractor for Modelo 202 tax year 2025.

    Owns the nine-casilla liquidación map covering the base, tipo,
    cuota íntegra, bonificaciones, retenciones, prior-period payments,
    resultado, mínimo, and the final cantidad a ingresar.

    Attributes:
        template_revision: Pinned to ``("202", 2025, "2025.01")``.
        casilla_ids: Tuple of every casilla parsed by the extractor.
    """

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="202",
        año=2025,
        revision="2025.01",
    )
    casilla_ids: ClassVar[tuple[str, ...]] = (
        "16",  # base del pago fraccionado
        "17",  # tipo de gravamen aplicable
        "18",  # cuota íntegra
        "27",  # bonificaciones
        "28",  # retenciones e ingresos a cuenta
        "30",  # pagos fraccionados anteriores del ejercicio
        "32",  # resultado
        "33",  # mínimo a ingresar
        "34",  # cantidad a ingresar (mayor de 32 o 33)
    )


__all__ = ["Modelo202V2025Extractor"]
