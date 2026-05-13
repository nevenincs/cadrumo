"""Application-level provider contracts and selection for AEAT auth."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from ._catalogue import (
    AUTH_PROVIDER_CATALOGUE,
    AuthProviderListing,
    get_auth_provider,
    list_auth_providers,
)

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class AuthProviderKind(StrEnum):
    """Closed enumeration of supported AEAT authentication providers.

    Attributes:
        CERTIFICATE: PKCS#12 client certificate (FNMT-RCM and equivalents).
        CLAVE_MOVIL: ``Cl@ve`` Móvil push-approval flow.
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
        browser_session: Any | None = None,
        target_url: str | None = None,
    ) -> Any:
        """Establish an authenticated session and return the provider's session record."""
        ...

    async def verify(
        self,
        session: Any,
        *,
        target_url: str | None = None,
    ) -> Any:
        """Re-probe ``session`` against ``target_url`` and return the provider's assertion record."""
        ...

    def describe(self) -> AuthProviderDescription:
        """Return a safe, log-friendly summary of the provider's configured state."""
        ...


def select_provider(
    kind: AuthProviderKind,
    *,
    settings: Any,
    browser_session_factory: Any | None = None,
) -> AuthProvider:
    """Return the concrete outbound auth provider for ``kind``.

    The application package owns the selection contract; the concrete
    implementations stay in the outbound adapter layer and are imported
    lazily to avoid an application/adapter import cycle at module load.
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


from ._acquisition_lock import (  # noqa: E402
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
from ._models import AuthState
from ._sessions import (  # noqa: E402
    AuthenticatedAeatSessionResult,
    AuthSessionUnavailableError,
    CorruptAuthSessionError,
    PersistedAuthSession,
    StorageStatePaths,
    delete_persisted_session,
    ensure_authenticated_aeat_session,
    load_persisted_session,
    require_verified_aeat_session,
    storage_state_paths,
)

__all__ = [
    "AUTH_PROVIDER_CATALOGUE",
    "AuthAcquisitionLockRecord",
    "AuthAcquisitionLockState",
    "AuthAcquisitionLockStatus",
    "AuthAcquisitionLockedError",
    "AuthProvider",
    "AuthProviderDescription",
    "AuthProviderKind",
    "AuthProviderListing",
    "AuthSessionUnavailableError",
    "AuthState",
    "AuthenticatedAeatSessionResult",
    "CorruptAuthSessionError",
    "PersistedAuthSession",
    "StorageStatePaths",
    "acquire_auth_acquisition_lock",
    "auth_acquisition_lock_path",
    "auth_lock_ttl_seconds",
    "clear_auth_acquisition_lock",
    "delete_persisted_session",
    "describe_provider_operator_impact",
    "ensure_authenticated_aeat_session",
    "get_auth_provider",
    "inspect_auth_acquisition_lock",
    "list_auth_providers",
    "load_persisted_session",
    "require_verified_aeat_session",
    "select_provider",
    "storage_state_paths",
    "update_auth",
]
