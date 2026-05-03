"""Typed catalogue for ``aeat setup auth providers``."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ...core.i18n import Translatable, TranslationError, require_authoritative

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")
"""Shared :class:`pydantic.ConfigDict` enforcing strict, frozen, no-extras."""


class AuthProviderAvailability(StrEnum):
    """Closed catalogue of auth-provider availability states.

    Attributes:
        AVAILABLE: A backend adapter exists; the provider can be
            configured, login can run, and identity can be probed.
        UNAVAILABLE: The provider is known but cannot be configured or
            used for login.
    """

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class AuthProviderListing(BaseModel):
    """One row in the ``aeat setup auth providers`` catalogue.

    Attributes:
        id: Stable lowercase identifier (``"certificate"``,
            ``"clave-movil"``, ``"clave-permanente"``). The CLI passes
            this verbatim through ``--provider``; the configure /
            login commands resolve it against the backend registry.
        label: Multilingual display label, Spanish authoritative.
        availability: Closed :class:`AuthProviderAvailability`.
        description: Multilingual one-paragraph operator-facing
            description.
    """

    model_config = _STRICT_FROZEN

    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_-]*$")
    label: Translatable
    availability: AuthProviderAvailability
    description: Translatable

    @field_validator("label", "description")
    @classmethod
    def _require_authoritative(cls, value: Translatable) -> Translatable:
        """Reject listings whose label or description omits authoritative Spanish."""
        try:
            require_authoritative(value, domain="aeat")
        except TranslationError as exc:
            raise ValueError(str(exc)) from exc
        return value


_CERTIFICATE_LABEL: Translatable = {
    "es": "Certificado digital",
    "en": "Digital certificate",
    "ca": "Certificat digital",
    "hu": "Digitális tanúsítvány",
}

_CERTIFICATE_DESCRIPTION: Translatable = {
    "es": (
        "Autenticación basada en un certificado X.509 (FNMT-RCM u "
        "otra autoridad reconocida). Compatible con todos los flujos "
        "de la sede electrónica."
    ),
    "en": ("X.509 client certificate authentication (FNMT-RCM or any recognised authority). Supports every Sede flow."),
    "ca": (
        "Autenticació basada en certificat X.509 (FNMT-RCM o una "
        "altra autoritat reconeguda). Compatible amb tots els fluxos "
        "de la seu electrònica."
    ),
    "hu": (
        "X.509 ügyféltanúsítvány-alapú hitelesítés (FNMT-RCM vagy "
        "más elismert hatóság). A Sede minden folyamatát támogatja."
    ),
}

_CLAVE_MOVIL_LABEL: Translatable = {
    "es": "Cl@ve Móvil",
    "en": "Cl@ve Móvil",
    "ca": "Cl@ve Móvil",
    "hu": "Cl@ve Móvil",
}

_CLAVE_MOVIL_DESCRIPTION: Translatable = {
    "es": (
        "Autenticación con aprobación push en el móvil del titular "
        "registrado en Cl@ve. Requiere DNI/NIE, registro en Cl@ve, y "
        "el dispositivo emparejado."
    ),
    "en": (
        "Push-approval authentication via the holder's phone "
        "registered with Cl@ve. Requires DNI/NIE, Cl@ve enrolment, "
        "and a paired device."
    ),
    "ca": (
        "Autenticació amb aprovació push al mòbil del titular "
        "registrat a Cl@ve. Requereix DNI/NIE, registre a Cl@ve i el "
        "dispositiu vinculat."
    ),
    "hu": (
        "Cl@ve-rendszerben regisztrált mobilon megjelenő "
        "push-jóváhagyásos hitelesítés. DNI/NIE, Cl@ve-regisztráció és "
        "párosított készülék szükséges."
    ),
}

_CLAVE_PERMANENTE_LABEL: Translatable = {
    "es": "Cl@ve Permanente",
    "en": "Cl@ve Permanente",
    "ca": "Cl@ve Permanente",
    "hu": "Cl@ve Permanente",
}

_CLAVE_PERMANENTE_DESCRIPTION: Translatable = {
    "es": (
        "Autenticación con usuario, contraseña reforzada y código SMS "
        "de Cl@ve Permanente. No está disponible en esta instalación; "
        "``configure`` y ``login`` se rechazan."
    ),
    "en": (
        "Username + reinforced-password + SMS authentication via "
        "Cl@ve Permanente. Not available in this installation, so "
        "``configure`` and ``login`` refuse the provider."
    ),
    "ca": (
        "Autenticació amb usuari, contrasenya reforçada i codi SMS de "
        "Cl@ve Permanente. No està disponible en aquesta instal·lació, "
        "així que ``configure`` i ``login`` es rebutgen."
    ),
    "hu": (
        "Cl@ve Permanente felhasználónév + megerősített jelszó + "
        "SMS-kód alapú hitelesítés. Ebben a telepítésben nem érhető el, "
        "ezért a ``configure`` és ``login`` parancsokat elutasítja."
    ),
}


AUTH_PROVIDER_CATALOGUE: tuple[AuthProviderListing, ...] = (
    AuthProviderListing(
        id="certificate",
        label=_CERTIFICATE_LABEL,
        availability=AuthProviderAvailability.AVAILABLE,
        description=_CERTIFICATE_DESCRIPTION,
    ),
    AuthProviderListing(
        id="clave-movil",
        label=_CLAVE_MOVIL_LABEL,
        availability=AuthProviderAvailability.AVAILABLE,
        description=_CLAVE_MOVIL_DESCRIPTION,
    ),
    AuthProviderListing(
        id="clave-permanente",
        label=_CLAVE_PERMANENTE_LABEL,
        availability=AuthProviderAvailability.UNAVAILABLE,
        description=_CLAVE_PERMANENTE_DESCRIPTION,
    ),
)
"""Catalogue of auth provider entries in display order."""


def list_auth_providers() -> tuple[AuthProviderListing, ...]:
    """Return the auth provider catalogue.

    Wraps :data:`AUTH_PROVIDER_CATALOGUE` so callers have a stable
    function-call site.
    """
    return AUTH_PROVIDER_CATALOGUE


def get_auth_provider(provider_id: str) -> AuthProviderListing:
    """Resolve a provider id to its catalogue listing.

    Supports both hyphens (canonical) and underscores (legacy alias).

    Raises:
        KeyError: When ``provider_id`` is not in the catalogue. The
            CLI's configure / login commands catch this and render
            an operator-facing "unknown provider" error.
    """
    pid = provider_id.strip().lower().replace("_", "-")
    for entry in AUTH_PROVIDER_CATALOGUE:
        if entry.id == pid:
            return entry
    raise KeyError(provider_id)


def available_auth_providers() -> tuple[AuthProviderListing, ...]:
    """Return only catalogue entries that can be configured and used."""
    return tuple(entry for entry in AUTH_PROVIDER_CATALOGUE if entry.availability is AuthProviderAvailability.AVAILABLE)


def unavailable_auth_providers() -> tuple[AuthProviderListing, ...]:
    """Return only catalogue entries that cannot be used."""
    return tuple(
        entry for entry in AUTH_PROVIDER_CATALOGUE if entry.availability is AuthProviderAvailability.UNAVAILABLE
    )


__all__ = [
    "AUTH_PROVIDER_CATALOGUE",
    "AuthProviderAvailability",
    "AuthProviderListing",
    "available_auth_providers",
    "get_auth_provider",
    "list_auth_providers",
    "unavailable_auth_providers",
]
