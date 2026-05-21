"""AEAT Sede authentication providers and public outbound auth surface."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .....application.auth import (
    AuthProvider,
    AuthProviderKind,
)
from .....core.access_gate import (
    AeatAccessGate,
    AeatGateEnvSnapshot,
    AeatLiveReadNotEnabledError,
)
from .....core.file_permissions import restrict_file_permissions
from ._authenticator import (
    AEAT_SESSION_IDLE_TTL,
    AeatAuthenticator,
    AeatLoginAssertion,
    AeatSession,
    BrowserContextLike,
    BrowserPageLike,
    BrowserResponseLike,
    BrowserSessionFactory,
    BrowserSessionLike,
)
from ._certificate_backends._playwright_context import (
    build_client_certificates_kwarg,
)
from ._clave_movil import (
    CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE,
    ClaveMovilApprovalTimeoutError,
    ClaveMovilAuthProvider,
    ClaveMovilConfigurationError,
)
from ._errors import (
    AeatLoginAssertionError,
    AeatSessionExpiredError,
    AuthConfigurationError,
    AuthError,
)
from ._providers import (
    CERTIFICATE_CONTEXT_MARKER,
    AuthLoginAssertionDetail,
    AuthSessionDetail,
    BrowserContextProvisioner,
    CertificateContextProvisioner,
    CertificateLoginAssertionDetail,
    CertificateSessionDetail,
    ClaveMovilLoginAssertionDetail,
    ClaveMovilSessionDetail,
    describe_certificate_provider,
)
from .certificate import (
    CertificateBackend,
    CertificateBundle,
    CertificateError,
    CertificateExpiredError,
    CertificateHandshakeError,
    CertificateHealth,
    CertificateHealthSeverity,
    CertificateLoadError,
    CertificateNifParseError,
    CertificatePasswordError,
    CertificatePreExpiryError,
    HandshakeResult,
    LoadedCertificate,
    evaluate_loaded_certificate_health,
    extract_nif_from_subject,
    health,
    load_certificate,
    preload_into_browser_context,
    verify_handshake,
)

if TYPE_CHECKING:
    from .....core.config import Settings

__all__ = [
    "AEAT_SESSION_IDLE_TTL",
    "CERTIFICATE_CONTEXT_MARKER",
    "CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE",
    "AeatAccessGate",
    "AeatAuthenticator",
    "AeatGateEnvSnapshot",
    "AeatLiveReadNotEnabledError",
    "AeatLoginAssertion",
    "AeatLoginAssertionError",
    "AeatSession",
    "AeatSessionExpiredError",
    "AuthConfigurationError",
    "AuthError",
    "AuthLoginAssertionDetail",
    "AuthSessionDetail",
    "BrowserContextLike",
    "BrowserContextProvisioner",
    "BrowserPageLike",
    "BrowserResponseLike",
    "BrowserSessionFactory",
    "BrowserSessionLike",
    "CertificateBackend",
    "CertificateBundle",
    "CertificateContextProvisioner",
    "CertificateError",
    "CertificateExpiredError",
    "CertificateHandshakeError",
    "CertificateHealth",
    "CertificateHealthSeverity",
    "CertificateLoadError",
    "CertificateLoginAssertionDetail",
    "CertificateNifParseError",
    "CertificatePasswordError",
    "CertificatePreExpiryError",
    "CertificateSessionDetail",
    "ClaveMovilApprovalTimeoutError",
    "ClaveMovilAuthProvider",
    "ClaveMovilConfigurationError",
    "ClaveMovilLoginAssertionDetail",
    "ClaveMovilSessionDetail",
    "HandshakeResult",
    "LoadedCertificate",
    "build_client_certificates_kwarg",
    "describe_certificate_provider",
    "evaluate_loaded_certificate_health",
    "extract_nif_from_subject",
    "health",
    "load_certificate",
    "preload_into_browser_context",
    "restrict_file_permissions",
    "select_provider",
    "verify_handshake",
]


def select_provider(
    kind: AuthProviderKind,
    *,
    settings: Settings,
    browser_session_factory: BrowserSessionFactory | None = None,
) -> AuthProvider:
    """Return the concrete outbound auth provider for ``kind``."""
    if kind is AuthProviderKind.CERTIFICATE:
        return AeatAuthenticator(
            settings,
            browser_session_factory=browser_session_factory,
        )
    if kind is AuthProviderKind.CLAVE_MOVIL:
        return ClaveMovilAuthProvider(
            settings,
            browser_session_factory=browser_session_factory,
        )
    raise AuthConfigurationError(f"unsupported auth provider kind {kind!r}")
