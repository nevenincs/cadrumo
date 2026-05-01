"""AEAT authentication — cert, Cl@ve Móvil, session management.

Provides the concrete AEAT-portal authentication providers:

- **Certificate (PKCS#12)** — mTLS-backed mutual auth against the AEAT sede.
- **Cl@ve Móvil** — mobile app PIN confirmation flow via the AEAT browser.

Provider-agnostic session types, the access gate, and certificate lifecycle
utilities are also exported from this package for convenience of callers that
need the full AEAT auth surface without reaching into sub-modules.

For Google OAuth and GCP service builders see
``aeat.adapters.outbound.google``.
"""

from __future__ import annotations

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
    ClaveMovilApprovalTimeoutError,
    ClaveMovilAuthProvider,
    ClaveMovilConfigurationError,
)
from .....core.file_permissions import restrict_file_permissions
from ._gate import AeatAccessGate, AeatGateEnvSnapshot
from ._providers import (
    CERTIFICATE_CONTEXT_MARKER,
    AuthProvider,
    AuthProviderDescription,
    AuthProviderKind,
    BrowserContextProvisioner,
    CertificateContextProvisioner,
    CertificateLoginAssertionDetail,
    CertificateSessionDetail,
    ClaveMovilLoginAssertionDetail,
    ClaveMovilSessionDetail,
    ClavePermanenteLoginAssertionDetail,
    ClavePermanenteSessionDetail,
    ClavePinLoginAssertionDetail,
    ClavePinSessionDetail,
    describe_provider_operator_impact,
    select_provider,
)
from .certificate import (
    AeatLiveReadNotEnabledError,
    AeatLoginAssertionError,
    AeatSessionExpiredError,
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

__all__ = [
    "AEAT_SESSION_IDLE_TTL",
    "CERTIFICATE_CONTEXT_MARKER",
    "AeatAccessGate",
    "AeatAuthenticator",
    "AeatGateEnvSnapshot",
    "AeatLiveReadNotEnabledError",
    "AeatLoginAssertion",
    "AeatLoginAssertionError",
    "AeatSession",
    "AeatSessionExpiredError",
    "AuthProvider",
    "AuthProviderDescription",
    "AuthProviderKind",
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
    "ClavePermanenteLoginAssertionDetail",
    "ClavePermanenteSessionDetail",
    "ClavePinLoginAssertionDetail",
    "ClavePinSessionDetail",
    "HandshakeResult",
    "LoadedCertificate",
    "build_client_certificates_kwarg",
    "describe_provider_operator_impact",
    "evaluate_loaded_certificate_health",
    "extract_nif_from_subject",
    "health",
    "load_certificate",
    "preload_into_browser_context",
    "restrict_file_permissions",
    "select_provider",
    "verify_handshake",
]
