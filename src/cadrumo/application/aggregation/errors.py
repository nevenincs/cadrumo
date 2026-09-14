"""Errors raised while handling aggregation and source-mesh boundaries.

Raised by pure rollup modules such as :mod:`~.iva_ledger`,
:mod:`~.renta_ledger`, :mod:`~.retenciones`, :mod:`~.counterpart`, and
:mod:`~.foreign_assets`, and by source-mesh resolvers such as
:mod:`~.modelo_bindings` and :mod:`~.oss_ioss`, when aggregation constraints
or resolver ownership contracts are violated.
"""

from __future__ import annotations

from collections.abc import Mapping

from ...core.errors.hierarchy import CadrumoError, CoreError, TerminalPreconditionErrorMixin
from ...core.i18n.translatable import Translatable as tr
from ..operator_actions.models import PreconditionVerdict


class AggregationConfigError(CoreError):
    """Raised when an aggregation service composition invariant is violated.

    Its canonical registered ancestry is :class:`CoreError`, so it participates
    in the central error registry and ``build_error_envelope``. Pydantic field
    and model validators translate it to ``ValueError`` at their narrow
    boundary.
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


class AggregationValidationError(AggregationError):
    """Raised on invalid aggregation payload or state.

    Its canonical registered ancestry is :class:`AggregationError` under the
    application error registry. Pydantic field validators translate this
    registered failure to ``ValueError`` at their narrow boundary.
    """


__all__ = [
    "AggregationCategoryCoverageError",
    "AggregationConfigError",
    "AggregationError",
    "AggregationMissingClassificationError",
    "AggregationPeriodError",
    "AggregationUnsupportedModeloError",
    "AggregationValidationError",
]
