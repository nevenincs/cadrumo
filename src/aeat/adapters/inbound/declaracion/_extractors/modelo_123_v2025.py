"""Modelo 123 declaración extractor (v2024 / v2025 / v2026 layouts).

Modelo 123 is the monthly (grandes empresas) or quarterly (default)
withholdings form for determined yields of movable capital — dividends,
interest on deposits/loans, securities income — under IRPF / IS / IRNR.
Small form: the liquidación block aggregates separately for dividends
(filas 01/04/07), other yields (02/05/08) and their totals (03/06/09),
plus the complementaria offset (10) and final resultado a ingresar (11).

Legal base: Orden 18-nov-1999 (BOE-A-1999-22309), last refreshed by
the AEAT 2024+ form layout. Caveat: the 1999 Orden's six-casilla layout
has since been replaced by the 11-casilla dividend/non-dividend split;
pre-2018 PDFs need a legacy extractor (not scoped here).
"""

from __future__ import annotations

from typing import ClassVar

from .._generic_extractor import GenericDeclaracionExtractor
from .._schema import TemplateRevision


class Modelo123V2025Extractor(GenericDeclaracionExtractor):
    """Concrete extractor for Modelo 123 tax year 2025.

    Owns the canonical 11-casilla map for the dividend / non-dividend
    liquidación split — perceptor counts (01-03), bases (04-06),
    retenciones (07-09), the complementaria offset (10), and the final
    resultado a ingresar (11).

    Attributes:
        template_revision: Pinned to ``("123", 2025, "2025.01")``.
        casilla_ids: Tuple of every casilla ID parsed by the extractor.
    """

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="123",
        año=2025,
        revision="2025.01",
    )
    casilla_ids: ClassVar[tuple[str, ...]] = (
        "01",  # nº perceptores — dividendos
        "02",  # nº perceptores — otras rentas
        "03",  # nº perceptores — total
        "04",  # base retenciones — dividendos
        "05",  # base retenciones — otras rentas
        "06",  # base retenciones — total
        "07",  # retenciones — dividendos
        "08",  # retenciones — otras rentas
        "09",  # retenciones — total
        "10",  # resultado declaración anterior (complementaria)
        "11",  # resultado a ingresar
    )


class Modelo123V2024Extractor(Modelo123V2025Extractor):
    """Modelo 123 v2024 extractor — inherits the v2025 liquidación layout.

    Attributes:
        template_revision: Pinned to ``("123", 2024, "2024.01")``.
    """

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="123",
        año=2024,
        revision="2024.01",
    )


class Modelo123V2026Extractor(Modelo123V2025Extractor):
    """Modelo 123 v2026 extractor — inherits the v2025 liquidación layout.

    Attributes:
        template_revision: Pinned to ``("123", 2026, "2026.01")``.
    """

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="123",
        año=2026,
        revision="2026.01",
    )


__all__ = [
    "Modelo123V2024Extractor",
    "Modelo123V2025Extractor",
    "Modelo123V2026Extractor",
]
