"""Domain errors for Kent's tax-residence profile."""

from __future__ import annotations

from ...core.errors import AeatError
from ...core.i18n import Translatable


class TaxResidenceProfileError(AeatError):
    """Base class for tax-residence profile failures."""


class ProfileNotConfiguredError(TaxResidenceProfileError):
    """Raised when RENTA verification needs a tax-residence profile."""

    def __init__(self) -> None:
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
    """Raised when the user selects a foral regime handled by issue #424."""

    def __init__(self, value: str) -> None:
        message: Translatable = {
            "es": f"{value!r} es un regimen foral fuera de este perfil; seguimiento en #424.",
            "en": f"{value!r} is a foral regime outside this profile; tracked in #424.",
            "hu": f"{value!r} foralis rendszer, ezen profilon kivul; kovetes: #424.",
        }
        super().__init__(
            f"{value!r} is a foral regime outside this profile; tracked in #424.",
            context={"tax_region": value, "issue": "#424"},
            translated_message=message,
        )
        self.value = value


__all__ = [
    "ForalRegimeError",
    "ProfileNotConfiguredError",
    "TaxResidenceProfileError",
]
