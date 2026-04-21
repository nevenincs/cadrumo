"""Modelo 720 v2025 extractor — Bienes y derechos en el extranjero.

Declaración informativa anual (1-ene → 31-mar del año siguiente) sobre
cuentas, valores/seguros/rentas e inmuebles en el extranjero cuando la
valoración por clave supera los 50 000 € (DA 18ª LGT).

**MVP scope is header-only.** The 720 diseño lógico (Orden HAP/72/2013)
has a resumen tipo-1 record with per-clave (C/V/I) counters and totals,
but the PDF rendering does not print numbered casilla IDs — the data
lives in named fields inside a registro de tipo 1. A field-name-anchored
primitive lands in sub-EPIC #305-textual-casillas. This extractor
recognizes the document, extracts NIF/ejercicio/período, and returns
an empty ``values`` tuple.

Legal base: Orden HAP/72/2013 (BOE-A-2013-954).
"""

from __future__ import annotations

from typing import ClassVar

from .._generic_extractor import GenericDeclaracionExtractor
from .._schema import TemplateRevision


class Modelo720V2025Extractor(GenericDeclaracionExtractor):
    """Header-only extractor for Modelo 720."""

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="720",
        año=2025,
        revision="2025.01",
    )
    casilla_ids: ClassVar[tuple[str, ...]] = ()


__all__ = ["Modelo720V2025Extractor"]
