"""Modelo 037 v2025 extractor — Declaración censal simplificada.

Declaración censal simplificada — reduced version of Modelo 036 for
empresarios individuales meeting size thresholds (no IVA intracomunitario,
no operaciones con paraísos fiscales, no exports/imports outside EU,
no IS, etc.). Event-triggered.

**MVP scope is header-only.** Same rationale as Modelo 036: payload is
text-dominant (régimen IVA, régimen IRPF estimación, actividad
económica, IAE epígrafe, domicilio fiscal). The text-value primitive
lands in sub-EPIC #305-textual-casillas. This extractor recognises
the document, captures NIF/ejercicio/período, and returns ``values=()``.

Legal base: Orden EHA/1274/2007 (same Orden as Modelo 036, Anexo II).
"""

from __future__ import annotations

from typing import ClassVar

from .._generic_extractor import GenericDeclaracionExtractor
from .._schema import TemplateRevision


class Modelo037V2025Extractor(GenericDeclaracionExtractor):
    """Header-only extractor for Modelo 037."""

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="037",
        año=2025,
        revision="2025.01",
    )
    casilla_ids: ClassVar[tuple[str, ...]] = ()


__all__ = ["Modelo037V2025Extractor"]
