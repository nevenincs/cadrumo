"""Application auth facade for operator configuration and AEAT sessions.

This package owns the application-layer authentication contract used by
operator configuration, live-read preflight, and AEAT session acquisition.
:class:`AuthProvider` defines the provider protocol; the layer-neutral
:class:`core.AuthProviderKind` and :class:`core.AuthProviderDescription`
contracts are owned by :mod:`core`. :func:`select_provider`
delegates lazily to concrete outbound providers under
:mod:`adapters.outbound.aeat.auth` so application consumers keep one
stable facade without importing adapter mechanics at module load.

Operator-facing auth configuration stays in this layer.
:func:`configure_operator_auth`,
:func:`inspect_operator_auth`,
:func:`test_operator_auth`,
:func:`login_operator_auth`,
:func:`logout_operator_auth`, and
:func:`reset_operator_auth` return typed result records
such as :class:`AuthStatusResult`,
:class:`AuthLoginResult`, and
:class:`LiveAuthPreflightReport`. Persisted auth state and durable auth intents
are owned by :mod:`application.workflow`; this facade deliberately does not
re-export them. Provider metadata is reported through
:class:`core.AuthProviderDescription` and :class:`AuthProvidersReport`.
Configuration writes are
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
    :class:`adapters.persistence.profile.buckets.BucketEventHistoryRepository`
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

from importlib import import_module
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from ...adapters.outbound.aeat.auth import (
        AeatLoginAssertion,
        AeatSession,
        BrowserSessionFactory,
    )
    from ...core.config import Settings

from ...core import AuthProviderDescription as _AuthProviderDescription
from ...core import AuthProviderKind as _AuthProviderKind
from ..auth_credentials import ActiveCertificateCredentials
from ._catalogue import (
    AUTH_PROVIDER_CATALOGUE,
    AuthProviderListing,
    get_auth_provider,
    implemented_auth_provider_ids,
    known_auth_provider_ids,
    list_auth_providers,
)


@runtime_checkable
class AuthProvider(Protocol):
    """Protocol every concrete AEAT auth provider satisfies.

    Implementations live under :mod:`adapters.outbound.aeat.auth`
    and are dispatched by :func:`select_provider`.
    """

    kind: _AuthProviderKind

    async def authenticate(
        self,
    ) -> AeatSession:
        """Establish an authenticated session and return the :class:`AeatSession` record."""
        ...

    async def verify(
        self,
        session: AeatSession,
    ) -> AeatLoginAssertion:
        """Re-probe ``session`` through the provider's authoritative proof."""
        ...

    def describe(self) -> _AuthProviderDescription:
        """Return the provider's safe :class:`core.AuthProviderDescription`."""
        ...

    async def close(self) -> None:
        """Release every browser resource owned by this provider."""
        ...


def select_provider(
    kind: _AuthProviderKind,
    *,
    settings: Settings,
    browser_session_factory: BrowserSessionFactory | None = None,
    certificate_credentials: ActiveCertificateCredentials | None = None,
) -> AuthProvider:
    """Return the concrete outbound auth provider for ``kind``.

    The application package owns the selection contract; the concrete
    implementations stay in the outbound adapter layer and are imported
    lazily to avoid an application/adapter import cycle at module load.

    Certificate construction resolves the active named credential exactly
    once, then passes that typed credential directly to the outbound adapter.
    Explicit absent values are retained so a missing named-source secret can
    never inherit an unrelated global password.

    Returns an :class:`AuthProvider` configured for the requested provider
    kind.
    """
    credentials = certificate_credentials
    if kind is _AuthProviderKind.CERTIFICATE and credentials is None:
        credentials = resolve_active_certificate_credentials(settings=settings)
    outbound_auth = import_module("cadrumo.adapters.outbound.aeat.auth")
    outbound_factory = outbound_auth.select_provider
    provider = outbound_factory(
        kind,
        settings=settings,
        browser_session_factory=browser_session_factory,
        certificate_credentials=credentials,
    )
    if not isinstance(provider, AuthProvider):
        raise TypeError("outbound auth factory returned an object outside the AuthProvider contract")
    return provider


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
    ApoderadoConfigurationIdentityError,
    ApoderadoConfigurationNotSetError,
    ApoderadoLiveCheckUnavailableError,
    ApoderadoRepresentedNifInvalidError,
    ApoderadoService,
    ApoderadoStatus,
)
from ._apoderado_flow import (
    APODERADO_FLOW_ID,
    APODERADO_FLOW_LOCALE_KEYS,
    ApoderadoFlowAnswers,
    apoderado_answers_from_state,
    build_apoderado_flow_definition,
)
from ._certificate_secret_backend import (
    CertificateSecretBackend,
    SecureStorageCertificateSecretBackend,
)
from ._certificate_sources import (
    CertificateSourceNoActiveBucketError,
)
from ._certificate_sources_operator import (
    certificate_source_tax_id,
    check_operator_certificate_sources,
    list_operator_certificate_sources,
    register_operator_certificate_source,
    remove_operator_certificate_source,
    remove_operator_certificate_source_secret,
    select_operator_certificate_source,
    set_operator_certificate_source_secret,
)
from ._credential_resolution import (
    ActiveAuthProjectionSnapshot,
    active_auth_projection_span,
    project_active_certificate_credentials,
    resolve_active_certificate_credentials,
    resolve_certificate_source_secret,
)
from ._diagnostics import (
    AUTH_DIAGNOSTIC_PHONE_STATES,
    AuthDiagnosticDetail,
    AuthDiagnosticListReport,
    AuthDiagnosticPhoneState,
    AuthDiagnosticPhoneStateSource,
    AuthDiagnosticReportResult,
    AuthDiagnosticSummary,
    list_auth_diagnostics,
    load_auth_diagnostic,
    record_auth_diagnostic_phone_state,
)
from ._errors import AuthDiagnosticPayloadError
from ._operator import (
    build_live_auth_preflight_report,
    configure_operator_auth,
    inspect_operator_auth,
    list_operator_auth_providers,
    login_operator_auth,
    logout_operator_auth,
    reset_operator_auth,
    test_operator_auth,
)
from ._operator_cleanup import clear_operator_auth_acquisition_locks
from ._operator_probes import (
    ProviderConfigurationProbe,
    bind_profile_auth_settings,
    probe_provider_configuration,
    probe_provider_credentials,
)
from ._operator_results import (
    AuthCleanupInProgressError,
    AuthConfigureDanglingActiveProfileError,
    AuthConfigureNoActiveBucketError,
    AuthConfigureResult,
    AuthLoginNotEnabledError,
    AuthLoginPreconditionError,
    AuthLoginResult,
    AuthLogoutResult,
    AuthOperationRequiresCustodySessionError,
    AuthOperationScopeConflictError,
    AuthProviderNotConfiguredError,
    AuthProviderReservedError,
    AuthProvidersReport,
    AuthResetResult,
    AuthStatusResult,
    AuthTestResult,
    CertificateSecretMutationInProgressError,
    CertificateSourceCheckEntry,
    CertificateSourceCheckReport,
    CertificateSourceListResult,
    CertificateSourceMutationResult,
    CertificateSourceNotFoundError,
    CertificateSourcePayload,
    CertificateSourceSecretMutationResult,
    LiveAuthPreflightReport,
)
from ._operator_scope import operator_auth_revocation_is_reachable
from ._probe_result import ProviderProbeResult
from ._sessions import (
    AuthenticatedAeatSessionResult,
    AuthProfileIdentityMismatchError,
    AuthSessionUnavailableError,
    ClaveAuthFacts,
    ClaveCredentials,
    ClaveCredentialsIncompleteError,
    CorruptAuthSessionError,
    PersistedAuthSession,
    SessionDeserializationError,
    StorageStatePaths,
    bind_clave_credentials_to_settings,
    clave_auth_facts_from_profile_values,
    delete_persisted_session,
    ensure_authenticated_aeat_session,
    load_persisted_session,
    persisted_session_exists,
    require_verified_aeat_session,
    resolve_clave_credentials,
    storage_state_paths,
)

__all__ = [
    "APODERADO_FLOW_ID",
    "APODERADO_FLOW_LOCALE_KEYS",
    "AUTH_DIAGNOSTIC_PHONE_STATES",
    "AUTH_PROVIDER_CATALOGUE",
    "ActiveAuthProjectionSnapshot",
    "ActiveCertificateCredentials",
    "ApoderadoConfiguration",
    "ApoderadoConfigurationIdentityError",
    "ApoderadoConfigurationNotSetError",
    "ApoderadoFlowAnswers",
    "ApoderadoLiveCheckUnavailableError",
    "ApoderadoRepresentedNifInvalidError",
    "ApoderadoService",
    "ApoderadoStatus",
    "AuthAcquisitionLockRecord",
    "AuthAcquisitionLockState",
    "AuthAcquisitionLockStatus",
    "AuthAcquisitionLockedError",
    "AuthCleanupInProgressError",
    "AuthConfigureDanglingActiveProfileError",
    "AuthConfigureNoActiveBucketError",
    "AuthConfigureResult",
    "AuthDiagnosticDetail",
    "AuthDiagnosticListReport",
    "AuthDiagnosticPayloadError",
    "AuthDiagnosticPhoneState",
    "AuthDiagnosticPhoneStateSource",
    "AuthDiagnosticReportResult",
    "AuthDiagnosticSummary",
    "AuthLoginNotEnabledError",
    "AuthLoginPreconditionError",
    "AuthLoginResult",
    "AuthLogoutResult",
    "AuthOperationRequiresCustodySessionError",
    "AuthOperationScopeConflictError",
    "AuthProfileIdentityMismatchError",
    "AuthProvider",
    "AuthProviderListing",
    "AuthProviderNotConfiguredError",
    "AuthProviderReservedError",
    "AuthProvidersReport",
    "AuthResetResult",
    "AuthSessionUnavailableError",
    "AuthStatusResult",
    "AuthTestResult",
    "AuthenticatedAeatSessionResult",
    "CertificateSecretBackend",
    "CertificateSecretMutationInProgressError",
    "CertificateSourceCheckEntry",
    "CertificateSourceCheckReport",
    "CertificateSourceListResult",
    "CertificateSourceMutationResult",
    "CertificateSourceNoActiveBucketError",
    "CertificateSourceNotFoundError",
    "CertificateSourcePayload",
    "CertificateSourceSecretMutationResult",
    "ClaveAuthFacts",
    "ClaveCredentials",
    "ClaveCredentialsIncompleteError",
    "CorruptAuthSessionError",
    "LiveAuthPreflightReport",
    "PersistedAuthSession",
    "ProviderConfigurationProbe",
    "ProviderProbeResult",
    "SecureStorageCertificateSecretBackend",
    "SessionDeserializationError",
    "StorageStatePaths",
    "acquire_auth_acquisition_lock",
    "active_auth_projection_span",
    "apoderado_answers_from_state",
    "auth_acquisition_lock_path",
    "auth_lock_ttl_seconds",
    "bind_clave_credentials_to_settings",
    "bind_profile_auth_settings",
    "build_apoderado_flow_definition",
    "build_live_auth_preflight_report",
    "certificate_source_tax_id",
    "check_operator_certificate_sources",
    "clave_auth_facts_from_profile_values",
    "clear_auth_acquisition_lock",
    "clear_operator_auth_acquisition_locks",
    "configure_operator_auth",
    "delete_persisted_session",
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
    "logout_operator_auth",
    "operator_auth_revocation_is_reachable",
    "persisted_session_exists",
    "probe_provider_configuration",
    "probe_provider_credentials",
    "project_active_certificate_credentials",
    "record_auth_diagnostic_phone_state",
    "register_operator_certificate_source",
    "remove_operator_certificate_source",
    "remove_operator_certificate_source_secret",
    "require_verified_aeat_session",
    "reset_operator_auth",
    "resolve_active_certificate_credentials",
    "resolve_certificate_source_secret",
    "resolve_clave_credentials",
    "select_operator_certificate_source",
    "select_provider",
    "set_operator_certificate_source_secret",
    "storage_state_paths",
    "test_operator_auth",
    "update_auth",
]
