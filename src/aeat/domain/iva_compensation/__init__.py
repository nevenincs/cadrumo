"""IVA-compensation domain: pure carry-forward, reconciliation, and balance logic.

This package owns the regulatory carry-forward projection (Modelo 303 four-year
compensation window), the wallet reconciliation decision logic, and the wallet
balance projection, plus their typed guard errors. Repositories, event stores,
and orchestration that wire these pure pieces to persistence remain in the
application layer.
"""

from __future__ import annotations

from ._errors import (
    IvaCompensationCarryForwardPolicyError,
    IvaCompensationDecimalParseError,
    IvaCompensationReconciliationInputError,
    IvaCompensationSeedConflictError,
    IvaCompensationYearRangeError,
)

__all__ = [
    "IvaCompensationCarryForwardPolicyError",
    "IvaCompensationDecimalParseError",
    "IvaCompensationReconciliationInputError",
    "IvaCompensationSeedConflictError",
    "IvaCompensationYearRangeError",
]
