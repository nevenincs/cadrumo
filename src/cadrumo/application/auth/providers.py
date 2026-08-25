"""Application-owned authentication provider contract and selection service."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from ...core import AuthProviderDescription, AuthProviderKind
from ..auth_credentials import ActiveCertificateCredentials
from .credentials import resolve_active_certificate_credentials

if TYPE_CHECKING:
    from ...adapters.outbound.aeat.auth import AeatLoginAssertion, AeatSession, BrowserSessionFactory
    from ...core.config import Settings


@runtime_checkable
class AuthProvider(Protocol):
    """Contract implemented by the concrete outbound AEAT providers."""

    kind: AuthProviderKind

    async def authenticate(self) -> AeatSession:
        """Establish an authenticated AEAT session."""
        ...

    async def verify(self, session: AeatSession) -> AeatLoginAssertion:
        """Verify an acquired AEAT session."""
        ...

    def describe(self) -> AuthProviderDescription:
        """Describe the provider without exposing secret material."""
        ...

    async def close(self) -> None:
        """Release every provider-owned resource."""
        ...


def select_provider(
    kind: AuthProviderKind,
    *,
    settings: Settings,
    browser_session_factory: BrowserSessionFactory | None = None,
    certificate_credentials: ActiveCertificateCredentials | None = None,
) -> AuthProvider:
    """Construct the concrete outbound provider for ``kind``.

    Certificate credentials are resolved once at the application boundary
    before construction so a missing named-source secret cannot fall through
    to an unrelated global password.
    """
    credentials = certificate_credentials
    if kind is AuthProviderKind.CERTIFICATE and credentials is None:
        credentials = resolve_active_certificate_credentials(settings=settings)
    outbound_auth = import_module("cadrumo.adapters.outbound.aeat.auth")
    provider = outbound_auth.select_provider(
        kind,
        settings=settings,
        browser_session_factory=browser_session_factory,
        certificate_credentials=credentials,
    )
    if not isinstance(provider, AuthProvider):
        raise TypeError("outbound auth factory returned an object outside the AuthProvider contract")
    return provider
