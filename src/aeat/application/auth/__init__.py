"""Provider-agnostic AEAT auth contracts and the provider factory.

Concrete provider implementations (certificate, Cl@ve Móvil) live in
``aeat.adapters.outbound.aeat.auth``.  This module owns only the
abstract surface that use-case code depends on, keeping the application
layer free of adapter-level imports at runtime.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from ...adapters.outbound.aeat.auth._authenticator import (
        AeatLoginAssertion,
        AeatSession,
        BrowserSessionFactory,
        BrowserSessionLike,
    )
    from ...core.config import Settings

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class AuthProviderKind(StrEnum):
    """Closed catalogue of AEAT auth-provider identifiers."""

    CERTIFICATE = "certificate"
    CLAVE_PERMANENTE = "clave_permanente"
    CLAVE_MOVIL = "clave_movil"
    CLAVE_PIN = "clave_pin"


class AuthProviderDescription(BaseModel):
    """Safe, loggable description of one auth provider's current state."""

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
    """Provider-agnostic protocol for AEAT authentication."""

    kind: AuthProviderKind

    async def authenticate(
        self,
        *,
        browser_session: BrowserSessionLike | None = None,
        target_url: str | None = None,
    ) -> AeatSession: ...

    async def verify(
        self,
        session: AeatSession,
        *,
        target_url: str | None = None,
    ) -> AeatLoginAssertion: ...

    def describe(self) -> AuthProviderDescription: ...


def describe_provider_operator_impact(description: AuthProviderDescription) -> str:
    """Explain what ``description`` means for Kent's CLI workflow today."""

    if not description.configured:
        return (
            "Kent can still produce, verify, and export filings locally, but "
            "AEAT-backed reads stay unavailable until an auth "
            "provider is configured."
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
    settings: Settings,
    browser_session_factory: BrowserSessionFactory | None = None,
) -> AuthProvider:
    """Return the configured auth-provider implementation for ``kind``.

    Today the certificate-backed provider and Cl@ve Móvil are concrete.
    Cl@ve Permanente and Cl@ve PIN are NOT offered by AEAT Sede
    Electrónica today — see
    ``.vault/reference/2026-04-21-clave-portal-reference.md`` for the
    live portal capture that confirmed only Cl@ve Móvil + Certificate
    are exposed on the ``SelectorAccesos.html`` chooser.
    """
    if kind is AuthProviderKind.CERTIFICATE:
        from ...adapters.outbound.aeat.auth._authenticator import AeatAuthenticator

        return AeatAuthenticator(
            settings,
            browser_session_factory=browser_session_factory,
        )
    if kind is AuthProviderKind.CLAVE_MOVIL:
        from ...adapters.outbound.aeat.auth._clave_movil import ClaveMovilAuthProvider

        return ClaveMovilAuthProvider(
            settings,
            browser_session_factory=browser_session_factory,
        )
    if kind is AuthProviderKind.CLAVE_PERMANENTE:
        raise NotImplementedError(
            "auth provider 'clave_permanente' is not offered by AEAT Sede Electrónica today; "
            "use clave_movil (push approval via the Cl@ve app) or certificate."
        )
    raise NotImplementedError(f"auth provider {kind.value!r} is not implemented yet")


__all__ = [
    "AuthProvider",
    "AuthProviderDescription",
    "AuthProviderKind",
    "describe_provider_operator_impact",
    "select_provider",
]
