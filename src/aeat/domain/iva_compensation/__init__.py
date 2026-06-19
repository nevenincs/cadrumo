"""IVA-compensation domain: pure carry-forward, reconciliation, and balance logic.

This package owns the regulatory carry-forward projection (Modelo 303 four-year
compensation window), the wallet reconciliation decision logic, and the wallet
balance projection, plus their typed guard errors. Repositories, event stores,
and orchestration that wire these pure pieces to persistence remain in the
application layer.
"""

from __future__ import annotations

from ._balance import (
    IvaWalletBalanceReport,
    build_iva_wallet_balance_report,
)
from ._carry_forward import (
    IvaCompensationCarryForwardLot,
    IvaCompensationCarryForwardReport,
    IvaCompensationExpiryReviewState,
    IvaCompensationPeriodState,
    build_iva_compensation_carry_forward_report,
    derive_303_compensation_available,
    enforce_iva_compensation_four_year_window,
)
from ._errors import (
    IvaCompensationCarryForwardPolicyError,
    IvaCompensationDecimalParseError,
    IvaCompensationReconciliationInputError,
    IvaCompensationSeedConflictError,
    IvaCompensationYearRangeError,
)
from ._reconciliation import (
    IvaCompensationOverride,
)

__all__ = [
    "IvaCompensationCarryForwardLot",
    "IvaCompensationCarryForwardPolicyError",
    "IvaCompensationCarryForwardReport",
    "IvaCompensationDecimalParseError",
    "IvaCompensationExpiryReviewState",
    "IvaCompensationOverride",
    "IvaCompensationPeriodState",
    "IvaCompensationReconciliationInputError",
    "IvaCompensationSeedConflictError",
    "IvaCompensationYearRangeError",
    "IvaWalletBalanceReport",
    "build_iva_compensation_carry_forward_report",
    "build_iva_wallet_balance_report",
    "derive_303_compensation_available",
    "enforce_iva_compensation_four_year_window",
]
