"""Domain errors for the contribuyente tax-residence profile and ledgers.

Defines :class:`TaxResidenceProfileError` and its concrete failures
surfaced to RENTA verification, plus the asset/inventory/amortizacion
ledger error hierarchy (:class:`AssetRecordError`,
:class:`InventoryLedgerError`, :class:`AmortizacionLedgerError` and their
subclasses). Every class derives from :class:`aeat.core.errors.AeatError`
so the shared error-code registration hook applies.
"""

from __future__ import annotations

from ...core.errors import AeatError, CoreError, CoreValidationError


class TaxResidenceProfileError(AeatError):
    """Base class for tax-residence profile failures.

    Concrete subclasses (:class:`ProfileNotConfiguredError`,
    :class:`ForalRegimeError`) carry their own translated messages and
    suggestions; this base type exists only so callers can catch the
    family with a single ``except`` clause.
    """


class ProfileNotConfiguredError(TaxResidenceProfileError):
    """Raised when RENTA verification needs a tax-residence profile.

    Attached to a ``suggestion`` pointing the operator at the profile
    edit wizard.
    """

    def __init__(self) -> None:
        """Build the multilingual no-profile-configured error."""
        super().__init__(
            "No tax-residence profile is configured for RENTA.",
            translated_message="profile.errors.not_configured",
            suggestion="aeat config profile edit NAME --tax-residence-ccaa <ccaa>",
        )


class ForalRegimeError(TaxResidenceProfileError):
    """Raised when the user selects a foral regime not modelled by this profile.

    Attributes:
        value: The foral CCAA identifier supplied by the caller.
    """

    def __init__(self, value: str) -> None:
        """Build the multilingual foral-regime-out-of-scope error."""
        super().__init__(
            f"{value!r} is a foral regime outside the scope of this profile.",
            context={"tax_region": value},
            translated_message="profile.errors.foral_regime",
        )
        self.value = value


class ProfileValidationError(TaxResidenceProfileError, ValueError):
    """Raised when profile records violate state or shape invariants.

    Inherits from ValueError to maintain compatibility with Pydantic
    validators.
    """


class ProfileKeysRegistrationError(CoreError):
    """Raised when profile keys are registered a second time with a conflicting tuple.

    The profile-key registry is single-writer: the first registration wins.
    A second call that supplies a different tuple is a programming error;
    this typed exception replaces the bare ``RuntimeError`` so callers can
    catch it precisely and the error surfaces in the central registry.
    """

    def __init__(self) -> None:
        """Build the profile-keys-already-registered error."""
        super().__init__(
            "profile keys already registered with a different tuple",
            context={"registry": "profile._keys"},
        )


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
    "ForalRegimeError",
    "InventoryLedgerError",
    "InventoryValidationError",
    "LIFOForbiddenError",
    "ProfileKeysRegistrationError",
    "ProfileNotConfiguredError",
    "ProfileValidationError",
    "TaxResidenceProfileError",
]
