"""Application-level provider contracts and selection for AEAT auth."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from ._catalogue import (
    AUTH_PROVIDER_CATALOGUE,
    AuthProviderAvailability,
    AuthProviderListing,
    get_auth_provider,
    implemented_auth_providers,
    list_auth_providers,
    research_only_auth_providers,
)

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class AuthProviderKind(StrEnum):
    """Closed enumeration of supported AEAT authentication providers.

    Attributes:
        CERTIFICATE: PKCS#12 client certificate (FNMT-RCM and equivalents).
        CLAVE_MOVIL: ``Cl@ve`` Móvil push-approval flow.
    """

    CERTIFICATE = "certificate"
    CLAVE_MOVIL = "clave_movil"


class AuthProviderDescription(BaseModel):
    """Operator-facing description of one configured auth provider.

    Attributes:
        kind: Identifier of the provider.
        label: Human-readable provider name.
        configured: Whether the provider's required settings are present.
        available: Whether a session can currently be established.
        identity_nif: NIF resolved by the provider, when known.
        subject: Subject DN or equivalent identity string.
        expires_on: Expiry date for the underlying credential.
        health_severity: Provider-specific health classification.
        days_until_expiry: Convenience countdown to ``expires_on``.
        health_summary: Short human-readable diagnostic.
    """

    model_config = _STRICT_FROZEN

    kind: AuthProviderKind
    label: str = Field(min_length=1)
    configured: bool
    available: bool
    identity_nif: str | None = None
    subject: str | None = None
    expires_on: date | None = None
    health_severity: str | None = None
    days_until_expiry: int | None = None
    health_summary: str | None = None


@runtime_checkable
class AuthProvider(Protocol):
    """Protocol every concrete AEAT auth provider satisfies.

    Implementations live under :mod:`aeat.adapters.outbound.aeat.auth`
    and are dispatched by :func:`select_provider`.
    """

    kind: AuthProviderKind

    async def authenticate(
        self,
        *,
        browser_session: Any | None = None,
        target_url: str | None = None,
    ) -> Any:
        """Establish an authenticated session and return the provider's session record."""
        ...

    async def verify(
        self,
        session: Any,
        *,
        target_url: str | None = None,
    ) -> Any:
        """Re-probe ``session`` against ``target_url`` and return the provider's assertion record."""
        ...

    def describe(self) -> AuthProviderDescription:
        """Return a safe, log-friendly summary of the provider's configured state."""
        ...


def describe_provider_operator_impact(description: AuthProviderDescription) -> str:
    """Return a one-paragraph operator-facing summary of how ``description`` affects the workflow.

    Used by ``aeat auth list-providers`` to render a human-readable
    diagnostic. The string focuses on what the operator can and cannot
    do given the current provider configuration; never contains
    secrets.
    """
    if not description.configured:
        return (
            "The operator can still produce, verify, and export filings locally, but "
            "AEAT-backed reads stay unavailable until an auth provider is configured."
        )
    if not description.available:
        return (
            f"{description.label} is configured but not ready yet. The operator can still "
            "produce, verify, and export filings locally, but AEAT-backed reads "
            "stay unavailable until auth is fixed."
        )
    if description.kind == AuthProviderKind.CERTIFICATE:
        return (
            "Certificate auth is ready. The operator keeps the same CLI filing flow for "
            "AEAT-backed reads, and future providers can plug into the same "
            "commands without changing the workflow."
        )
    return (
        f"{description.label} is ready. The operator keeps the same CLI filing flow while "
        "this provider plugs into the shared auth protocol."
    )


__all__ = [
    "AUTH_PROVIDER_CATALOGUE",
    "AuthProvider",
    "AuthProviderAvailability",
    "AuthProviderDescription",
    "AuthProviderKind",
    "AuthProviderListing",
    "describe_provider_operator_impact",
    "get_auth_provider",
    "implemented_auth_providers",
    "list_auth_providers",
    "research_only_auth_providers",
]
