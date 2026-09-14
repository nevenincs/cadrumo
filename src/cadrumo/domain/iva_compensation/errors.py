"""Typed error classes for the IVA-compensation domain.

These guard-violation errors are raised by the pure carry-forward,
reconciliation, and balance logic. Each uses the canonical registered
:class:`~cadrumo.core.errors.CadrumoError` ancestry, so the failure reaches the
typed error registry with a stable code and structured context. Pydantic
validators translate a registered failure to ``ValueError`` at their narrow
validator boundary when scalar validation or coercion crosses that protocol.
"""

from __future__ import annotations

from ...core.errors.hierarchy import CadrumoError, CoreError


class IvaCompensationCarryForwardPolicyError(CadrumoError):
    """Raised when IVA compensation carry-forward lots violate policy."""


class IvaCompensationSeedConflictError(CadrumoError):
    """Raised when a seed is attempted for a period that already has a stored state."""


class IvaCompensationYearRangeError(CadrumoError):
    """Raised when a filing_year or as_of_year falls outside the supported range [2000, 2099].

    Replaces bare :exc:`ValueError` at the year-range guards in
    :func:`iva_compensation_period_key` and
    :func:`build_iva_compensation_carry_forward_report`. Its canonical
    registered ancestry is :class:`~cadrumo.core.errors.CadrumoError`; a
    Pydantic validator translates it to ``ValueError`` at its narrow boundary
    when these scalar checks are performed there.
    """


class IvaCompensationDecimalParseError(CadrumoError):
    """Raised when a casilla value cannot be coerced to :class:`~decimal.Decimal`.

    Replaces the bare :exc:`ValueError` re-raised from
    :exc:`~decimal.InvalidOperation` inside the casilla-decimal coercion helper.
    Its canonical registered ancestry is :class:`~cadrumo.core.errors.CadrumoError`;
    a Pydantic validator translates it to ``ValueError`` at its narrow boundary
    while the direct helper chains the original :exc:`~decimal.InvalidOperation`
    cause.
    """


class IvaCompensationCasillaReferenceError(CadrumoError):
    """Raised when IVA compensation input uses a noncanonical casilla reference."""


class IvaCompensationReconciliationInputError(CadrumoError):
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
