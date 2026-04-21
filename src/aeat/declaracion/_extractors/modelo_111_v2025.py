"""Modelo 111 v2025 extractor — Retenciones IRPF trimestrales.

Modelo 111 is the quarterly withholdings summary every employer /
autónomo files: number of perceivers + aggregate amounts + retenciones
across six categories (rendimientos del trabajo, actividades
económicas, premios, ganancias patrimoniales, imputación de rentas,
cesión derechos imagen) plus the total to pay.
"""

from __future__ import annotations

from typing import ClassVar

from .._generic_extractor import GenericDeclaracionExtractor
from .._schema import TemplateRevision


class Modelo111V2025Extractor(GenericDeclaracionExtractor):
    """Concrete extractor for Modelo 111 tax year 2025."""

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="111",
        año=2025,
        revision="2025.01",
    )
    casilla_ids: ClassVar[tuple[str, ...]] = (
        # Apartado I — Rendimientos del trabajo.
        "01",  # nº perceptores
        "02",  # importe percepciones
        "03",  # importe retenciones
        # Apartado II — Actividades económicas.
        "04",
        "05",
        "06",
        # Apartado III — Premios.
        "07",
        "08",
        "09",
        # Apartado IV — Ganancias patrimoniales aprovechamientos forestales.
        "10",
        "11",
        "12",
        # Apartado V — Contraprestaciones en especie (subsuma del apartado I).
        "13",
        "14",
        "15",
        # Apartado VI — Imputación de rentas por cesión de derechos de imagen.
        "16",
        "17",
        "18",
        # Resultado.
        "28",  # Total ingresos a cuenta
        "29",  # Resultados negativos de declaraciones anteriores
        "30",  # Resultado a ingresar
    )


__all__ = ["Modelo111V2025Extractor"]
