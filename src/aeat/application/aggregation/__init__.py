"""T6 aggregation from classified transactions to AEAT casilla inputs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._errors import (
    AggregationCasillaMappingError,
    AggregationCategoryCoverageError,
    AggregationError,
    AggregationMissingClassificationError,
    AggregationPeriodError,
    AggregationUnsupportedModeloError,
)
from ._models import CasillaAggregation, CasillaProvenance, Period, PeriodKind
from ._service import aggregate_catalogue

if TYPE_CHECKING:
    from ._provider import FinancialFilingInputsProvider

__all__ = [
    "AggregationCasillaMappingError",
    "AggregationCategoryCoverageError",
    "AggregationError",
    "AggregationMissingClassificationError",
    "AggregationPeriodError",
    "AggregationUnsupportedModeloError",
    "CasillaAggregation",
    "CasillaProvenance",
    "FinancialFilingInputsProvider",
    "Period",
    "PeriodKind",
    "aggregate_catalogue",
]


def __getattr__(name: str) -> object:
    """Lazily expose repository-backed provider without importing storage at CLI startup."""

    if name == "FinancialFilingInputsProvider":
        from ._provider import FinancialFilingInputsProvider

        return FinancialFilingInputsProvider
    raise AttributeError(name)
