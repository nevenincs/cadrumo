"""Application-level provider contracts and selection for AEAT auth."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from ...core.config import Settings

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class AuthProviderKind(StrEnum):
    CERTIFICATE = "certificate"
    CLAVE_PERMANENTE = "clave_permanente"
    CLAVE_MOVIL = "clave_movil"
    CLAVE_PIN = "clave_pin"


class AuthProviderDescription(BaseModel):
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
    kind: AuthProviderKind

    async def authenticate(
        self,
        *,
        browser_session: Any | None = None,
        target_url: str | None = None,
    ) -> Any: ...

    async def verify(
        self,
        session: Any,
        *,
        target_url: str | None = None,
    ) -> Any: ...

    def describe(self) -> AuthProviderDescription: ...


def describe_provider_operator_impact(description: AuthProviderDescription) -> str:
    if not description.configured:
        return (
            "Kent can still produce, verify, and export filings locally, but "
            "AEAT-backed reads stay unavailable until an auth provider is configured."
        )
    if not description.available:
        return (
            f"{description.label} is configured but not ready yet. Kent can still "
            "produce, verify, and export filings locally, but AEAT-backed reads "
            "stay unavailable until auth is fixed."
        )
    if description.kind == AuthProviderKind.CERTIFICATE:
        return (
            "Certificate auth is ready. Kent keeps the same CLI filing flow for "
            "AEAT-backed reads, and future providers can plug into the same "
            "commands without changing the workflow."
        )
    return (
        f"{description.label} is ready. Kent keeps the same CLI filing flow while "
        "this provider plugs into the shared auth protocol."
    )


def select_provider(
    kind: AuthProviderKind,
    *,
    settings,
    browser_session_factory=None,
) -> AuthProvider:
    from ...adapters.outbound.aeat.auth import select_provider as _select_outbound_provider

    return _select_outbound_provider(
        kind,
        settings=settings,
        browser_session_factory=browser_session_factory,
    )


__all__ = [
    "AuthProvider",
    "AuthProviderDescription",
    "AuthProviderKind",
    "describe_provider_operator_impact",
    "select_provider",
]
