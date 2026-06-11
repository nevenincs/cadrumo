"""Application-level provider contracts and selection for AEAT auth.

Owns the auth abstraction the rest of the application depends on: the
provider protocol, the selection contract, the operator-facing configure /
status / test / clear actions, and the persisted-session lifecycle. The
concrete providers live in the outbound adapter layer and are imported
lazily to avoid an application/adapter import cycle.

This module uses :class:`Settings` for auth provider configuration.

Major declarations:

* :class:`AuthProvider` and :class:`AuthProviderKind` — the provider
  protocol and the closed set of supported kinds, dispatched by
  :func:`~aeat.application.auth.select_provider`.
* :class:`AuthProviderDescription` — the safe, log-friendly provider state.
* :func:`configure_operator_auth`, :func:`inspect_operator_auth`,
  :func:`test_operator_auth`, and :func:`clear_operator_auth` — the
  operator actions behind ``aeat config auth``.
* :func:`ensure_authenticated_aeat_session` and
  :func:`require_verified_aeat_session` with :class:`PersistedAuthSession`
  — the persisted-session lifecycle.
* :class:`AuthState` — the persisted auth configuration record.
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
    """

    CERTIFICATE = "certificate"
    CLAVE_MOVIL = "clave_movil"


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

    Implementations live under :mod:`aeat.adapters.outbound.aeat.auth`
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
from ._models import AuthState
from ._operator import (
    build_live_auth_preflight_report,
    clear_operator_auth,
    configure_operator_auth,
    inspect_operator_auth,
    list_operator_auth_providers,
    login_operator_auth,
    test_operator_auth,
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
    LiveAuthPreflightReport,
)
from ._sessions import (
    AuthenticatedAeatSessionResult,
    AuthProfileIdentityMismatchError,
    AuthSessionUnavailableError,
    CorruptAuthSessionError,
    PersistedAuthSession,
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
    "CorruptAuthSessionError",
    "LiveAuthPreflightReport",
    "PersistedAuthSession",
    "StorageStatePaths",
    "acquire_auth_acquisition_lock",
    "auth_acquisition_lock_path",
    "auth_lock_ttl_seconds",
    "build_live_auth_preflight_report",
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
    "load_auth_diagnostic",
    "load_persisted_session",
    "login_operator_auth",
    "record_auth_diagnostic_phone_state",
    "require_verified_aeat_session",
    "select_provider",
    "storage_state_paths",
    "test_operator_auth",
    "update_auth",
]
