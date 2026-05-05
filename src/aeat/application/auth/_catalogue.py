"""Typed catalogue for ``aeat setup auth providers``."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from ...core.i18n import Translatable as tr  # noqa: N813

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
        label: Translation key for display label.
        availability: Closed :class:`AuthProviderAvailability`.
        description: Translation key for one-paragraph operator-facing
            description.
    """

    model_config = _STRICT_FROZEN

    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_-]*$")
    label: tr
    availability: AuthProviderAvailability
    description: tr


AUTH_PROVIDER_CATALOGUE: tuple[AuthProviderListing, ...] = (
    AuthProviderListing(
        id="certificate",
        label=tr("auth.catalogue.certificate_label"),
        availability=AuthProviderAvailability.AVAILABLE,
        description=tr("auth.catalogue.certificate_description"),
    ),
    AuthProviderListing(
        id="clave-movil",
        label=tr("auth.catalogue.clave_movil_label"),
        availability=AuthProviderAvailability.AVAILABLE,
        description=tr("auth.catalogue.clave_movil_description"),
    ),
    AuthProviderListing(
        id="clave-permanente",
        label=tr("auth.catalogue.clave_permanente_label"),
        availability=AuthProviderAvailability.UNAVAILABLE,
        description=tr("auth.catalogue.clave_permanente_description"),
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
