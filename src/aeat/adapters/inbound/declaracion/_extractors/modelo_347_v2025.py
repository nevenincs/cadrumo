"""Modelo 347 (Operaciones con terceros) extractor for tax year 2025.

Annual informative filing of transactions with single parties whose
aggregate value exceeds €3,005.06 during the year. This extractor
targets the summary totals block; per-counterparty detail rows (one
per NIF declarado) are out of scope.

The extractor delegates to :class:`aeat.adapters.inbound.declaracion._generic_extractor.GenericDeclaracionExtractor`,
overriding only :attr:`template_revision` and :attr:`casilla_ids`.
"""

from __future__ import annotations

from typing import ClassVar

from .._generic_extractor import GenericDeclaracionExtractor
from .._schema import TemplateRevision


class Modelo347V2025Extractor(GenericDeclaracionExtractor):
    """Concrete extractor for Modelo 347 tax year 2025 (período 0A).

    Captures the four summary casillas printed at the foot of the
    declaración (declared-counterparty count + total operations + cash
    receipt count + cash receipt total).

    Attributes:
        template_revision: Identifier (modelo ``"347"``, año ``2025``,
            revision ``"2025.01"``).
        casilla_ids: Ordered tuple of supported casillas — 01 (Nº total
            de declarados), 02 (Importe total anual de operaciones), 03
            (Nº total registros por cobros en metálico), 04 (Importe
            total cobros en metálico).
    """

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
