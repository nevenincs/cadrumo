"""Domain errors for the contribuyente tax-residence profile.

Defines :class:`TaxResidenceProfileError` and the two concrete failures
surfaced to RENTA verification — :class:`ProfileNotConfiguredError`
when no profile is set, and :class:`ForalRegimeError` when the user
selects a foral regime that this profile shape does not model.
"""

from __future__ import annotations

from ...core.errors import AeatError
from ...core.i18n import Translatable


class TaxResidenceProfileError(AeatError):
    """Base class for tax-residence profile failures.

    Concrete subclasses (:class:`ProfileNotConfiguredError`,
    :class:`ForalRegimeError`) carry their own translated messages and
    suggestions; this base type exists only so callers can catch the
    family with a single ``except`` clause.
    """


class ProfileNotConfiguredError(TaxResidenceProfileError):
    """Raised when RENTA verification needs a tax-residence profile.

    Attached to a ``suggestion`` pointing the operator at
    ``aeat profile set tax-region <ccaa>``.
    """

    def __init__(self) -> None:
        """Build the multilingual no-profile-configured error."""
        message: Translatable = {
            "es": "No hay perfil de residencia fiscal configurado para RENTA.",
            "en": "No tax-residence profile is configured for RENTA.",
            "hu": "Nincs beallitva RENTA adoilletosegi profil.",
        }
        super().__init__(
            "No tax-residence profile is configured for RENTA.",
            translated_message=message,
            suggestion="aeat profile set tax-region <ccaa>",
        )


class ForalRegimeError(TaxResidenceProfileError):
    """Raised when the user selects a foral regime not modelled by this profile.

    Attributes:
        value: The foral CCAA identifier supplied by the caller.
    """

    def __init__(self, value: str) -> None:
        """Build the multilingual foral-regime-out-of-scope error."""
        message: Translatable = {
            "es": f"{value!r} es un regimen foral fuera del alcance de este perfil.",
            "en": f"{value!r} is a foral regime outside the scope of this profile.",
            "hu": f"{value!r} foralis rendszer, e profil hatokoren kivul.",
        }
        super().__init__(
            f"{value!r} is a foral regime outside the scope of this profile.",
            context={"tax_region": value},
            translated_message=message,
        )
        self.value = value


__all__ = [
    "ForalRegimeError",
    "ProfileNotConfiguredError",
    "TaxResidenceProfileError",
]
