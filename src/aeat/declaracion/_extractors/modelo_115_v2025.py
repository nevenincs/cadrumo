"""Modelo 115 v2025 extractor — Retenciones trimestrales de arrendamientos.

Modelo 115 is the quarterly withholdings form for rent paid on urban
real estate (typically office or commercial premises). Small form —
six casillas covering nº de arrendadores, base de retención, retención
(typically 19% of base), ingresos a cuenta, pérdidas anteriores,
resultado.
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
    casilla_ids: ClassVar[tuple[str, ...]] = (
        "01",  # nº de arrendadores
        "02",  # base de retención
        "03",  # retenciones (19% de 02)
        "04",  # ingresos a cuenta
        "05",  # resultados negativos de declaraciones anteriores
        "06",  # resultado a ingresar
    )


__all__ = ["Modelo115V2025Extractor"]
