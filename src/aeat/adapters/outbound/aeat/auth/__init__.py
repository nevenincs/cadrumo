"""Public outbound AEAT auth facade.

This package mirrors the application auth contract from
:mod:`aeat.application.auth` by re-exporting
:class:`~aeat.application.auth.AuthProvider` and
:class:`~aeat.application.auth.AuthProviderKind` alongside the concrete
certificate and Cl@ve Móvil providers. Use
:func:`~aeat.adapters.outbound.aeat.auth.select_provider` to resolve
``CERTIFICATE`` to :class:`~aeat.adapters.outbound.aeat.auth.AeatAuthenticator`
and ``CLAVE_MOVIL`` to
:class:`~aeat.adapters.outbound.aeat.auth.ClaveMovilAuthProvider`;
unsupported kinds raise
:exc:`~aeat.adapters.outbound.aeat.auth.AuthConfigurationError`.

Authentication results are strict, frozen, secret-free records:
:class:`~aeat.adapters.outbound.aeat.auth.AeatSession` and
:class:`~aeat.adapters.outbound.aeat.auth.AeatLoginAssertion` carry
provider-specific payloads through the discriminated ``AuthSessionDetail`` and
``AuthLoginAssertionDetail`` unions.
Selected certificate public API is available through
:mod:`aeat.adapters.outbound.aeat.auth.certificate`, including
:func:`~aeat.adapters.outbound.aeat.auth.certificate.load_certificate`,
:func:`~aeat.adapters.outbound.aeat.auth.certificate.verify_handshake`, and
:func:`~aeat.adapters.outbound.aeat.auth.certificate.health`.

Live-read policy is owned by
:class:`~aeat.core.access_gate.AeatAccessGate`: pytest live reads require
literal ``AEAT_LIVE_TESTS_ENABLED="1"``, while operator-context reads continue
through auth, profile, and read-only guards. The associated
:class:`~aeat.core.access_gate.AeatGateEnvSnapshot` records only
``aeat_live_tests_enabled`` and ``pytest_current_test``. Live AEAT writes and
live AEAT submissions are permanently refused by
:exc:`~aeat.core.access_gate.LiveSubmitForbiddenError`; auth exposes no
AEAT-side write verb.

Errors remain typed at the facade boundary, including
:exc:`~aeat.adapters.outbound.aeat.auth.AuthError`,
:exc:`~aeat.adapters.outbound.aeat.auth.AuthConfigurationError`,
:exc:`~aeat.adapters.outbound.aeat.auth.AeatLoginAssertionError`,
:exc:`~aeat.adapters.outbound.aeat.auth.AeatSessionExpiredError`, certificate
errors, and Cl@ve Móvil errors.
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
    BrowserSessionProfileLike,
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
    "BrowserSessionProfileLike",
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
    """Return the concrete outbound :class:`AuthProvider` for ``kind``.

    ``AuthProviderKind.CERTIFICATE`` builds an :class:`AeatAuthenticator`;
    ``AuthProviderKind.CLAVE_MOVIL`` builds a :class:`ClaveMovilAuthProvider`.
    The optional browser session factory is forwarded to either provider so
    application code can share Playwright sessions without depending on
    adapter internals.

    Raises:
        AuthConfigurationError: If ``kind`` is outside the supported
            :class:`AuthProviderKind` set.
    """
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
