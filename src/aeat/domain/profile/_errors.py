"""Domain errors for the contribuyente tax-residence profile.

Defines :class:`TaxResidenceProfileError` and the two concrete failures
surfaced to RENTA verification — :class:`ProfileNotConfiguredError`
when no profile is set, and :class:`ForalRegimeError` when the user
selects a foral regime that this profile shape does not model.
"""

from __future__ import annotations

from ...core.errors import AeatError, CoreError


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


__all__ = [
    "ForalRegimeError",
    "ProfileKeysRegistrationError",
    "ProfileNotConfiguredError",
    "ProfileValidationError",
    "TaxResidenceProfileError",
]
