"""Typed catalogue for ``aeat config auth providers``.

:class:`AuthProviderListing` records feed :data:`AUTH_PROVIDER_CATALOGUE`; the
query helpers expose implemented and reserved provider ids to the operator
auth command surface.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ...core.i18n import Translatable as tr
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN

"""Shared :class:`pydantic.ConfigDict` enforcing strict, frozen, no-extras."""


class AuthProviderListing(BaseModel):
    """One row in the ``aeat config auth providers`` catalogue.

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
    implemented: bool = True


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
    AuthProviderListing(
        id="clave_pin",
        label=tr("auth.catalogue.clave_pin_label"),
        description=tr("auth.catalogue.clave_pin_description"),
        implemented=False,
    ),
    AuthProviderListing(
        id="clave_permanente",
        label=tr("auth.catalogue.clave_permanente_label"),
        description=tr("auth.catalogue.clave_permanente_description"),
    ),
    AuthProviderListing(
        id="dnie_pkcs",
        label=tr("auth.catalogue.dnie_pkcs_label"),
        description=tr("auth.catalogue.dnie_pkcs_description"),
        implemented=False,
    ),
)
"""Catalogue of auth provider entries in display order."""


def list_auth_providers() -> tuple[AuthProviderListing, ...]:
    """Return the auth provider catalogue.

    Wraps :data:`AUTH_PROVIDER_CATALOGUE` so callers have a stable
    function-call site.

    Returns a tuple of :class:`AuthProviderListing` entries.
    """
    return AUTH_PROVIDER_CATALOGUE


def implemented_auth_provider_ids() -> tuple[str, ...]:
    """Return provider ids accepted by auth commands that need an implementation."""
    return tuple(entry.id for entry in AUTH_PROVIDER_CATALOGUE if entry.implemented)


def known_auth_provider_ids() -> tuple[str, ...]:
    """Return every recognized provider id, including reserved slots."""
    return tuple(entry.id for entry in AUTH_PROVIDER_CATALOGUE)


def get_auth_provider(provider_id: str) -> AuthProviderListing:
    """Resolve a provider id to its catalogue listing.

    Provider ids are exact. Retired spellings and unavailable providers
    are rejected instead of being carried as alternate paths.

    Args:
        provider_id: The provider identifier to look up (case-insensitive,
            leading/trailing whitespace stripped before comparison).

    Returns:
        The matching :class:`AuthProviderListing` from the catalogue.

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
    "implemented_auth_provider_ids",
    "known_auth_provider_ids",
    "list_auth_providers",
]
