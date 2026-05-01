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

from ...pdf._label_regex import SPANISH_AMOUNT_GROUP
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
    # Line-anchored + soportado-exclusion (wave 33 M2 fix) to stop
    # ``Total cuotas IVA soportado`` from matching ``total_cuota_iva``
    # (soportado = IVA deducible, NOT IVA devengada).
    # Each pattern uses a negative-lookahead to reject ``soportad`` (IVA
    # deducible), so ``Total cuotas IVA soportado`` won't collide with
    # the devengada/to-pay fields. Line-anchored (?m)^ keeps matches
    # local to one row.
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
