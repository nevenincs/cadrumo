"""Modelo 232 v2025 extractor — Operaciones vinculadas y paraísos fiscales.

Declaración informativa anual (mes 11 post-cierre, noviembre para el
ejercicio natural) que recoge operaciones con partes vinculadas por
encima de umbrales y cualquier operación con paraísos fiscales.

**MVP scope is header-only.** AEAT does NOT print numbered casilla IDs
on the 232 resumen — the form is structured as three info blocks with
named fields (nº registros por bloque). A field-name-anchored primitive
lands in sub-EPIC #305-textual-casillas. This extractor recognizes the
document, extracts NIF/ejercicio/período, and returns an empty
``values`` tuple.

Legal base: Orden HFP/816/2017 (BOE-A-2017-10042).
"""

from __future__ import annotations

from typing import ClassVar

from .._generic_extractor import GenericDeclaracionExtractor
from .._schema import TemplateRevision


class Modelo232V2025Extractor(GenericDeclaracionExtractor):
    """Header-only extractor for Modelo 232."""

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="232",
        año=2025,
        revision="2025.01",
    )
    casilla_ids: ClassVar[tuple[str, ...]] = ()


__all__ = ["Modelo232V2025Extractor"]
