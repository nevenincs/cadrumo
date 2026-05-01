"""Modelo 115 declaración extractor for the v2024, v2025, and v2026 layouts.

Modelo 115 is the quarterly withholdings form for rent paid on urban real
estate (typically office or commercial premises). Six casillas cover nº de
arrendadores, base de retención, retención (19 % of base per RIRPF art. 100 ¶
1), ingresos a cuenta, pérdidas anteriores, and resultado.

The AEAT form layout is unchanged across 2024, 2025, and 2026 because RIRPF
art. 100 has not been amended (the consolidated text was last updated on
2026-02-28). A single extraction implementation therefore backs three thin
per-year subclasses that each pin their own ``template_revision`` ClassVar.
The extraction logic lives on :meth:`GenericDeclaracionExtractor.extract`,
inherited by :class:`Modelo115V2025Extractor` and its 2024 / 2026 siblings.
"""

from __future__ import annotations

from typing import ClassVar

from .._generic_extractor import GenericDeclaracionExtractor
from .._schema import TemplateRevision


class Modelo115V2025Extractor(GenericDeclaracionExtractor):
    """Concrete extractor for Modelo 115 tax year 2025."""

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="115",
        año=2025,
        revision="2025.01",
    )
    # Labels verified vs AEAT Instrucciones Modelo 115 (/49 H5).
    casilla_ids: ClassVar[tuple[str, ...]] = (
        "01",  # nº de arrendadores
        "02",  # base de retención
        "03",  # retenciones (19% de 02)
        "04",  # ingresos a cuenta (retribuciones en especie)
        "05",  # A deducir: exclusivamente en declaración complementaria
        "06",  # resultado a ingresar
    )


class Modelo115V2024Extractor(Modelo115V2025Extractor):
    """Modelo 115 v2024 extractor — same layout as v2025 / v2026.

    Issue #319: the AEAT Modelo 115 form layout is unchanged
    across 2024 → 2025 → 2026 (RIRPF art. 100 not amended;
    consolidated text last update 2026-02-28). This subclass
    inherits the full
    :meth:`GenericDeclaracionExtractor.extract` implementation
    via :class:`Modelo115V2025Extractor` and pins only the
    ``template_revision`` ClassVar so the registry resolves
    ``(modelo="115", año=2024, revision="2024.01")`` to a working
    extractor.
    """

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="115",
        año=2024,
        revision="2024.01",
    )


class Modelo115V2026Extractor(Modelo115V2025Extractor):
    """Modelo 115 v2026 extractor — same layout as v2024 / v2025.

    Issue #319: the AEAT Modelo 115 form layout is unchanged
    across 2024 → 2025 → 2026 (RIRPF art. 100 not amended;
    consolidated text last update 2026-02-28). This subclass
    inherits the full
    :meth:`GenericDeclaracionExtractor.extract` implementation
    via :class:`Modelo115V2025Extractor` and pins only the
    ``template_revision`` ClassVar so the registry resolves
    ``(modelo="115", año=2026, revision="2026.01")`` to a working
    extractor.
    """

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="115",
        año=2026,
        revision="2026.01",
    )


__all__ = [
    "Modelo115V2024Extractor",
    "Modelo115V2025Extractor",
    "Modelo115V2026Extractor",
]
