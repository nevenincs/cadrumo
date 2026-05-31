"""Profile-ledger error hierarchy.

Errors for the asset ledger (:mod:`aeat.domain.profile.assets`) and
inventory ledger (:mod:`aeat.domain.profile.inventory`). Every class
ultimately derives from :class:`aeat.core.errors.AeatError` so the
shared error-code registration hook applies.
"""

from __future__ import annotations

from ...core.errors import AeatError, CoreValidationError


class AssetRecordError(AeatError):
    """Raised when an asset record is structurally invalid."""


class AssetValidationError(AssetRecordError, ValueError):
    """Raised when an asset record fails Pydantic validation."""


class AmortizacionLedgerError(AeatError):
    """Raised when an amortizacion ledger operation is invalid."""


class InventoryLedgerError(AeatError):
    """Raised when an inventory ledger operation is invalid."""


class InventoryValidationError(InventoryLedgerError, CoreValidationError):
    """Raised when an inventory ledger fails Pydantic validation.

    Inherits from CoreValidationError (which itself inherits from CoreError
    and ValueError) to participate in the shared CoreValidationError catch
    surface and remain compatible with pydantic validators.
    """


class LIFOForbiddenError(InventoryLedgerError):
    """Raised when a caller attempts LIFO inventory valuation.

    LIS art. 17.1 does not admit LIFO for tax-purpose stock valuation
    in this regime; the message routes the operator to FIFO, PMP, or
    coste medio.
    """

    def __init__(self, method: str = "lifo") -> None:
        """Construct a refusal citing the LIS art. 17 valuation boundary.

        Args:
            method: User-supplied valuation method.
        """
        super().__init__(
            "LIFO valuation is not admitted for this tax ledger; use FIFO, PMP, or coste_medio per LIS art. 17.1.",
            context={"method": method, "legal_basis": "LIS art. 17.1"},
        )


class BasisCapExceededError(AmortizacionLedgerError):
    """Raised when cumulative amortization would exceed cost basis."""


__all__ = [
    "AmortizacionLedgerError",
    "AssetRecordError",
    "AssetValidationError",
    "BasisCapExceededError",
    "InventoryLedgerError",
    "InventoryValidationError",
    "LIFOForbiddenError",
]
