"""Concrete AEAT authentication provider selection.

The selector is a public contract in its own defining module.  Keeping it
outside the package initializer preserves the package's intentionally inert
namespace while giving application orchestration an exact import target.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .....application.auth.protocols import BrowserSessionFactoryPort
from .....application.auth_credentials import ActiveCertificateCredentials
from .....core import AuthProviderKind
from .authenticator import AeatAuthenticator
from .clave_movil import ClaveMovilAuthProvider
from .clave_permanente import ClavePermanenteAuthProvider
from .errors import AuthConfigurationError

if TYPE_CHECKING:
    from .....core.config import Settings

__all__ = ["select_provider"]


def select_provider(
    kind: AuthProviderKind,
    *,
    settings: Settings,
    browser_session_factory: BrowserSessionFactoryPort | None = None,
    certificate_credentials: ActiveCertificateCredentials | None = None,
) -> AeatAuthenticator | ClaveMovilAuthProvider | ClavePermanenteAuthProvider:
    """Return the concrete outbound provider implementation for ``kind``.

    ``CERTIFICATE`` requires certificate credentials; browser-backed providers
    receive the optional shared browser-session factory.
    """
    if kind is AuthProviderKind.CERTIFICATE:
        if certificate_credentials is None:
            raise AuthConfigurationError(
                "certificate provider construction requires ActiveCertificateCredentials",
            )
        return AeatAuthenticator(
            settings,
            credentials=certificate_credentials,
            browser_session_factory=browser_session_factory,
        )
    if kind is AuthProviderKind.CLAVE_MOVIL:
        return ClaveMovilAuthProvider(
            settings,
            browser_session_factory=browser_session_factory,
        )
    if kind is AuthProviderKind.CLAVE_PERMANENTE:
        return ClavePermanenteAuthProvider(
            settings,
            browser_session_factory=browser_session_factory,
        )
    raise AuthConfigurationError(f"unsupported auth provider kind {kind!r}")
