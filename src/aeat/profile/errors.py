"""Profile-ledger error hierarchy."""

from __future__ import annotations

from ..errors import AeatError


class AssetRecordError(AeatError):
    """Raised when an asset record is structurally invalid."""


class AmortizationLedgerError(AeatError):
    """Raised when an amortization ledger operation is invalid."""


class InventoryLedgerError(AeatError):
    """Raised when an inventory ledger operation is invalid."""


class LIFOForbiddenError(InventoryLedgerError):
    """Raised when a caller attempts LIFO inventory valuation."""

    def __init__(self, method: str = "lifo") -> None:
        """Construct a refusal citing the LIS art. 17 valuation boundary.

        Args:
            method: User-supplied valuation method.
        """

        super().__init__(
            "LIFO valuation is not admitted for this tax ledger; use FIFO, PMP, or coste_medio per LIS art. 17.1.",
            context={"method": method, "legal_basis": "LIS art. 17.1"},
        )


class BasisCapExceededError(AmortizationLedgerError):
    """Raised when cumulative amortization would exceed cost basis."""


__all__ = [
    "AmortizationLedgerError",
    "AssetRecordError",
    "BasisCapExceededError",
    "InventoryLedgerError",
    "LIFOForbiddenError",
]
