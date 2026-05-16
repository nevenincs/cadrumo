"""Operator-facing auth application services for the config CLI."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from ...core.config import Settings
from . import AuthProviderKind, select_provider
from ._acquisition_lock import clear_auth_acquisition_lock
from ._actions import update_auth
from ._catalogue import AuthProviderListing, get_auth_provider, list_auth_providers
from ._models import AuthState
from ._sessions import delete_persisted_session

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")

if TYPE_CHECKING:
    from ..workflow._models import WorkflowState


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


class AuthStatusResult(BaseModel):
    """Current local auth readiness state."""

    model_config = _STRICT_FROZEN

    provider: str = ""
    configured: bool = False
    authenticated: bool = False
    available: bool = False
    certificate_path: str = ""
    health_severity: str = ""
    health_summary: str = ""


class AuthClearResult(BaseModel):
    """Result of clearing local auth metadata and persisted state."""

    model_config = _STRICT_FROZEN

    removed_sessions: int
    cleared_workflow_state: bool
    cleared_locks: int


def list_operator_auth_providers() -> AuthProvidersReport:
    """Return implemented and reserved auth provider slots."""

    return AuthProvidersReport(providers=list_auth_providers())


def configure_operator_auth(provider: str, *, certificate_path: Path | None = None) -> AuthConfigureResult:
    """Configure the active auth provider in workflow state.

    Emits a typed ``AUTH_PROVIDER_CONFIGURED`` event into the
    bucket-event-history catalogue scoped to the active profile's
    bucket. The certificate path is recorded as a payload value when
    supplied because it is a filesystem reference, not credential
    material; certificate passwords, private keys, and session tokens
    never enter the payload.
    """

    listing = _implemented_provider(provider)

    from ..workflow._persistence import workflow_state_repository

    updated = workflow_state_repository().update(
        lambda current: _append_bucket_event(
            update_auth(
                current,
                provider=listing.id,
                certificate_path=str(certificate_path) if certificate_path is not None else None,
            ),
            action="auth.provider.configured",
            object_id=listing.id,
        )
    )
    _emit_auth_provider_configured_event(
        active_bucket_id=updated.active_profile_bucket_id(),
        provider_id=listing.id,
        certificate_path=certificate_path,
    )
    return AuthConfigureResult(provider=listing.id, file=str(certificate_path) if certificate_path is not None else "")


def _emit_auth_provider_configured_event(
    *,
    active_bucket_id: str | None,
    provider_id: str,
    certificate_path: Path | None,
) -> None:
    """Append an ``AUTH_PROVIDER_CONFIGURED`` event to the catalogue.

    No-ops when the workflow state does not yet have an active profile
    bucket; provider configuration during initial bootstrap may run
    before a bucket exists, and the workflow-state-internal event log
    already records the transition for those cases.
    """

    if active_bucket_id is None:
        return

    from datetime import UTC, datetime

    from ...domain.buckets import (
        BucketEvent,
        BucketEventHistoryRepository,
        BucketEventObjectType,
        BucketEventType,
        append_bucket_event,
        derive_bucket_event_id,
    )

    occurred_at = datetime.now(UTC)
    payload: dict[str, str] = {"provider_id": provider_id}
    if certificate_path is not None:
        payload["certificate_path"] = str(certificate_path)
    actor = "operator"
    event_id = derive_bucket_event_id(
        bucket_id=active_bucket_id,
        event_type=BucketEventType.AUTH_PROVIDER_CONFIGURED,
        occurred_at=occurred_at,
        actor=actor,
        object_type=BucketEventObjectType.PROFILE,
        object_id=provider_id,
        payload=payload,
    )
    repo = BucketEventHistoryRepository()
    repo.save(
        append_bucket_event(
            repo.load(),
            BucketEvent(
                event_id=event_id,
                bucket_id=active_bucket_id,
                event_type=BucketEventType.AUTH_PROVIDER_CONFIGURED,
                occurred_at=occurred_at,
                actor=actor,
                object_type=BucketEventObjectType.PROFILE,
                object_id=provider_id,
                payload_version=1,
                payload=payload,
            ),
        )
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
    return AuthStatusResult(
        provider=configured_provider,
        configured=configured,
        authenticated=configured and bool(auth.authenticated_at),
        available=configured and bool(auth.authenticated_at),
        certificate_path=auth.certificate_path or "",
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
    return AuthStatusResult(
        provider=description.kind.value,
        configured=description.configured,
        authenticated=persisted.authenticated,
        available=description.available,
        certificate_path=persisted.certificate_path,
        health_severity=description.health_severity or "",
        health_summary=description.health_summary or "",
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

    cleared_locks = 0
    if locks or all_providers:
        lock_kinds = list(AuthProviderKind) if all_providers or provider_kind is None else [provider_kind]
        for kind in lock_kinds:
            status = clear_auth_acquisition_lock(resolved_settings, kind, reason="operator-clear")
            if status.state.value != "absent":
                cleared_locks += 1

    from ..workflow._persistence import workflow_state_repository

    repository = workflow_state_repository()
    state = repository.load()
    current_provider = state.auth.provider
    should_clear_workflow_state = provider_kind is None or all_providers or current_provider == provider_kind.value
    if should_clear_workflow_state:
        event_object = current_provider or (provider_kind.value if provider_kind is not None else "all")
        repository.update(
            lambda current: _append_bucket_events(
                current.model_copy(update={"auth": AuthState()}),
                (
                    ("auth.provider.cleared", event_object),
                    *(() if session_event_count == 0 else (("auth.session.cleared", event_object),)),
                    *(() if cleared_locks == 0 else (("auth.lock.cleared", event_object),)),
                ),
            )
        )
    elif session_event_count or cleared_locks:
        event_object = provider_kind.value if provider_kind is not None else "all"
        repository.update(
            lambda current: _append_bucket_events(
                current,
                (
                    *(() if session_event_count == 0 else (("auth.session.cleared", event_object),)),
                    *(() if cleared_locks == 0 else (("auth.lock.cleared", event_object),)),
                ),
            )
        )

    return AuthClearResult(
        removed_sessions=len(removed_sessions),
        cleared_workflow_state=should_clear_workflow_state,
        cleared_locks=cleared_locks,
    )


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
