"""Application-owned authentication provider contract and selection service."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from ...core.auth_provider import AuthProviderDescription, AuthProviderKind
from ..auth_credentials import ActiveCertificateCredentials
from .credentials import resolve_active_certificate_credentials
from .protocols import BrowserSessionFactoryPort
from .session_types import AeatLoginAssertion, AeatSession

if TYPE_CHECKING:
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


class AuthProviderSelector(Protocol):
    """Concrete-provider constructor supplied by outward composition."""

    def __call__(
        self,
        kind: AuthProviderKind,
        *,
        settings: Settings,
        browser_session_factory: BrowserSessionFactoryPort | None = None,
        certificate_credentials: ActiveCertificateCredentials | None = None,
    ) -> AuthProvider:
        """Construct the provider selected by ``kind``."""
        ...


_BOUND_AUTH_PROVIDER_SELECTOR: ContextVar[AuthProviderSelector] = ContextVar(
    "cadrumo_auth_provider_selector",
)


@contextmanager
def bind_auth_provider_selector(selector: AuthProviderSelector) -> Generator[AuthProviderSelector]:
    """Bind the outward concrete-provider composition for one runtime scope."""
    token = _BOUND_AUTH_PROVIDER_SELECTOR.set(selector)
    try:
        yield selector
    finally:
        _BOUND_AUTH_PROVIDER_SELECTOR.reset(token)


def _auth_provider_selector() -> AuthProviderSelector:
    try:
        return _BOUND_AUTH_PROVIDER_SELECTOR.get()
    except LookupError as exc:
        raise RuntimeError("AEAT authentication provider composition is not bound") from exc


def select_provider(
    kind: AuthProviderKind,
    *,
    settings: Settings,
    browser_session_factory: BrowserSessionFactoryPort | None = None,
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
    return _auth_provider_selector()(
        kind,
        settings=settings,
        browser_session_factory=browser_session_factory,
        certificate_credentials=credentials,
    )


__all__ = ["AuthProvider", "AuthProviderSelector", "bind_auth_provider_selector", "select_provider"]
