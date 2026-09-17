"""Domain errors for the contribuyente tax-residence profile.

Defines :class:`TaxResidenceProfileError` and its concrete failures surfaced
to RENTA verification. The inventory ledger error hierarchy lives with its
records in :mod:`domain.contribuyente.inventory`. Every class derives from
:class:`core.errors.hierarchy.CadrumoError` so the shared error-code registration hook
applies.
"""

from __future__ import annotations

from ...core.errors.hierarchy import CadrumoError


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


class ProfileValidationError(TaxResidenceProfileError):
    """Raised when profile records violate state or shape invariants.

    Its canonical registered ancestry is :class:`TaxResidenceProfileError`.
    Pydantic validators translate this registered failure to ``ValueError`` at
    their narrow boundary.
    """


__all__ = [
    "ForalRegimeError",
    "ProfileNotConfiguredError",
    "ProfileValidationError",
    "TaxResidenceProfileError",
]
