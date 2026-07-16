"""Application auth facade for operator configuration and AEAT sessions.

This package owns the application-layer authentication contract used by
operator configuration, live-read preflight, and AEAT session acquisition.
:class:`AuthProvider` and
:class:`AuthProviderKind` define the provider protocol
and closed provider catalogue; :func:`select_provider`
delegates lazily to concrete outbound providers under
:mod:`adapters.outbound.aeat.auth` so application consumers keep one
stable facade without importing adapter mechanics at module load.

Operator-facing auth configuration stays in this layer.
:func:`configure_operator_auth`,
:func:`inspect_operator_auth`,
:func:`test_operator_auth`,
:func:`login_operator_auth`, and
:func:`clear_operator_auth` return typed result records
such as :class:`AuthStatusResult`,
:class:`AuthLoginResult`, and
:class:`LiveAuthPreflightReport`. The persisted local
configuration is :class:`AuthState`, while provider
metadata is reported through
:class:`AuthProviderDescription` and
:class:`AuthProvidersReport`. Configuration writes are
gated by :class:`application.workflow.ActiveProfileHealth`: a missing,
dangling, or unreadable active bucket is refused before workflow state changes.
Successful provider configuration persists the updated
:class:`application.workflow.WorkflowState` and the typed
``AUTH_PROVIDER_CONFIGURED`` bucket event in one secure-object transaction;
the event payload may include a certificate path but never private keys,
passwords, session tokens, or QR payloads.

The session lifecycle is encrypted and profile-scoped.
:func:`ensure_authenticated_aeat_session` and
:func:`require_verified_aeat_session` coordinate
:class:`PersistedAuthSession` reuse,
:class:`AuthAcquisitionLockRecord` locking, and the provider's
:class:`adapters.outbound.aeat.auth.AeatSession` /
:class:`adapters.outbound.aeat.auth.AeatLoginAssertion` pair. Live-read call
sites combine this facade with :class:`core.access_gate.AeatAccessGate`;
this package does not expose AEAT-side write verbs. Session object keys are
derived from the active bucket through
:func:`storage_state_paths`, and operator verbs open an
active-profile storage span when the process has a selected pointer but no
ambient master-key session. Cl@ve Móvil session acquisition additionally fails
closed with :class:`AuthProfileIdentityMismatchError`
when the configured identity, active profile tax id, or verified session
identity disagree.

Additional package-level surfaces cover local auth diagnostics and
apoderado configuration. :class:`AuthDiagnosticSummary`,
:class:`AuthDiagnosticDetail`, and
:func:`record_auth_diagnostic_phone_state` operate on redacted encrypted
diagnostic records. :class:`ApoderadoService`
persists identity-sensitive represented-party configuration through encrypted
storage and permanently refuses live AEAT-side apoderamiento mutation.

See Also:
    :mod:`adapters.outbound.aeat.auth`
        Concrete certificate and Cl@ve Movil providers selected through this
        application facade.
    :class:`core.access_gate.AeatAccessGate`
        Mandatory live-read precondition and permanent live-write refusal used
        before authenticated AEAT access proceeds.
    :mod:`application.state_projection`
        Canonical operator-state projection consumed by auth status, auth test,
        and live-auth preflight surfaces.
    :mod:`application.workflow`
        Public workflow facade that owns
        :class:`application.workflow.WorkflowState` and
        :class:`application.workflow.ActiveProfileHealth`.
    :class:`domain.buckets.BucketEventHistoryRepository`
        Durable bucket event catalogue that receives auth configuration,
        session, lock, and clear events without secret payload material.
    :mod:`application.live`
        Read-only AEAT capture workflows that obtain verified sessions through
        this package.
    :mod:`domain.auth.apoderamientos`
        Domain-owned scope catalogue consumed by
        :class:`ApoderadoService`.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from ...adapters.outbound.aeat.auth import (
        AeatLoginAssertion,
        AeatSession,
        BrowserSessionFactory,
        BrowserSessionLike,
    )
    from ...core.config import Settings

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ._catalogue import (
    AUTH_PROVIDER_CATALOGUE,
    AuthProviderListing,
    get_auth_provider,
    implemented_auth_provider_ids,
    known_auth_provider_ids,
    list_auth_providers,
)


class AuthProviderKind(StrEnum):
    """Closed enumeration of supported AEAT authentication providers.

    Attributes:
        CERTIFICATE: PKCS#12 client certificate (FNMT-RCM and equivalents).
        CLAVE_MOVIL: operator-mediated ``Cl@ve`` Móvil flow.
        CLAVE_PERMANENTE: DNI/NIE + password ``Cl@ve`` Permanente flow, used
            for AEAT read paths without an FNMT certificate or a phone.
    """

    CERTIFICATE = "certificate"
    CLAVE_MOVIL = "clave_movil"
    CLAVE_PERMANENTE = "clave_permanente"


class AuthProviderDescription(BaseModel):
    """Operator-facing description of one configured auth provider.

    Attributes:
        kind: Identifier of the provider.
        label: Human-readable provider name.
        configured: Whether the provider's required settings are present.
        available: Whether a session can be established.
        identity_nif: NIF resolved by the provider, when known.
        subject: Subject DN or equivalent identity string.
        expires_on: Expiry date for the underlying credential.
        health_severity: Provider-specific health classification.
        days_until_expiry: Convenience countdown to ``expires_on``.
        health_summary: Short human-readable diagnostic.
    """

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
    """Protocol every concrete AEAT auth provider satisfies.

    Implementations live under :mod:`adapters.outbound.aeat.auth`
    and are dispatched by :func:`select_provider`.
    """

    kind: AuthProviderKind

    async def authenticate(
        self,
        *,
        browser_session: BrowserSessionLike | None = None,
        target_url: str | None = None,
    ) -> AeatSession:
        """Establish an authenticated session and return the :class:`AeatSession` record."""
        ...

    async def verify(
        self,
        session: AeatSession,
        *,
        target_url: str | None = None,
    ) -> AeatLoginAssertion:
        """Re-probe ``session`` against ``target_url`` and return the :class:`AeatLoginAssertion` for the provider."""
        ...

    def describe(self) -> AuthProviderDescription:
        """Return a safe, log-friendly :class:`AuthProviderDescription` of the provider's configured state."""
        ...


def select_provider(
    kind: AuthProviderKind,
    *,
    settings: Settings,
    browser_session_factory: BrowserSessionFactory | None = None,
) -> AuthProvider:
    """Return the concrete outbound auth provider for ``kind``.

    The application package owns the selection contract; the concrete
    implementations stay in the outbound adapter layer and are imported
    lazily to avoid an application/adapter import cycle at module load.

    Returns an :class:`AuthProvider` configured for the requested
    provider kind.
    """
    from ...adapters.outbound.aeat.auth import select_provider as _select_provider

    return _select_provider(
        kind,
        settings=settings,
        browser_session_factory=browser_session_factory,
    )


def describe_provider_operator_impact(description: AuthProviderDescription) -> str:
    """Return a one-paragraph operator-facing summary of how ``description`` affects the workflow.

    Used by ``aeat config auth providers`` to render a human-readable
    diagnostic. The string focuses on what the operator can and cannot
    do given the current provider configuration; never contains
    secrets.
    """
    from ...core.i18n import tr

    if not description.configured:
        return tr("application.auth.provider_impact.unconfigured")
    if not description.available:
        return tr("application.auth.provider_impact.unavailable", label=description.label)
    if description.kind == AuthProviderKind.CERTIFICATE:
        return tr("application.auth.provider_impact.certificate_ready")
    return tr("application.auth.provider_impact.generic_ready", label=description.label)


from ._acquisition_lock import (
    AuthAcquisitionLockedError,
    AuthAcquisitionLockRecord,
    AuthAcquisitionLockState,
    AuthAcquisitionLockStatus,
    acquire_auth_acquisition_lock,
    auth_acquisition_lock_path,
    auth_lock_ttl_seconds,
    clear_auth_acquisition_lock,
    inspect_auth_acquisition_lock,
)
from ._actions import update_auth
from ._apoderado import (
    ApoderadoConfiguration,
    ApoderadoConfigurationNotSetError,
    ApoderadoLiveCheckUnavailableError,
    ApoderadoService,
    ApoderadoStatus,
)
from ._certificate_secret_backend import (
    SECURE_STORAGE_BACKEND_LABEL,
    CertificateSecretBackend,
    SecureStorageCertificateSecretBackend,
)
from ._certificate_sources import (
    CertificateSourceNoActiveBucketError,
)
from ._certificate_sources import (
    CertificateSourceNotFoundError as StateCertificateSourceNotFoundError,
)
from ._certificate_sources_operator import (
    ActiveCertificateCredentials,
    check_operator_certificate_sources,
    list_operator_certificate_sources,
    register_operator_certificate_source,
    remove_operator_certificate_source,
    remove_operator_certificate_source_secret,
    resolve_active_certificate_credentials,
    resolve_certificate_source_secret,
    select_operator_certificate_source,
    set_operator_certificate_source_secret,
)
from ._diagnostics import (
    AUTH_DIAGNOSTIC_PHONE_STATES,
    AuthDiagnosticDetail,
    AuthDiagnosticListReport,
    AuthDiagnosticReportResult,
    AuthDiagnosticSummary,
    list_auth_diagnostics,
    load_auth_diagnostic,
    record_auth_diagnostic_phone_state,
)
from ._errors import AuthDiagnosticPayloadError
from ._models import AuthState, CertificateSourceRecord
from ._operator import (
    build_live_auth_preflight_report,
    clear_operator_auth,
    configure_operator_auth,
    inspect_operator_auth,
    list_operator_auth_providers,
    login_operator_auth,
    test_operator_auth,
)
from ._operator_probes import (
    ProviderConfigurationProbe,
    ProviderProbeResult,
    probe_provider_configuration,
)
from ._operator_results import (
    AuthClearResult,
    AuthConfigureDanglingActiveProfileError,
    AuthConfigureNoActiveBucketError,
    AuthConfigureResult,
    AuthLoginNotEnabledError,
    AuthLoginPreconditionError,
    AuthLoginResult,
    AuthProviderReservedError,
    AuthProvidersReport,
    AuthStatusResult,
    AuthTestResult,
    CertificateSourceCheckEntry,
    CertificateSourceCheckReport,
    CertificateSourceListResult,
    CertificateSourceMutationResult,
    CertificateSourceNotFoundError,
    CertificateSourcePayload,
    CertificateSourceSecretMutationResult,
    LiveAuthPreflightReport,
)
from ._sessions import (
    AuthenticatedAeatSessionResult,
    AuthProfileIdentityMismatchError,
    AuthSessionUnavailableError,
    CorruptAuthSessionError,
    PersistedAuthSession,
    SessionDeserializationError,
    StorageStatePaths,
    configure_session_store,
    delete_persisted_session,
    ensure_authenticated_aeat_session,
    load_persisted_session,
    require_verified_aeat_session,
    storage_state_paths,
)

__all__ = [
    "AUTH_DIAGNOSTIC_PHONE_STATES",
    "AUTH_PROVIDER_CATALOGUE",
    "SECURE_STORAGE_BACKEND_LABEL",
    "ActiveCertificateCredentials",
    "ApoderadoConfiguration",
    "ApoderadoConfigurationNotSetError",
    "ApoderadoLiveCheckUnavailableError",
    "ApoderadoService",
    "ApoderadoStatus",
    "AuthAcquisitionLockRecord",
    "AuthAcquisitionLockState",
    "AuthAcquisitionLockStatus",
    "AuthAcquisitionLockedError",
    "AuthClearResult",
    "AuthConfigureDanglingActiveProfileError",
    "AuthConfigureNoActiveBucketError",
    "AuthConfigureResult",
    "AuthDiagnosticDetail",
    "AuthDiagnosticListReport",
    "AuthDiagnosticPayloadError",
    "AuthDiagnosticReportResult",
    "AuthDiagnosticSummary",
    "AuthLoginNotEnabledError",
    "AuthLoginPreconditionError",
    "AuthLoginResult",
    "AuthProfileIdentityMismatchError",
    "AuthProvider",
    "AuthProviderDescription",
    "AuthProviderKind",
    "AuthProviderListing",
    "AuthProviderReservedError",
    "AuthProvidersReport",
    "AuthSessionUnavailableError",
    "AuthState",
    "AuthStatusResult",
    "AuthTestResult",
    "AuthenticatedAeatSessionResult",
    "CertificateSecretBackend",
    "CertificateSourceCheckEntry",
    "CertificateSourceCheckReport",
    "CertificateSourceListResult",
    "CertificateSourceMutationResult",
    "CertificateSourceNoActiveBucketError",
    "CertificateSourceNotFoundError",
    "CertificateSourcePayload",
    "CertificateSourceRecord",
    "CertificateSourceSecretMutationResult",
    "CorruptAuthSessionError",
    "LiveAuthPreflightReport",
    "PersistedAuthSession",
    "ProviderConfigurationProbe",
    "ProviderProbeResult",
    "SecureStorageCertificateSecretBackend",
    "SessionDeserializationError",
    "StateCertificateSourceNotFoundError",
    "StorageStatePaths",
    "acquire_auth_acquisition_lock",
    "auth_acquisition_lock_path",
    "auth_lock_ttl_seconds",
    "build_live_auth_preflight_report",
    "check_operator_certificate_sources",
    "clear_auth_acquisition_lock",
    "clear_operator_auth",
    "configure_operator_auth",
    "configure_session_store",
    "delete_persisted_session",
    "describe_provider_operator_impact",
    "ensure_authenticated_aeat_session",
    "get_auth_provider",
    "implemented_auth_provider_ids",
    "inspect_auth_acquisition_lock",
    "inspect_operator_auth",
    "known_auth_provider_ids",
    "list_auth_diagnostics",
    "list_auth_providers",
    "list_operator_auth_providers",
    "list_operator_certificate_sources",
    "load_auth_diagnostic",
    "load_persisted_session",
    "login_operator_auth",
    "probe_provider_configuration",
    "record_auth_diagnostic_phone_state",
    "register_operator_certificate_source",
    "remove_operator_certificate_source",
    "remove_operator_certificate_source_secret",
    "require_verified_aeat_session",
    "resolve_active_certificate_credentials",
    "resolve_certificate_source_secret",
    "select_operator_certificate_source",
    "select_provider",
    "set_operator_certificate_source_secret",
    "storage_state_paths",
    "test_operator_auth",
    "update_auth",
]
