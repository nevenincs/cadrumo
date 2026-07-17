"""Typed error classes for the IVA-compensation domain.

These guard-violation errors are raised by the pure carry-forward,
reconciliation, and balance logic. Each inherits from both
:class:`~cadrumo.core.errors.CadrumoError` (so the failure reaches the typed error
registry with a stable code and structured context) and :exc:`ValueError` (so
scalar validation and coercion failures retain the standard Python error
category).
"""

from __future__ import annotations

from ...core.errors import CadrumoError, CoreError


class IvaCompensationCarryForwardPolicyError(CadrumoError, ValueError):
    """Raised when IVA compensation carry-forward lots violate policy."""


class IvaCompensationSeedConflictError(CadrumoError, ValueError):
    """Raised when a seed is attempted for a period that already has a stored state."""


class IvaCompensationYearRangeError(CadrumoError, ValueError):
    """Raised when a filing_year or as_of_year falls outside the supported range [2000, 2099].

    Replaces bare :exc:`ValueError` at the year-range guards in
    :func:`iva_compensation_period_key` and
    :func:`build_iva_compensation_carry_forward_report`. Inherits from
    :exc:`ValueError` because these guards validate caller-supplied scalar year
    values while still surfacing a typed Cadrumo error.
    """


class IvaCompensationDecimalParseError(CadrumoError, ValueError):
    """Raised when a casilla value cannot be coerced to :class:`~decimal.Decimal`.

    Replaces the bare :exc:`ValueError` re-raised from
    :exc:`~decimal.InvalidOperation` inside the casilla-decimal coercion helper.
    Inherits from :exc:`ValueError` because it reports a scalar coercion failure
    and chains the original :exc:`~decimal.InvalidOperation` cause.
    """


class IvaCompensationCasillaReferenceError(CadrumoError, ValueError):
    """Raised when IVA compensation input uses a noncanonical casilla reference."""


class IvaCompensationReconciliationInputError(CadrumoError, ValueError):
    """Raised when IVA compensation wallet reconciliation inputs are invalid."""


class IvaWalletReconciliationError(CoreError):
    """Raised when an IVA wallet reconciliation invariant is violated.

    Covers pre-condition checks on the reconciliation inputs that fall outside
    pydantic model validation — for example, a negative ``max_wallet_age_days``
    argument supplied to the staleness predicate. Raising a typed
    :class:`CoreError` subclass instead of a bare :class:`ValueError` ensures
    the failure propagates through the error registry and produces a structured
    envelope with a stable error code.
    """
