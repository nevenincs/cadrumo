"""Modelo 369 v2025 extractor — IVA OSS / IOSS ventanilla única.

Autoliquidación de los regímenes especiales OSS (Régimen Unión +
Régimen Exterior, trimestral) y IOSS (Régimen Importación, mensual)
para ventas B2C transfronterizas en la UE.

**MVP scope is header-only.** AEAT does not publish numbered casilla
IDs for the 369 summary block in the Orden HAC/611/2021 diseño de
registro — field names (total_base_imponible, total_cuota_iva,
total_a_ingresar) are the access path, and the per-country detail
block is autocompleted. A field-name-anchored primitive lands in
sub-EPIC #305-textual-casillas. This extractor recognizes the
document, extracts NIF/ejercicio/período, and returns an empty
``values`` tuple.

Legal base: Orden HAC/611/2021 (BOE 18/06/2021).
"""

from __future__ import annotations

from typing import ClassVar

from .._generic_extractor import GenericDeclaracionExtractor
from .._schema import TemplateRevision


class Modelo369V2025Extractor(GenericDeclaracionExtractor):
    """Header-only extractor for Modelo 369."""

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="369",
        año=2025,
        revision="2025.01",
    )
    casilla_ids: ClassVar[tuple[str, ...]] = ()


__all__ = ["Modelo369V2025Extractor"]
