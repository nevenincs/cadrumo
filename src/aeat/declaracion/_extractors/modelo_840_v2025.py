"""Modelo 840 v2025 extractor — IAE (censal, declaración por actos).

Declaración censal del Impuesto sobre Actividades Económicas — alta,
variación, baja, o comunicación del importe neto de la cifra de
negocios. Not periodic: filed within one month of the hecho censal.
IAE affects only sujetos whose INCN exceeds 1M€ (art. 82.1.c LRHL);
most autónomos are exempt.

**MVP scope is header-only.** AEAT prints numbered casilla IDs on the
form (14, 15, 33, 34, 37, 38, 40, 62), but the values under those
labels are non-numeric (actividad codes, epígrafes, municipios,
fechas). The current :class:`GenericDeclaracionExtractor` primitive
captures Spanish-formatted decimals only; a text-value-anchored
primitive lands in sub-EPIC #305-textual-casillas. This extractor
recognizes the document, extracts NIF/ejercicio/período, and returns
an empty ``values`` tuple so the rest of the pipeline treats it as
``EXTRACTION_UNRELIABLE`` (zero resolved casillas).

Legal base: Orden HAC/2572/2003 (BOE 18/09/2003).
"""

from __future__ import annotations

from typing import ClassVar

from .._generic_extractor import GenericDeclaracionExtractor
from .._schema import TemplateRevision


class Modelo840V2025Extractor(GenericDeclaracionExtractor):
    """Header-only extractor for Modelo 840 pending text-value primitive."""

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="840",
        año=2025,
        revision="2025.01",
    )
    # Intentionally empty: numeric primitive cannot parse text casillas.
    casilla_ids: ClassVar[tuple[str, ...]] = ()


__all__ = ["Modelo840V2025Extractor"]
