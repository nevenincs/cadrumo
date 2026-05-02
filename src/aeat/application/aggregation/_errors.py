"""Errors raised while aggregating classified transactions into casilla totals.

Used by :mod:`aeat.application.aggregation` to signal contract
violations when classified transaction streams are folded into the
casilla ledger consumed by :mod:`aeat.domain.filing`.
"""

from __future__ import annotations

from ...core.errors import AeatError
from ...core.i18n import Translatable


class AggregationError(AeatError):
    """Base class for financial transaction aggregation failures."""


class AggregationPeriodError(AggregationError):
    """Raised when a requested filing period cannot be parsed unambiguously."""


class AggregationUnsupportedModeloError(AggregationError):
    """Raised when no aggregation contract is available for the requested modelo."""


class AggregationMissingClassificationError(AggregationError):
    """Raised when in-period transactions still need business classification."""


class AggregationCategoryCoverageError(AggregationError):
    """Raised when a business transaction lacks category or profile coverage."""


class AggregationCasillaMappingError(AggregationError):
    """Raised when category profiles do not provide usable casilla mappings."""


def t(es: str, en: str, hu: str) -> Translatable:
    """Build a multilingual :class:`aeat.core.i18n.Translatable` message payload.

    Args:
        es: Spanish message.
        en: English message.
        hu: Hungarian message.

    Returns:
        A :class:`aeat.core.i18n.Translatable` mapping carrying all
        three languages keyed by ISO 639-1 code.
    """

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
