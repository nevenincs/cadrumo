"""Modelo 390 (Resumen anual del IVA) declaración extractor.

Annual aggregation of the quarterly Modelo 303 filings. Sections:
régimen general (Apartado 3), régimen simplificado (Apartado 4),
resultado anual (Apartado 6), regularización de la inversión en
bienes de inversión (Apartado 7). The full form has ~680 casillas; this
extractor targets the 15-casilla result chain verified by the
``modelo_390.{year}`` rulesets.

Three template-revision variants ship — :class:`Modelo390V2024Extractor`
for 2024 filings, :class:`Modelo390V2025Extractor` for 2025, and
:class:`Modelo390V2026Extractor` for 2026. The casilla map is the same
across the three years because the form layout is unchanged.
"""

from __future__ import annotations

from typing import ClassVar

from .._generic_extractor import GenericDeclaracionExtractor
from .._schema import TemplateRevision


class Modelo390V2025Extractor(GenericDeclaracionExtractor):
    """Concrete extractor for Modelo 390 tax year 2025 (período 0A).

    Captures the 15-casilla summary + resultado chain via the shared
    :class:`aeat.adapters.inbound.declaracion._generic_extractor.GenericDeclaracionExtractor`
    primitives.

    Attributes:
        template_revision: Identifier (modelo ``"390"``, año ``2025``,
            revision ``"2025.01"``).
        casilla_ids: Ordered tuple of supported casillas covering Apartado 1
            (datos estadísticos), Apartado 3 (régimen general anual totals),
            Apartado 6 (resultado anual), and Apartado 7 (regularización
            bienes inversión).
    """

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="390",
        año=2025,
        revision="2025.01",
    )
    casilla_ids: ClassVar[tuple[str, ...]] = (
        # Apartado 1 — datos estadísticos.
        "01",  # Régimen general (1T total base)
        "04",  # Régimen general (1T total cuota)
        # Apartado 3 — régimen general anual totals.
        "95",  # Total bases imponibles
        "96",  # Total cuotas repercutidas
        "100",  # Total IVA deducible interior
        "101",  # Total IVA deducible importaciones
        "104",  # Total IVA soportado
        "105",  # Resultado régimen general
        "108",  # Resultado simplificado
        "109",  # Otros regímenes
        # Apartado 6 — resultado anual.
        "190",  # Suma resultado
        "191",  # Cuota resultante anual
        "192",  # Total a ingresar
        "193",  # Total a devolver
        # Apartado 7 — regularización bienes inversión.
        "662",  # Regularización bienes inversión
    )


class Modelo390V2024Extractor(Modelo390V2025Extractor):
    """Modelo 390 v2024 extractor reusing the unchanged 2025 layout.

    Attributes:
        template_revision: Identifier (modelo ``"390"``, año ``2024``,
            revision ``"2024.01"``).
    """

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="390",
        año=2024,
        revision="2024.01",
    )


class Modelo390V2026Extractor(Modelo390V2025Extractor):
    """Modelo 390 v2026 extractor reusing the unchanged 2025 layout.

    Attributes:
        template_revision: Identifier (modelo ``"390"``, año ``2026``,
            revision ``"2026.01"``).
    """

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="390",
        año=2026,
        revision="2026.01",
    )


__all__ = [
    "Modelo390V2024Extractor",
    "Modelo390V2025Extractor",
    "Modelo390V2026Extractor",
]
