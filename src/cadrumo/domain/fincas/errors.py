"""Domain errors for the rental register.

Every subclass is registered in ``cadrumo.core.errors._registry._DECLARED_ERROR_CODES``
so the ``__init_subclass__`` hook on :class:`core.errors.CadrumoError`
can bind a stable :class:`core.errors.ErrorCode`.
"""

from __future__ import annotations

from ...core.errors.hierarchy import CadrumoError


class FincaRegisterError(CadrumoError):
    """Base error for the rental-register subpackage."""


class FincaNotFoundError(FincaRegisterError):
    """Raised when a referenced finca id is not present in the register."""


class ContractNotFoundError(FincaRegisterError):
    """Raised when a referenced rental contract id is not present in the register."""


class TierResolutionError(FincaRegisterError):
    """Raised when contract metadata is inconsistent and a tier cannot be resolved.

    Examples: ``tenant_min_age > tenant_max_age``,
    ``qualifying_co_tenant_count > tenant_count`` (also enforced at
    DB level), or a tier-90-a candidate with no prior-contract data.
    """


class AmortizationLedgerCapExceededError(FincaRegisterError):
    """Raised in strict mode when cumulative amortización would exceed the cap.

    Default ``compute_amortization_for_year`` clamps to the remaining
    cap and never raises. Strict callers (e.g. preflight verifiers
    that want to flag the surface) opt in via ``strict=True``.
    """


class FincaAggregationError(FincaRegisterError):
    """Raised when the rental register cannot produce coherent aggregates.

    Surface causes: contract referencing a non-existent finca; income
    record without a contract; ledger entry whose
    ``cumulative_amortization_through_year`` is out of order with
    surrounding entries (re-stated mid-year accrual without a prior
    recompute).
    """


class FincaValidationError(FincaRegisterError, ValueError):
    """Raised when rental records violate state or shape invariants.

    Inherits from ValueError to maintain compatibility with Pydantic
    validators.
    """


__all__ = [
    "AmortizationLedgerCapExceededError",
    "ContractNotFoundError",
    "FincaAggregationError",
    "FincaNotFoundError",
    "FincaRegisterError",
    "FincaValidationError",
    "TierResolutionError",
]
