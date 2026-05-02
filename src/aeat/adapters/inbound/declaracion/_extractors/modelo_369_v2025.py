"""Modelo 369 (IVA OSS / IOSS ventanilla única) extractor for tax year 2025.

Autoliquidación de los regímenes especiales OSS (Régimen Unión + Régimen
Exterior, trimestral) y IOSS (Régimen Importación, mensual) para ventas
B2C transfronterizas en la UE.

AEAT does not publish numbered casilla IDs for the 369 summary block per
Orden HAC/611/2021, so this extractor uses the named-field primitive: it
captures three summary totals every 369 filing prints — total base
imponible, total cuota IVA (devengada), total a ingresar.

Legal base: Orden HAC/611/2021 (BOE 18/06/2021).
"""

from __future__ import annotations

from typing import ClassVar

from ...pdf._label_regex import SPANISH_AMOUNT_GROUP
from .._generic_extractor import GenericDeclaracionExtractor
from .._schema import TemplateRevision


class Modelo369V2025Extractor(GenericDeclaracionExtractor):
    """Named-field extractor for Modelo 369.

    Each :attr:`named_field_patterns` entry is line-anchored (``(?m)^``)
    and applies a negative lookahead for ``soportad`` to keep ``Total
    cuotas IVA soportado`` (IVA deducible) from colliding with the
    devengada / to-pay totals (``soportado`` is IVA deducible, NOT IVA
    devengada).

    Attributes:
        template_revision: Identifier (modelo ``"369"``, año ``2025``,
            revision ``"2025.01"``).
        casilla_ids: Empty — Modelo 369 prints no numbered casillas.
        named_field_patterns: Map ``field_id → raw regex pattern`` for
            the three summary totals (total base imponible, total cuota
            IVA, total a ingresar).
    """

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="369",
        año=2025,
        revision="2025.01",
    )
    casilla_ids: ClassVar[tuple[str, ...]] = ()
    named_field_patterns: ClassVar[dict[str, str]] = {
        "total_base_imponible": (
            rf"(?m)^(?![^\n]*soportad)[^\n]*?Total\s+bases?\s+imponibles?[^\n]*?{SPANISH_AMOUNT_GROUP}"
        ),
        "total_cuota_iva": (
            rf"(?m)^(?![^\n]*soportad)[^\n]*?Total\s+cuotas?\s+(?:IVA\s*(?:devengad\S*)?|devengadas?)[^\n]*?"
            rf"{SPANISH_AMOUNT_GROUP}"
        ),
        "total_a_ingresar": (rf"(?m)^[^\n]*?Total\s+a\s+ingresar[^\n]*?{SPANISH_AMOUNT_GROUP}"),
    }


__all__ = ["Modelo369V2025Extractor"]
