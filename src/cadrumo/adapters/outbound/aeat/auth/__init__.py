"""Concrete outbound AEAT authentication implementations.

This facade exports certificate, Cl@ve Móvil, and Cl@ve Permanente providers,
their session and assertion payloads, browser-context helpers, and typed
adapter errors. Provider identifiers and readiness descriptions are owned by
:mod:`core`; application orchestration is owned by
:mod:`application.auth`. Use
:func:`select_provider` to resolve
``CERTIFICATE`` to :class:`AeatAuthenticator`
and ``CLAVE_MOVIL`` to
:class:`ClaveMovilAuthProvider`, or ``CLAVE_PERMANENTE`` to
:class:`ClavePermanenteAuthProvider`;
unsupported kinds raise
:exc:`AuthConfigurationError`.

Authentication results are strict, frozen, secret-free records:
:class:`AeatSession` and
:class:`AeatLoginAssertion` carry
provider-specific payloads through the discriminated ``AuthSessionDetail`` and
``AuthLoginAssertionDetail`` unions.
Selected certificate public API is available through
:mod:`adapters.outbound.aeat.auth.certificate`, including
:func:`adapters.outbound.aeat.auth.certificate.load_certificate` and
:func:`adapters.outbound.aeat.auth.certificate.health`.

Live-read policy is owned by
:class:`core.access_gate.AeatAccessGate`: pytest live reads require
the live-test opt-in enabled, while operator-context reads continue
through auth, profile, and read-only guards. The associated
:class:`core.access_gate.AeatGateEnvSnapshot` records only the
live-test opt-in flag and the current pytest test id. Live AEAT writes and
live AEAT submissions are permanently refused by
:exc:`core.access_gate.LiveSubmitForbiddenError`; auth exposes no
AEAT-side write verb.

Errors remain typed at the facade boundary, including
:exc:`AuthError`,
:exc:`AuthConfigurationError`,
:exc:`AeatLoginAssertionError`,
:exc:`AeatSessionExpiredError`, certificate
errors, and Cl@ve Móvil errors.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .....application.auth_credentials import ActiveCertificateCredentials
from .....core import AuthProviderKind as _AuthProviderKind
from .....core.access_gate import (
    AeatAccessGate,
    AeatGateEnvSnapshot,
)
from .....core.config import (
    AEAT_CERTIFICATE_PROTECTED_ORIGIN,
    AEAT_CERTIFICATE_PROTECTED_PATH,
    AEAT_CERTIFICATE_PROTECTED_URL,
)
from . import _session_store as session_store
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
from ._authenticator_types import CertificateHealthCheck
from ._clave_movil import (
    CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE,
    ClaveMovilApprovalTimeoutError,
    ClaveMovilAuthProvider,
    ClaveMovilConfigurationError,
    ClaveMovilFailureMode,
)
from ._clave_movil_support import classify_identity, operator_progress_sink
from ._clave_permanente import (
    ClavePermanenteAuthProvider,
    ClavePermanenteFailureMode,
)
from ._errors import (
    AeatLoginAssertionError,
    AeatSessionExpiredError,
    AuthConfigurationError,
    AuthError,
    AuthProviderCleanupError,
    AuthValidationError,
)
from ._providers import (
    AuthLoginAssertionDetail,
    AuthSessionDetail,
    BrowserContextProvisioner,
    CertificateContextProvisioner,
    CertificateLoginAssertionDetail,
    CertificateSessionDetail,
    ClaveMovilLoginAssertionDetail,
    ClaveMovilSessionDetail,
    ClavePermanenteLoginAssertionDetail,
    ClavePermanenteSessionDetail,
    describe_certificate_provider,
)
from .certificate import (
    CertificateBundle,
    CertificateError,
    CertificateExpiredError,
    CertificateHealth,
    CertificateHealthSeverity,
    CertificateLoadError,
    CertificateNifParseError,
    CertificatePasswordError,
    CertificatePreExpiryError,
    LoadedCertificate,
    evaluate_loaded_certificate_health,
    extract_nif_from_subject,
    health,
    load_certificate,
)

if TYPE_CHECKING:
    from .....core.config import Settings

__all__ = [
    "AEAT_CERTIFICATE_PROTECTED_ORIGIN",
    "AEAT_CERTIFICATE_PROTECTED_PATH",
    "AEAT_CERTIFICATE_PROTECTED_URL",
    "AEAT_SESSION_IDLE_TTL",
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
    "AuthProviderCleanupError",
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
    "CertificateHealth",
    "CertificateHealthCheck",
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
    "ClavePermanenteAuthProvider",
    "ClavePermanenteFailureMode",
    "ClavePermanenteLoginAssertionDetail",
    "ClavePermanenteSessionDetail",
    "LoadedCertificate",
    "classify_identity",
    "describe_certificate_provider",
    "evaluate_loaded_certificate_health",
    "extract_nif_from_subject",
    "health",
    "load_certificate",
    "operator_progress_sink",
    "select_provider",
    "session_store",
]


def select_provider(
    kind: _AuthProviderKind,
    *,
    settings: Settings,
    browser_session_factory: BrowserSessionFactory | None = None,
    certificate_credentials: ActiveCertificateCredentials | None = None,
) -> AeatAuthenticator | ClaveMovilAuthProvider | ClavePermanenteAuthProvider:
    """Return the concrete outbound provider implementation for ``kind``.

    ``AuthProviderKind.CERTIFICATE`` builds an :class:`AeatAuthenticator`;
    ``AuthProviderKind.CLAVE_MOVIL`` builds a
    :class:`ClaveMovilAuthProvider`; ``AuthProviderKind.CLAVE_PERMANENTE``
    builds a :class:`ClavePermanenteAuthProvider`. The optional browser session
    factory is forwarded to browser-backed providers so application code can
    share Playwright sessions without depending on adapter internals.

    Raises:
        AuthConfigurationError: If ``kind`` is outside the supported
            :class:`core.AuthProviderKind` set.
    """
    if kind is _AuthProviderKind.CERTIFICATE:
        if certificate_credentials is None:
            raise AuthConfigurationError(
                "certificate provider construction requires ActiveCertificateCredentials",
            )
        return AeatAuthenticator(
            settings,
            credentials=certificate_credentials,
            browser_session_factory=browser_session_factory,
        )
    if kind is _AuthProviderKind.CLAVE_MOVIL:
        return ClaveMovilAuthProvider(
            settings,
            browser_session_factory=browser_session_factory,
        )
    if kind is _AuthProviderKind.CLAVE_PERMANENTE:
        return ClavePermanenteAuthProvider(
            settings,
            browser_session_factory=browser_session_factory,
        )
    raise AuthConfigurationError(f"unsupported auth provider kind {kind!r}")
