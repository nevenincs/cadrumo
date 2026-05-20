"""Operator-facing auth application services for the config CLI."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from ...core.config import Settings
from ...core.errors import AeatError
from ...core.i18n import tr
from . import AuthProviderKind, select_provider
from ._acquisition_lock import clear_auth_acquisition_lock
from ._actions import update_auth
from ._catalogue import AuthProviderListing, get_auth_provider, list_auth_providers
from ._models import AuthState
from ._sessions import delete_persisted_session, ensure_authenticated_aeat_session

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")

if TYPE_CHECKING:
    from ..workflow._models import WorkflowState
    from ..workflow._persistence import WorkflowStateRepository


class AuthProviderReservedError(ValueError):
    """Raised when a known provider slot is reserved but not implemented."""


class AuthProvidersReport(BaseModel):
    """Auth provider catalogue projected for operator output."""

    model_config = _STRICT_FROZEN

    providers: tuple[AuthProviderListing, ...]


class AuthConfigureResult(BaseModel):
    """Result of configuring an auth provider in workflow state."""

    model_config = _STRICT_FROZEN

    provider: str
    file: str = ""
    active_profile: str = ""
    profile_tax_id_present: bool = False
    provider_identity_present: bool = False
    identity_alignment: str = ""
    next_action: str = ""


class AuthStatusResult(BaseModel):
    """Current local auth readiness state."""

    model_config = _STRICT_FROZEN

    provider: str = ""
    configured: bool = False
    authenticated: bool = False
    available: bool = False
    active_profile: str = ""
    active_profile_status: str = ""
    active_profile_registered: bool = False
    active_profile_record_present: bool = False
    active_profile_next_action: str = ""
    backend_configured: bool = False
    backend_available: bool = False
    certificate_path: str = ""
    health_severity: str = ""
    health_summary: str = ""


class AuthLoginResult(BaseModel):
    """Result of an operator-triggered live authentication attempt."""

    model_config = _STRICT_FROZEN

    provider: str
    authenticated: bool
    reused_persisted_session: bool
    fresh: bool
    removed_sessions: int
    acquired_lock: bool
    reset_lock_state: str = ""
    verification_status: str = ""


class AuthClearResult(BaseModel):
    """Result of clearing local auth metadata and persisted state."""

    model_config = _STRICT_FROZEN

    removed_sessions: int
    cleared_workflow_state: bool
    cleared_locks: int


def list_operator_auth_providers() -> AuthProvidersReport:
    """Return implemented and reserved auth provider slots."""

    return AuthProvidersReport(providers=list_auth_providers())


class AuthConfigureNoActiveBucketError(AeatError):
    """Raised when ``configure_operator_auth`` runs before an active profile bucket exists.

    The bucket-event-history ADR requires every event to be scoped to a
    bucket id. Provider configuration must happen after
    ``aeat config profile create NAME`` has activated a profile bucket; running before
    that point would either leave a silent audit hole or require deferred
    replay, both of which the ADR refuses. Surfacing the refusal here
    keeps the bootstrap contract explicit at the CLI surface.
    """


class AuthConfigureDanglingActiveProfileError(ValueError):
    """Raised when the active-profile pointer does not resolve to a registered bucket."""


def configure_operator_auth(provider: str, *, certificate_path: Path | None = None) -> AuthConfigureResult:
    """Configure the active auth provider in workflow state.

    Persists the workflow-state update and a typed
    ``AUTH_PROVIDER_CONFIGURED`` event into the bucket-event-history
    catalogue in a single SQL transaction (via
    :meth:`SecureObjectRepository.save_many`), so a crash between the
    two writes cannot leave the state mutated without the catalogue
    event landing. The certificate path is recorded as a payload value
    when supplied because it is a filesystem reference, not credential
    material; certificate passwords, private keys, and session tokens
    never enter the payload.

    Raises:
        AuthConfigureNoActiveBucketError: When no active profile bucket
            exists yet. The operator must run ``aeat config profile create NAME`` first.
    """

    from datetime import UTC, datetime

    from ...adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
    from ...domain.buckets import (
        BucketEvent,
        BucketEventHistoryRepository,
        BucketEventObjectType,
        BucketEventType,
        append_bucket_event,
        derive_bucket_event_id,
    )
    from ..workflow._models import resolve_active_bucket_id
    from ..workflow._persistence import workflow_state_repository
    from ..workflow._profile_health import assess_active_profile_health

    listing = _implemented_provider(provider)

    if resolve_active_bucket_id() is None:
        raise AuthConfigureNoActiveBucketError(
            tr("application.auth.operator.errors.no_active_bucket"),
        )
    state_repo = workflow_state_repository()
    current_state = state_repo.load()
    profile_health = assess_active_profile_health(current_state)
    active_bucket_id = profile_health.active_profile
    if active_bucket_id is None:
        raise AuthConfigureNoActiveBucketError(
            tr("application.auth.operator.errors.no_active_bucket"),
        )
    if profile_health.status == "dangling_pointer":
        raise AuthConfigureDanglingActiveProfileError(
            tr(
                "application.auth.operator.errors.dangling_active_profile",
                active_profile=active_bucket_id,
            )
        )
    if profile_health.status in {"missing_profile_record", "profile_record_unreadable"}:
        raise AuthConfigureDanglingActiveProfileError(
            tr(
                "application.auth.operator.errors.unreadable_active_profile",
                active_profile=active_bucket_id,
                status=profile_health.status,
                next_action=profile_health.next_action,
            )
        )

    next_state = _append_bucket_event(
        update_auth(
            current_state,
            provider=listing.id,
            certificate_path=str(certificate_path) if certificate_path is not None else None,
        ),
        action="auth.provider.configured",
        object_id=listing.id,
    )
    active_bucket_id = next_state.active_profile_bucket_id()
    assert active_bucket_id is not None  # invariant: update_auth preserves the active profile

    occurred_at = datetime.now(UTC)
    payload: dict[str, str] = {"provider_id": listing.id}
    if certificate_path is not None:
        payload["certificate_path"] = str(certificate_path)
    actor = "operator"
    event_id = derive_bucket_event_id(
        bucket_id=active_bucket_id,
        event_type=BucketEventType.AUTH_PROVIDER_CONFIGURED,
        occurred_at=occurred_at,
        actor=actor,
        object_type=BucketEventObjectType.PROFILE,
        object_id=listing.id,
        payload=payload,
    )
    catalogue_repo = BucketEventHistoryRepository()
    next_catalogue = append_bucket_event(
        catalogue_repo.load(),
        BucketEvent(
            event_id=event_id,
            bucket_id=active_bucket_id,
            event_type=BucketEventType.AUTH_PROVIDER_CONFIGURED,
            occurred_at=occurred_at,
            actor=actor,
            object_type=BucketEventObjectType.PROFILE,
            object_id=listing.id,
            payload_version=1,
            payload=payload,
        ),
    )

    state_write = state_repo.to_secure_object_write(next_state)
    catalogue_write = catalogue_repo.to_secure_object_write(next_catalogue)
    SecureObjectRepository().save_many((state_write, catalogue_write))

    return _auth_configure_result(
        state=next_state,
        provider=listing.id,
        certificate_path=certificate_path,
    )


def inspect_operator_auth(provider: str | None = None) -> AuthStatusResult:
    """Return current local auth state, optionally scoped to a known provider slot."""

    if provider is not None:
        get_auth_provider(provider)

    from ..workflow._persistence import workflow_state_repository

    state = workflow_state_repository().load()
    auth = state.auth
    requested_provider = provider.strip().lower() if provider is not None else None
    configured_provider = requested_provider or auth.provider or ""
    configured = bool(auth.provider) and (requested_provider is None or auth.provider == requested_provider)
    backend_configured = False
    backend_available = False
    health_severity = ""
    health_summary = ""
    if configured_provider:
        try:
            backend = select_provider(AuthProviderKind(configured_provider), settings=Settings())
            description = backend.describe()
            backend_configured = description.configured
            backend_available = description.available
            health_severity = description.health_severity or ""
            health_summary = description.health_summary or ""
        except Exception:
            backend_configured = False
            backend_available = False
    from ..workflow._profile_health import assess_active_profile_health

    profile_health = assess_active_profile_health(state)
    active_profile = profile_health.active_profile or ""

    return AuthStatusResult(
        provider=configured_provider,
        configured=configured,
        authenticated=configured and bool(auth.authenticated_at),
        available=configured and bool(auth.authenticated_at),
        active_profile=active_profile,
        active_profile_status=profile_health.status,
        active_profile_registered=profile_health.registered_bucket,
        active_profile_record_present=profile_health.profile_record_present,
        active_profile_next_action=profile_health.next_action,
        backend_configured=backend_configured,
        backend_available=backend_available,
        certificate_path=auth.certificate_path or "",
        health_severity=health_severity,
        health_summary=health_summary,
    )


def _auth_configure_result(
    *,
    state: WorkflowState,
    provider: str,
    certificate_path: Path | None,
) -> AuthConfigureResult:
    """Build a redacted configuration result that exposes identity readiness."""

    from ..user_profile._projections import record_to_path_values

    active_profile = state.active_profile_bucket_id() or ""
    record = state.active_profile_record()
    values = record_to_path_values(record)
    profile_tax_id = (values.get("identity.tax_id") or "").strip().upper()
    settings = Settings()
    provider_identity = ""
    if provider == AuthProviderKind.CLAVE_MOVIL.value:
        provider_identity = (settings.aeat_clave_movil_dni_nie or "").strip().upper()
    alignment = "not_applicable"
    if provider == AuthProviderKind.CLAVE_MOVIL.value:
        if not profile_tax_id and not provider_identity:
            alignment = "profile_tax_id_missing_and_clave_identity_missing"
        elif not profile_tax_id:
            alignment = "profile_tax_id_missing"
        elif not provider_identity:
            alignment = "clave_identity_missing"
        elif profile_tax_id == provider_identity:
            alignment = "matches"
        else:
            alignment = "mismatch"
    return AuthConfigureResult(
        provider=provider,
        file=str(certificate_path) if certificate_path is not None else "",
        active_profile=active_profile,
        profile_tax_id_present=bool(profile_tax_id),
        provider_identity_present=bool(provider_identity) if provider == AuthProviderKind.CLAVE_MOVIL.value else True,
        identity_alignment=alignment,
        next_action=(
            "aeat config auth test --provider clave_movil"
            if provider == AuthProviderKind.CLAVE_MOVIL.value
            else f"aeat config auth test --provider {provider}"
        ),
    )


def test_operator_auth(provider: str | None = None) -> AuthStatusResult:
    """Return backend-computed auth readiness without CLI-local branching."""

    provider_kind = _provider_kind_or_none(provider)
    settings = Settings()
    if provider_kind is None:
        provider_kind = _configured_or_default_provider(settings)
    provider_backend = select_provider(provider_kind, settings=settings)
    description = provider_backend.describe()
    persisted = inspect_operator_auth(description.kind.value)

    from ..workflow._persistence import workflow_state_repository
    from ..workflow._profile_health import assess_active_profile_health

    profile_health = assess_active_profile_health(workflow_state_repository().load())

    return AuthStatusResult(
        provider=description.kind.value,
        configured=description.configured,
        authenticated=persisted.authenticated,
        available=description.available,
        active_profile=profile_health.active_profile or "",
        active_profile_status=profile_health.status,
        active_profile_registered=profile_health.registered_bucket,
        active_profile_record_present=profile_health.profile_record_present,
        active_profile_next_action=profile_health.next_action,
        certificate_path=persisted.certificate_path,
        health_severity=description.health_severity or "",
        health_summary=description.health_summary or "",
    )


async def login_operator_auth(
    provider: str | None = None,
    *,
    fresh: bool = False,
    reset_lock: bool = False,
    target_url: str | None = None,
    settings: Settings | None = None,
) -> AuthLoginResult:
    """Acquire or verify a live AEAT session and persist backend auth state."""

    resolved_settings = settings or Settings()
    provider_kind = _provider_kind_or_none(provider)
    if provider_kind is None:
        provider_kind = _configured_or_default_provider(resolved_settings)
    _implemented_provider(provider_kind.value)

    result = await ensure_authenticated_aeat_session(
        resolved_settings,
        kind=provider_kind,
        fresh=fresh,
        reset_lock=reset_lock,
        operation="operator-auth-login",
        target_url=target_url,
    )

    from ..workflow._persistence import workflow_state_repository

    repository = workflow_state_repository()
    repository.update(
        lambda current: _append_bucket_event(
            update_auth(
                current,
                provider=provider_kind.value,
                authenticated=True,
            ),
            action="auth.session.verified",
            object_id=provider_kind.value,
        )
    )

    return AuthLoginResult(
        provider=provider_kind.value,
        authenticated=True,
        reused_persisted_session=result.reused_persisted_session,
        fresh=result.fresh,
        removed_sessions=len(result.removed_sessions),
        acquired_lock=result.acquired_lock is not None,
        reset_lock_state=result.reset_lock.state.value if result.reset_lock is not None else "",
        verification_status=getattr(result.assertion, "status", "") or "",
    )


def clear_operator_auth(
    *,
    provider: str | None = None,
    all_providers: bool = False,
    sessions: bool = False,
    locks: bool = False,
    settings: Settings | None = None,
) -> AuthClearResult:
    """Clear workflow auth state, persisted sessions, and acquisition locks."""

    provider_kind = _provider_kind_or_none(provider)
    resolved_settings = settings or Settings()
    removed_sessions: list[Path] = []
    session_event_count = 0
    if sessions or all_providers:
        removed_sessions = delete_persisted_session(resolved_settings, kind=None if all_providers else provider_kind)
        session_event_count = len(removed_sessions)

    cleared_locks = _clear_acquisition_locks(
        resolved_settings,
        provider_kind=provider_kind,
        all_providers=all_providers,
        locks_requested=locks,
    )

    from ..workflow._persistence import workflow_state_repository

    repository = workflow_state_repository()
    current_provider = repository.load().auth.provider
    should_clear_workflow_state = provider_kind is None or all_providers or current_provider == provider_kind.value
    _apply_auth_clear_to_repository(
        repository=repository,
        provider_kind=provider_kind,
        current_provider=current_provider,
        should_clear_workflow_state=should_clear_workflow_state,
        session_event_count=session_event_count,
        cleared_locks=cleared_locks,
    )

    return AuthClearResult(
        removed_sessions=len(removed_sessions),
        cleared_workflow_state=should_clear_workflow_state,
        cleared_locks=cleared_locks,
    )


def _clear_acquisition_locks(
    settings: Settings,
    *,
    provider_kind: AuthProviderKind | None,
    all_providers: bool,
    locks_requested: bool,
) -> int:
    """Clear acquisition locks for the targeted provider(s) and return the cleared count.

    With ``locks_requested`` or ``all_providers`` set, the target lock
    kinds are every provider (if ``all_providers`` or no specific
    ``provider_kind`` was supplied) or the single requested kind. A
    lock that was already absent does not count toward the cleared
    total.
    """
    if not (locks_requested or all_providers):
        return 0
    lock_kinds = list(AuthProviderKind) if all_providers or provider_kind is None else [provider_kind]
    cleared = 0
    for kind in lock_kinds:
        status = clear_auth_acquisition_lock(settings, kind, reason="operator-clear")
        if status.state.value != "absent":
            cleared += 1
    return cleared


def _apply_auth_clear_to_repository(
    *,
    repository: WorkflowStateRepository,
    provider_kind: AuthProviderKind | None,
    current_provider: str | None,
    should_clear_workflow_state: bool,
    session_event_count: int,
    cleared_locks: int,
) -> None:
    """Apply the operator-clear transition to the workflow-state repository.

    When ``should_clear_workflow_state`` is set, the auth state is
    reset and a ``auth.provider.cleared`` event is appended; the
    session-cleared and lock-cleared events are appended whenever
    their counters are non-zero. When the workflow state is left
    untouched, only the non-zero session / lock events are emitted —
    and only if at least one was actually performed.
    """
    if should_clear_workflow_state:
        event_object = current_provider or (provider_kind.value if provider_kind is not None else "all")
        events = (
            ("auth.provider.cleared", event_object),
            *_optional_clear_events(event_object, session_event_count, cleared_locks),
        )
        repository.update(
            lambda current: _append_bucket_events(current.model_copy(update={"auth": AuthState()}), events)
        )
        return
    if not (session_event_count or cleared_locks):
        return
    event_object = provider_kind.value if provider_kind is not None else "all"
    events = _optional_clear_events(event_object, session_event_count, cleared_locks)
    repository.update(lambda current: _append_bucket_events(current, events))


def _optional_clear_events(
    event_object: str,
    session_event_count: int,
    cleared_locks: int,
) -> tuple[tuple[str, str], ...]:
    """Build the variable-length tail of clear events keyed on non-zero counters."""
    events: list[tuple[str, str]] = []
    if session_event_count:
        events.append(("auth.session.cleared", event_object))
    if cleared_locks:
        events.append(("auth.lock.cleared", event_object))
    return tuple(events)


def _implemented_provider(provider: str) -> AuthProviderListing:
    listing = get_auth_provider(provider)
    if not listing.implemented:
        raise AuthProviderReservedError(provider)
    return listing


def _provider_kind_or_none(provider: str | None) -> AuthProviderKind | None:
    if provider is None:
        return None
    listing = _implemented_provider(provider)
    return AuthProviderKind(listing.id)


def _configured_or_default_provider(settings: Settings) -> AuthProviderKind:
    from ..workflow._persistence import workflow_state_repository

    state = workflow_state_repository().load()
    if state.auth.provider:
        return AuthProviderKind(state.auth.provider)
    if settings.aeat_auth_provider is not None:
        return AuthProviderKind(settings.aeat_auth_provider.value)
    return AuthProviderKind.CERTIFICATE


def _append_bucket_event(
    state: WorkflowState,
    *,
    action: str,
    object_id: str,
) -> WorkflowState:
    from ..workflow._models import WorkflowEvent

    bucket_id = state.active_profile_bucket_id() or "default"
    event = WorkflowEvent(action=action, bucket_id=bucket_id, object_id=object_id)
    return state.model_copy(update={"bucket_events": (*state.bucket_events, event)})


def _append_bucket_events(
    state: WorkflowState,
    events: tuple[tuple[str, str], ...],
) -> WorkflowState:
    updated = state
    for action, object_id in events:
        updated = _append_bucket_event(updated, action=action, object_id=object_id)
    return updated
