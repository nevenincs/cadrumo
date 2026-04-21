"""Modelo 036 v2025 extractor — Declaración censal completa.

Declaración censal de alta, modificación o baja en el Censo de
Empresarios, Profesionales y Retenedores. Completa (~8 pages, all
obligados tributarios regardless of size/régimen). Event-triggered —
filed within 1 month of the hecho censal (article 10 RD 1065/2007).

**MVP scope is header-only.** Modelo 036's payload is overwhelmingly
text (actividad, régimen IVA, régimen IRPF, domicilios, representantes,
IAE epígrafes). No numeric-decimal primitive can parse it. Landing
proper extraction requires the text-value primitive tracked under
sub-EPIC #305-textual-casillas. This extractor recognises the document,
captures NIF/ejercicio/período, and returns ``values=()``.

Legal base: Orden EHA/1274/2007, modified through HAC/1634/2022.
"""

from __future__ import annotations

from typing import ClassVar

from .._generic_extractor import GenericDeclaracionExtractor
from .._schema import TemplateRevision


class Modelo036V2025Extractor(GenericDeclaracionExtractor):
    """Header-only extractor for Modelo 036."""

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="036",
        año=2025,
        revision="2025.01",
    )
    casilla_ids: ClassVar[tuple[str, ...]] = ()


__all__ = ["Modelo036V2025Extractor"]
