"""Errors raised while handling financial transaction aggregation boundaries.

Used by :mod:`aeat.application.aggregation` to signal contract
violations before transaction streams reach the central calculation
registry.
"""

from __future__ import annotations

from collections.abc import Mapping

from ...core.errors import AeatError
from ...core.i18n import Translatable as tr  # noqa: N813


class AggregationError(AeatError):
    """Base class for financial transaction aggregation failures.

    The :attr:`message` field is a translation key resolved by the
    internationalization system at runtime.
    """

    def __init__(
        self,
        message: tr,
        *,
        context: Mapping[str, object] | None = None,
        suggestion: str | None = None,
    ) -> None:
        super().__init__(translated_message=message, context=context, suggestion=suggestion)


class AggregationPeriodError(AggregationError):
    """Raised when a requested filing period cannot be parsed unambiguously."""


class AggregationUnsupportedModeloError(AggregationError):
    """Raised when no aggregation contract is available for the requested modelo."""


class AggregationMissingClassificationError(AggregationError):
    """Raised when in-period transactions still need business classification."""


class AggregationCategoryCoverageError(AggregationError):
    """Raised when a business transaction lacks category or profile coverage."""


class AggregationValidationError(AggregationError, ValueError):
    """Raised on invalid aggregation payload or state. Inherits from ValueError for Pydantic."""


def t(message: str) -> tr:
    """Build a multilingual :class:`aeat.core.i18n.tr` message payload.

    Args:
        message: The translation key.

    Returns:
        A :class:`aeat.core.i18n.tr` marker for the key.
    """

    return tr(message)


__all__ = [
    "AggregationCategoryCoverageError",
    "AggregationError",
    "AggregationMissingClassificationError",
    "AggregationPeriodError",
    "AggregationUnsupportedModeloError",
    "AggregationValidationError",
    "t",
]
