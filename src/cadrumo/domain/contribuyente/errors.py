"""Domain errors for the contribuyente tax-residence profile.

Defines :class:`TaxResidenceProfileError` and its concrete failures
surfaced to RENTA verification, plus :class:`ProfileKeysRegistrationError`
for the profile-key registry. The ledger error hierarchies live with their
records in :mod:`domain.contribuyente.assets` (asset) and
:mod:`domain.contribuyente.inventory` (inventory and amortizacion). Every
class derives from :class:`core.errors.CadrumoError` so the shared
error-code registration hook applies.
"""

from __future__ import annotations

from ...core.errors.hierarchy import CadrumoError, CoreError


class TaxResidenceProfileError(CadrumoError):
    """Base class for tax-residence profile failures.

    Concrete subclasses (:class:`ProfileNotConfiguredError`,
    :class:`ForalRegimeError`) carry their own translated messages and
    suggestions; this base type exists only so callers can catch the
    family with a single ``except`` clause.
    """


class ProfileNotConfiguredError(TaxResidenceProfileError):
    """Raised when RENTA verification needs a tax-residence profile."""

    def __init__(self) -> None:
        """Build the multilingual no-profile-configured error."""
        super().__init__(
            "No tax-residence profile is configured for RENTA.",
            translated_message="profile.errors.not_configured",
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
    """Raised on a profile-key registry invariant violation.

    Two cases share this typed exception (registered once centrally): a second
    registration with a conflicting tuple (the registry is single-writer, first
    registration wins), or an access before any registration — a programming /
    import-order error meaning the wizard catalogue
    (:mod:`application.wizard`) was not imported at startup to push the
    compiled keys via :func:`register_profile_keys`. Replaces a bare
    ``RuntimeError`` so callers can catch it precisely and the failure surfaces
    in the central registry.
    """

    def __init__(self, message: str = "profile keys already registered with a different tuple") -> None:
        """Build the profile-keys registry-invariant error."""
        super().__init__(
            message,
            context={"registry": "profile._keys"},
        )


__all__ = [
    "ForalRegimeError",
    "ProfileKeysRegistrationError",
    "ProfileNotConfiguredError",
    "ProfileValidationError",
    "TaxResidenceProfileError",
]
