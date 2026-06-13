"""Errors raised while handling financial transaction aggregation boundaries.

Raised by: :mod:`~._iva_ledger`, :mod:`~._renta_ledger`, :mod:`~._retenciones`,
:mod:`~._counterpart`, :mod:`~._foreign_assets` when aggregation constraints are violated.
"""

from __future__ import annotations

from collections.abc import Mapping

from ...core.errors import AeatError, CoreError, CoreValidationError
from ...core.i18n import Translatable as tr


class AggregationConfigError(CoreError, ValueError):
    """Raised when an aggregation service composition invariant is violated.

    Inherits from ``ValueError`` so pydantic field and model validators
    surface it through ``ValidationError`` without special handling.
    Inherits from ``CoreError`` so it participates in the central error
    registry and ``build_error_envelope``.
    """


class AggregationError(AeatError):
    """Base class for financial transaction aggregation failures.

    The ``translated_message`` field is a translation key resolved by
    the internationalization system at runtime. The same key is also
    routed through the positional ``message=`` arg so ``str(exc)``
    returns the key (rather than the empty string) for diagnostic
    surfaces, structured logs, and operator error envelopes that
    render exceptions via ``str``. Without this routing, every
    operator-facing display of an aggregation error showed the empty
    string.
    """

    def __init__(
        self,
        message: tr,
        *,
        context: Mapping[str, object] | None = None,
        suggestion: str | None = None,
    ) -> None:
        super().__init__(
            str(message),
            translated_message=message,
            context=context,
            suggestion=suggestion,
        )


class AggregationPeriodError(AggregationError):
    """Raised when a requested filing period cannot be parsed unambiguously."""


class AggregationUnsupportedModeloError(AggregationError):
    """Raised when no aggregation contract is available for the requested modelo."""


class AggregationMissingClassificationError(AggregationError):
    """Raised when in-period transactions still need business classification."""


class AggregationCategoryCoverageError(AggregationError):
    """Raised when a business transaction lacks category or profile coverage."""


class AggregationValidationError(AggregationError, CoreValidationError):
    """Raised on invalid aggregation payload or state.

    Inherits from CoreValidationError (which itself inherits from CoreError
    and ValueError) to participate in the shared CoreValidationError catch
    surface and remain compatible with pydantic field validators.
    """


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
    "AggregationConfigError",
    "AggregationError",
    "AggregationMissingClassificationError",
    "AggregationPeriodError",
    "AggregationUnsupportedModeloError",
    "AggregationValidationError",
    "t",
]
