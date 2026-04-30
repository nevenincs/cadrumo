"""Domain errors for the rental register (#454).

Every subclass is registered in ``aeat.errors._registry._DECLARED_ERROR_CODES``
so the ``__init_subclass__`` hook on :class:`AeatError` can bind a stable
:class:`ErrorCode` per #398.
"""

from __future__ import annotations

from ..errors import AeatError


class RentalRegisterError(AeatError):
    """Base error for the rental-register subpackage."""


class FincaNotFoundError(RentalRegisterError):
    """Raised when a referenced finca id is not present in the register."""


class ContractNotFoundError(RentalRegisterError):
    """Raised when a referenced rental contract id is not present in the register."""


class TierResolutionError(RentalRegisterError):
    """Raised when contract metadata is inconsistent and a tier cannot be resolved.

    Examples: ``tenant_min_age > tenant_max_age``,
    ``qualifying_co_tenant_count > tenant_count`` (also enforced at
    DB level), or a tier-90-a candidate with no prior-contract data.
    """


class AmortizationLedgerCapExceededError(RentalRegisterError):
    """Raised in strict mode when cumulative amortización would exceed the cap.

    Default ``compute_amortization_for_year`` clamps to the remaining
    cap and never raises. Strict callers (e.g. preflight verifiers
    that want to flag the surface) opt in via ``strict=True``.
    """


class AnexoCAggregationError(RentalRegisterError):
    """Raised when the rental register cannot produce coherent Anexo C aggregates.

    Surface causes: contract referencing a non-existent finca; income
    record without a contract; ledger entry whose
    ``cumulative_amortization_through_year`` is out of order with
    surrounding entries (re-stated mid-year accrual without a prior
    recompute).
    """


__all__ = [
    "AmortizationLedgerCapExceededError",
    "AnexoCAggregationError",
    "ContractNotFoundError",
    "FincaNotFoundError",
    "RentalRegisterError",
    "TierResolutionError",
]
