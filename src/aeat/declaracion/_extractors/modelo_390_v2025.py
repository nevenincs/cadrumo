"""Modelo 390 v2025 extractor — Resumen anual del IVA.

Annual aggregation of the quarterly Modelo 303 filings. Forms:
régimen general (Apartado 3), régimen simplificado (Apartado 4),
resultado anual (Apartado 6), regularización de la inversión en
bienes de inversión (Apartado 7). Full form has ~680 casillas; the
scoped surface targets the 15-casilla result chain that the
``modelo_390.{year}`` rulesets verify (issue #327).

Three template-revision variants ship: ``Modelo390V2024Extractor``
for 2024 filings, ``Modelo390V2025Extractor`` for 2025, and
``Modelo390V2026Extractor`` for 2026. The casilla map is the same
across the three years because the form layout is unchanged.
"""

from __future__ import annotations

from typing import ClassVar

from .._generic_extractor import GenericDeclaracionExtractor
from .._schema import TemplateRevision


class Modelo390V2025Extractor(GenericDeclaracionExtractor):
    """Concrete extractor for Modelo 390 tax year 2025 (período 0A)."""

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="390",
        año=2025,
        revision="2025.01",
    )
    # MVP: summary + resultado casillas only. Full form support lands in
    # sub-EPIC #305-Modelo-390-full alongside ruleset #221.
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
    """Modelo 390 v2024 extractor using the unchanged 2025 layout."""

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="390",
        año=2024,
        revision="2024.01",
    )


class Modelo390V2026Extractor(Modelo390V2025Extractor):
    """Modelo 390 v2026 extractor using the unchanged 2025 layout."""

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
