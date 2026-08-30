"""Errors raised while handling aggregation and source-mesh boundaries.

Raised by pure rollup modules such as :mod:`~._iva_ledger`,
:mod:`~._renta_ledger`, :mod:`~._retenciones`, :mod:`~._counterpart`, and
:mod:`~._foreign_assets`, and by source-mesh resolvers such as
:mod:`~._modelo_bindings` and :mod:`~._oss_ioss`, when aggregation constraints
or resolver ownership contracts are violated.
"""

from __future__ import annotations

from collections.abc import Mapping

from ...core.errors.hierarchy import CadrumoError, CoreError, CoreValidationError, TerminalPreconditionErrorMixin
from ...core.i18n import Translatable as tr
from ..operator_actions import PreconditionVerdict


class AggregationConfigError(CoreError, ValueError):
    """Raised when an aggregation service composition invariant is violated.

    Inherits from ``ValueError`` so pydantic field and model validators
    surface it through ``ValidationError`` without special handling.
    Inherits from ``CoreError`` so it participates in the central error
    registry and ``build_error_envelope``.
    """


class AggregationError(TerminalPreconditionErrorMixin[PreconditionVerdict], CadrumoError):
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
        precondition_verdict: PreconditionVerdict | None = None,
    ) -> None:
        """Initialize this public contract."""
        super().__init__(
            str(message), translated_message=message, context=context, precondition_verdict=precondition_verdict
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


# Local construction shorthand for this package's typed translation keys.
t = tr


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
