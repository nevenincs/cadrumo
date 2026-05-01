"""Domain errors for classified-transaction casilla aggregation."""

from __future__ import annotations

from ....core.errors import AeatError
from ....core.i18n import Translatable


class AggregationError(AeatError):
    """Base class for financial T6 aggregation failures."""


class AggregationPeriodError(AggregationError):
    """Raised when a requested filing period cannot be parsed unambiguously."""


class AggregationUnsupportedModeloError(AggregationError):
    """Raised when no aggregation contract is available for the requested modelo."""


class AggregationMissingClassificationError(AggregationError):
    """Raised when in-period transactions still need classification."""


class AggregationCategoryCoverageError(AggregationError):
    """Raised when a business transaction lacks category/profile coverage."""


class AggregationCasillaMappingError(AggregationError):
    """Raised when category profiles do not provide usable casilla mappings."""


def t(es: str, en: str, hu: str) -> Translatable:
    """Build a trilingual message payload."""

    return {"es": es, "en": en, "hu": hu}


__all__ = [
    "AggregationCasillaMappingError",
    "AggregationCategoryCoverageError",
    "AggregationError",
    "AggregationMissingClassificationError",
    "AggregationPeriodError",
    "AggregationUnsupportedModeloError",
    "t",
]
