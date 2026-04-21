"""Modelo 369 v2025 extractor — IVA OSS / IOSS ventanilla única.

Autoliquidación de los regímenes especiales OSS (Régimen Unión +
Régimen Exterior, trimestral) y IOSS (Régimen Importación, mensual)
para ventas B2C transfronterizas en la UE.

AEAT does not publish numbered casilla IDs for the 369 summary block
per Orden HAC/611/2021. Wave 27 adds the named-field primitive and
migrates this extractor off the header-only MVP: we capture three
summary totals that every 369 filing prints (total base imponible,
total cuota IVA, total a ingresar).

Legal base: Orden HAC/611/2021 (BOE 18/06/2021).
"""

from __future__ import annotations

from typing import ClassVar

from .._generic_extractor import GenericDeclaracionExtractor
from .._schema import TemplateRevision


class Modelo369V2025Extractor(GenericDeclaracionExtractor):
    """Named-field extractor for Modelo 369."""

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="369",
        año=2025,
        revision="2025.01",
    )
    casilla_ids: ClassVar[tuple[str, ...]] = ()
    named_field_patterns: ClassVar[dict[str, str]] = {
        "total_base_imponible": (
            r"Total\s+bases?\s+imponibles?[^\n]*?"
            r"(-?[0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2})"
        ),
        "total_cuota_iva": (
            r"Total\s+cuotas?\s+(?:IVA|devengadas?)[^\n]*?"
            r"(-?[0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2})"
        ),
        "total_a_ingresar": (
            r"Total\s+a\s+ingresar[^\n]*?"
            r"(-?[0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2})"
        ),
    }


__all__ = ["Modelo369V2025Extractor"]
