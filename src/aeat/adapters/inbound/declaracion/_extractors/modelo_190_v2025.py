"""Modelo 190 v2025 extractor — Resumen anual retenciones IRPF.

Annual aggregation of the quarterly Modelo 111 filings. The current
scope targets the summary totals block across the six retenciones
categories (rendimientos del trabajo, actividades económicas, premios,
ganancias patrimoniales forestales, contraprestaciones en especie,
cesión derechos imagen) plus the overall resultado.

Out of scope: per-perceptor detail rows (one line per NIF perceptor)
and per-categoría rate verification against the tabla trabajadores
variable rates. The implementation only verifies the 21-casilla
summary aggregation, not the rate-times-base per-row relationship.
"""

from __future__ import annotations

from typing import ClassVar

from .._generic_extractor import GenericDeclaracionExtractor
from .._schema import TemplateRevision


class Modelo190V2025Extractor(GenericDeclaracionExtractor):
    """Concrete extractor for Modelo 190 tax year 2025 (período 0A).

    Attributes:
        template_revision: Pinned to ``("190", 2025, "2025.01")``.
        casilla_ids: Tuple of every casilla parsed by the extractor —
            the 18 per-categoría triples (perceptores, percepciones,
            retenciones) plus the three global totales (19/20/21).
    """

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="190",
        año=2025,
        revision="2025.01",
    )
    casilla_ids: ClassVar[tuple[str, ...]] = (
        # Apartado I — Rendimientos del trabajo.
        "01",  # Total perceptores trabajo
        "02",  # Total percepciones trabajo
        "03",  # Total retenciones trabajo
        # Apartado II — Actividades económicas.
        "04",
        "05",
        "06",
        # Apartado III — Premios.
        "07",
        "08",
        "09",
        # Apartado IV — Ganancias patrimoniales forestales.
        "10",
        "11",
        "12",
        # Apartado V — Contraprestaciones en especie.
        "13",
        "14",
        "15",
        # Apartado VI — Cesión derechos imagen.
        "16",
        "17",
        "18",
        # Totales.
        "19",  # Total perceptores global
        "20",  # Total percepciones global
        "21",  # Total retenciones global
    )


__all__ = ["Modelo190V2025Extractor"]
