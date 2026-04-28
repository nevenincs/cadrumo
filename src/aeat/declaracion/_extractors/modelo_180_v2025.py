"""Modelo 180 v2025 extractor — Resumen anual retenciones arrendamientos.

Annual aggregation of the quarterly Modelo 115 filings. The MVP
targets the summary totals block; per-arrendador detail rows are
deferred to a later wave.
"""

from __future__ import annotations

from typing import ClassVar

from .._generic_extractor import GenericDeclaracionExtractor
from .._schema import TemplateRevision


class _Modelo180BaseExtractor(GenericDeclaracionExtractor):
    """Shared summary-block extractor for Modelo 180 annual templates."""

    casilla_ids: ClassVar[tuple[str, ...]] = (
        "01",  # Total de perceptores (arrendadores)
        "02",  # Total base de retención
        "03",  # Total retenciones
        "04",  # Total ingresos a cuenta
    )


class Modelo180V2024Extractor(_Modelo180BaseExtractor):
    """Concrete extractor for Modelo 180 tax year 2024."""

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="180",
        año=2024,
        revision="2024.01",
    )


class Modelo180V2025Extractor(_Modelo180BaseExtractor):
    """Concrete extractor for Modelo 180 tax year 2025."""

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="180",
        año=2025,
        revision="2025.01",
    )


class Modelo180V2026Extractor(_Modelo180BaseExtractor):
    """Concrete extractor for Modelo 180 tax year 2026."""

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="180",
        año=2026,
        revision="2026.01",
    )


__all__ = ["Modelo180V2024Extractor", "Modelo180V2025Extractor", "Modelo180V2026Extractor"]
