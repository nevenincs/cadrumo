"""Typed catalogue for ``aeat setup auth providers``."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ...core.i18n import Translatable as tr  # noqa: N813

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")
"""Shared :class:`pydantic.ConfigDict` enforcing strict, frozen, no-extras."""


class AuthProviderListing(BaseModel):
    """One row in the ``aeat setup auth providers`` catalogue.

    Attributes:
        id: Stable lowercase identifier (``"certificate"``,
            ``"clave_movil"``). The CLI passes this verbatim through
            ``--provider``; the configure / login commands resolve it
            against the backend registry.
        label: Translation key for display label.
        description: Translation key for one-paragraph operator-facing
            description.
    """

    model_config = _STRICT_FROZEN

    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_-]*$")
    label: tr
    description: tr


AUTH_PROVIDER_CATALOGUE: tuple[AuthProviderListing, ...] = (
    AuthProviderListing(
        id="certificate",
        label=tr("auth.catalogue.certificate_label"),
        description=tr("auth.catalogue.certificate_description"),
    ),
    AuthProviderListing(
        id="clave_movil",
        label=tr("auth.catalogue.clave_movil_label"),
        description=tr("auth.catalogue.clave_movil_description"),
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

    Provider ids are exact. Legacy spellings and unavailable providers
    are rejected instead of being carried as compatibility paths.

    Raises:
        KeyError: When ``provider_id`` is not in the catalogue. The
            CLI's configure / login commands catch this and render
            an operator-facing "unknown provider" error.
    """
    pid = provider_id.strip().lower()
    for entry in AUTH_PROVIDER_CATALOGUE:
        if entry.id == pid:
            return entry
    raise KeyError(provider_id)


__all__ = [
    "AUTH_PROVIDER_CATALOGUE",
    "AuthProviderListing",
    "get_auth_provider",
    "list_auth_providers",
]
