"""AEAT Sede authentication: providers, sessions, and certificate health.

The outbound auth surface establishes and verifies authenticated sessions
against the AEAT Sede electrónica. It implements the application-layer
:class:`AuthProvider` contract for each supported provider kind and gates
every live interaction behind the core access gate.

Major declarations:

* :func:`~aeat.adapters.outbound.aeat.auth.select_provider` — dispatch a
  :class:`AuthProviderKind` to its concrete provider
  (:class:`AeatAuthenticator` for client certificates,
  :class:`ClaveMovilAuthProvider` for Cl@ve Móvil).
* :class:`AeatSession` and :class:`AeatLoginAssertion` — the authenticated
  session record and the re-probe assertion the providers return.
* :class:`CertificateBundle` and :class:`LoadedCertificate` from
  :mod:`aeat.adapters.outbound.aeat.auth.certificate` — the PKCS#12
  certificate-loading and health-evaluation surface.
* :class:`AuthError` and its subclasses
  (:class:`AeatSessionExpiredError`, :class:`AuthConfigurationError`, and
  the certificate and Cl@ve-Móvil error families) — the failure taxonomy.

Live reads pass through :class:`AeatAccessGate`; no path performs a remote
write to the AEAT.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .....application.auth import (
    AuthProvider,
    AuthProviderKind,
)
from .....core.access_gate import (
    AeatAccessGate,
    AeatGateEnvSnapshot,
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
    ClaveMovilFailureMode,
)
from ._errors import (
    AeatLoginAssertionError,
    AeatSessionExpiredError,
    AuthConfigurationError,
    AuthError,
    AuthValidationError,
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
    "AeatLoginAssertion",
    "AeatLoginAssertionError",
    "AeatSession",
    "AeatSessionExpiredError",
    "AuthConfigurationError",
    "AuthError",
    "AuthLoginAssertionDetail",
    "AuthProvider",
    "AuthProviderKind",
    "AuthSessionDetail",
    "AuthValidationError",
    "BrowserContextLike",
    "BrowserContextProvisioner",
    "BrowserPageLike",
    "BrowserResponseLike",
    "BrowserSessionFactory",
    "BrowserSessionLike",
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
    "ClaveMovilFailureMode",
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
    """Return the concrete outbound :class:`AuthProvider` for ``kind``."""
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
