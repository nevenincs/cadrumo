"""Modelo 347 v2025 extractor — Operaciones con terceros (>= 3005.06 €).

Annual informative filing of transactions with single parties whose
aggregate value exceeds €3,005.06 during the year. The MVP targets
the summary totals block; per-counterparty detail rows (one per NIF
declarado) lands in sub-EPIC #305-Modelo-347-full.
"""

from __future__ import annotations

from typing import ClassVar

from .._generic_extractor import GenericDeclaracionExtractor
from .._schema import TemplateRevision


class Modelo347V2025Extractor(GenericDeclaracionExtractor):
    """Concrete extractor for Modelo 347 tax year 2025 (período 0A)."""

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="347",
        año=2025,
        revision="2025.01",
    )
    casilla_ids: ClassVar[tuple[str, ...]] = (
        "01",  # Nº total de declarados
        "02",  # Importe total anual de operaciones declaradas
        "03",  # Nº total registros por cobros en metálico
        "04",  # Importe total cobros en metálico
    )


__all__ = ["Modelo347V2025Extractor"]
