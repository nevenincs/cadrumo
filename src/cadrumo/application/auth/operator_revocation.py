"""Operator-facing auth application services for the config CLI.

Auth configuration and login actions mutate
:class:`application.workflow.state_models.WorkflowState`, validate the active bucket
through :func:`application.workflow.profile_health.assess_active_profile_health`, and
emit durable :class:`domain.buckets.event.BucketEvent` records through
:class:`adapters.persistence.profile.buckets.BucketEventHistoryRepository`.

Status, test, and preflight surfaces consume the canonical
:func:`application.state_projection.build_operator_state_projection`
producer, then narrow its
:class:`application.state_projection_auth.ProjectionAuthReadiness` and
:class:`application.state_projection_models.ProjectionActiveProfile` fields into
operator-facing result records.

See Also:
    :class:`application.auth.models.AuthState`
        Workflow-owned persisted authentication readiness.
    :class:`application.auth.operator_results.AuthStatusResult`
        CLI readiness result emitted by ``auth status``.
    :class:`application.auth.operator_results.AuthTestResult`
        CLI readiness result emitted by ``auth test`` with local provider
        probes.
    :class:`application.auth.operator_results.LiveAuthPreflightReport`
        Redacted readiness report used before a live read can request login.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import TYPE_CHECKING

from ...core.config import Settings, load_settings
from ...core.errors.hierarchy import InternalInvariantError
from ...core.time.clock import now
from ...domain.calculations.registry.authority import bundled_indexed_authority
from ._mutation import AuthBucketEventSpec as _BucketEventSpec
from ._mutation import build_auth_bucket_events as _build_bucket_events
from .certificate_secret_backend import CertificateSecretBackendFactory
from .models import (
    AuthCleanupIntent,
    AuthCleanupOperationKind,
    AuthState,
)
from .operator_cleanup import (
    apply_auth_cleanup_intent,
    assert_logout_request_matches,
    assert_reset_request_matches,
    auth_cleanup_bucket_events,
    auth_cleanup_intent_has_effects,
    build_auth_cleanup_intent,
    clear_scoped_locks,
    delete_certificate_source_secrets,
    delete_scoped_sessions,
)
from .operator_events import append_auth_bucket_events
from .operator_results import (
    AuthConfigureNoActiveBucketError,
    AuthLogoutResult,
    AuthOperationRequiresCustodySessionError,
    AuthResetResult,
)
from .operator_scope import active_profile_storage_span as _active_profile_storage_span
from .operator_scope import (
    assert_certificate_secret_mutation_not_in_progress as _assert_certificate_secret_mutation_not_in_progress,
)
from .operator_scope import auth_mutation_span as _auth_mutation_span
from .operator_scope import resolve_auth_operation_scope
from .operator_scope_ports import OperatorScopePorts
from .preferences import clear_profile_auth_preference

if TYPE_CHECKING:
    from ...domain.buckets.event import BucketEvent
    from ..workflow.state_models import WorkflowState


@contextmanager
def _revocation_storage_span(
    settings: Settings,
    *,
    target_bucket_id: str | None = None,
    operator_scope_ports: OperatorScopePorts,
):
    """Enter the auth storage span, naming the unrevoked session when it refuses.

    Logout and reset revoke an AEAT session that lives as an encrypted row inside
    the profile's own store, so revoking it genuinely requires the profile to be
    unlocked -- there is no key-free half to perform first. The generic custody
    refusal tells the operator the profile is locked, which reads as a
    permissions problem and leaves the important fact unsaid: the session is
    still there and still usable. This narrows the message to say so.

    Only the span's own entry refusal is rewritten. A refusal raised by the
    operation running inside the span is a different failure and keeps its own
    message.
    """
    entered = False
    try:
        with _active_profile_storage_span(
            settings,
            target_bucket_id=target_bucket_id,
            operator_scope_ports=operator_scope_ports,
        ) as bucket_id:
            entered = True
            yield bucket_id
    except AuthOperationRequiresCustodySessionError as exc:
        if entered:
            raise
        raise AuthOperationRequiresCustodySessionError(
            translated_message="application.auth.operator.errors.revoke_requires_custody_session",
            context=exc.context,
        ) from exc


def logout_operator_auth(
    *,
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    provider: str | None = None,
    all_providers: bool = False,
    target_bucket_id: str | None = None,
    settings: Settings | None = None,
    operator_scope_ports: OperatorScopePorts,
) -> AuthLogoutResult:
    """Terminate persisted sessions while preserving provider configuration."""
    if settings is not None:
        with _revocation_storage_span(
            settings,
            target_bucket_id=target_bucket_id,
            operator_scope_ports=operator_scope_ports,
        ):
            return logout_operator_auth(
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                provider=provider,
                all_providers=all_providers,
                target_bucket_id=target_bucket_id,
                settings=None,
                operator_scope_ports=operator_scope_ports,
            )
    resolved_settings = load_settings()
    with _revocation_storage_span(
        resolved_settings,
        target_bucket_id=target_bucket_id,
        operator_scope_ports=operator_scope_ports,
    ) as bucket_id:
        if bucket_id is None:
            raise AuthConfigureNoActiveBucketError(
                translated_message="application.auth.operator.errors.no_active_bucket",
            )
        from ..workflow.persistence import workflow_state_repository

        with _auth_mutation_span(
            settings=resolved_settings,
            bucket_id=bucket_id,
            operator_scope_ports=operator_scope_ports,
        ):
            repository = workflow_state_repository()
            started_at = now()

            def prepare(state: WorkflowState) -> WorkflowState:
                _assert_certificate_secret_mutation_not_in_progress(state)
                existing = state.auth.cleanup_intent
                if existing is not None:
                    assert_logout_request_matches(
                        existing,
                        provider=provider,
                        all_providers=all_providers,
                    )
                    return state
                scope = resolve_auth_operation_scope(
                    bucket_id=bucket_id,
                    current_provider=state.auth.provider,
                    provider=provider,
                    all_providers=all_providers,
                )
                intent = build_auth_cleanup_intent(
                    certificate_secret_backend_factory=certificate_secret_backend_factory,
                    settings=resolved_settings,
                    bucket_id=bucket_id,
                    auth=state.auth,
                    provider_ids=scope.provider_ids,
                    all_providers=all_providers,
                    operation_kind=AuthCleanupOperationKind.LOGOUT,
                    started_at=started_at,
                )
                if not auth_cleanup_intent_has_effects(intent):
                    return state
                return state.model_copy(
                    update={"auth": state.auth.model_copy(update={"cleanup_intent": intent})},
                )

            prepared = repository.update(prepare)
            intent = prepared.auth.cleanup_intent
            if intent is None:
                scope = resolve_auth_operation_scope(
                    bucket_id=bucket_id,
                    current_provider=prepared.auth.provider,
                    provider=provider,
                    all_providers=all_providers,
                )
                return AuthLogoutResult(
                    bucket_id=bucket_id,
                    providers=scope.provider_ids,
                    removed_sessions=0,
                    cleared_session_state=False,
                )
            delete_scoped_sessions(
                resolved_settings,
                intent.session_provider_ids,
                bucket_id=bucket_id,
            )
            operation_id = intent.operation_id
            operation_started_at = intent.started_at

            def finalize(state: WorkflowState) -> tuple[WorkflowState, tuple[BucketEvent, ...]]:
                current_intent = state.auth.cleanup_intent
                if current_intent is None:
                    return state, ()
                if current_intent.operation_id != operation_id:
                    raise InternalInvariantError("auth cleanup intent changed during a serialized logout")
                clears_current = _logout_state_matches_intent(state.auth, intent)
                cleared_auth = state.auth.model_copy(
                    update={
                        **({"authenticated_at": None, "subject": None} if clears_current else {}),
                        "cleanup_intent": None,
                    },
                )
                clears_session_state = clears_current and intent.had_session_state
                event_provider_ids = _logout_event_provider_ids(
                    state.auth.provider,
                    clears_session_state=clears_session_state,
                    intent=intent,
                )
                updated = append_auth_bucket_events(
                    state.model_copy(update={"auth": cleared_auth}),
                    tuple(("auth.session.cleared", provider_id) for provider_id in event_provider_ids),
                )

                durable_events = _logout_durable_events(
                    event_provider_ids,
                    operation_id=operation_id,
                    occurred_at=operation_started_at,
                )
                if not durable_events:
                    return updated, ()
                return updated, _build_bucket_events(
                    bucket_id=bucket_id,
                    events=durable_events,
                )

            finalized = repository.update_with_bucket_events(finalize)
            cleared_session_state = (
                intent.had_session_state
                and finalized.auth.provider == intent.provider_at_start
                and finalized.auth.authenticated_at is None
                and finalized.auth.subject is None
            )
    return AuthLogoutResult(
        bucket_id=intent.bucket_id,
        providers=intent.provider_ids,
        removed_sessions=len(intent.session_provider_ids),
        cleared_session_state=cleared_session_state,
    )


def _logout_state_matches_intent(auth: AuthState, intent: AuthCleanupIntent) -> bool:
    """Whether cleanup may clear the currently configured and verified provider."""
    return (
        auth.provider in intent.provider_ids
        and auth.provider == intent.provider_at_start
        and auth.configured_at == intent.configured_at_at_start
        and auth.authenticated_at == intent.authenticated_at_at_start
    )


def _logout_event_provider_ids(
    current_provider: str | None,
    *,
    clears_session_state: bool,
    intent: AuthCleanupIntent,
) -> tuple[str, ...]:
    """Order the current session first, then preserve the recorded provider order."""
    return tuple(
        dict.fromkeys(
            (
                *(
                    (current_provider,)
                    if clears_session_state and (current_provider is not None and current_provider)
                    else ()
                ),
                *intent.session_provider_ids,
            ),
        ),
    )


def _logout_durable_events(
    provider_ids: tuple[str, ...],
    *,
    operation_id: str,
    occurred_at: datetime,
) -> tuple[_BucketEventSpec, ...]:
    """Build the append-only logout evidence for each session removed."""
    from ...domain.buckets.event import BucketEventType

    return tuple(
        _BucketEventSpec(
            BucketEventType.AUTH_SESSION_CLEARED,
            provider_id,
            {"provider_id": provider_id, "operation": "logout", "operation_id": operation_id},
            occurred_at,
        )
        for provider_id in provider_ids
    )


def reset_operator_auth(
    *,
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    provider: str | None = None,
    all_providers: bool = False,
    target_bucket_id: str | None = None,
    settings: Settings | None = None,
    operator_scope_ports: OperatorScopePorts,
) -> AuthResetResult:
    """Remove auth custody through one durable, resumable reset operation."""
    if settings is not None:
        with _revocation_storage_span(
            settings,
            target_bucket_id=target_bucket_id,
            operator_scope_ports=operator_scope_ports,
        ):
            return reset_operator_auth(
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                provider=provider,
                all_providers=all_providers,
                target_bucket_id=target_bucket_id,
                settings=None,
                operator_scope_ports=operator_scope_ports,
            )
    resolved_settings = load_settings()
    with _revocation_storage_span(
        resolved_settings,
        target_bucket_id=target_bucket_id,
        operator_scope_ports=operator_scope_ports,
    ) as bucket_id:
        if bucket_id is None:
            raise AuthConfigureNoActiveBucketError(
                translated_message="application.auth.operator.errors.no_active_bucket",
            )
        from ..workflow.persistence import workflow_state_repository

        with _auth_mutation_span(
            settings=resolved_settings,
            bucket_id=bucket_id,
            operator_scope_ports=operator_scope_ports,
        ):
            repository = workflow_state_repository()
            started_at = now()

            def prepare(state: WorkflowState) -> WorkflowState:
                _assert_certificate_secret_mutation_not_in_progress(state)
                existing = state.auth.cleanup_intent
                if existing is not None:
                    assert_reset_request_matches(
                        existing,
                        provider=provider,
                        all_providers=all_providers,
                    )
                    return state
                scope = resolve_auth_operation_scope(
                    bucket_id=bucket_id,
                    current_provider=state.auth.provider,
                    provider=provider,
                    all_providers=all_providers,
                )
                intent = build_auth_cleanup_intent(
                    certificate_secret_backend_factory=certificate_secret_backend_factory,
                    settings=resolved_settings,
                    bucket_id=bucket_id,
                    auth=state.auth,
                    provider_ids=scope.provider_ids,
                    all_providers=all_providers,
                    operation_kind=AuthCleanupOperationKind.RESET,
                    started_at=started_at,
                )
                if not auth_cleanup_intent_has_effects(intent):
                    return state
                return state.model_copy(
                    update={"auth": state.auth.model_copy(update={"cleanup_intent": intent})},
                )

            prepared = repository.update(prepare)
            intent = prepared.auth.cleanup_intent
            if intent is None:
                scope = resolve_auth_operation_scope(
                    bucket_id=bucket_id,
                    current_provider=prepared.auth.provider,
                    provider=provider,
                    all_providers=all_providers,
                )
                return AuthResetResult(
                    bucket_id=bucket_id,
                    providers=scope.provider_ids,
                    removed_sessions=0,
                    cleared_provider_configuration=False,
                    cleared_locks=0,
                    removed_certificate_sources=0,
                    removed_certificate_secrets=0,
                )

            delete_scoped_sessions(
                resolved_settings,
                intent.session_provider_ids,
                bucket_id=bucket_id,
            )
            with bundled_indexed_authority().operation() as authority:
                preference_cleared = clear_profile_auth_preference(
                    profile_id=bucket_id,
                    providers=intent.provider_ids,
                    profile_decode_context=authority.profile_decode_context(),
                )
            # `auth reset` keeps its existing clearance for now. The ruling that
            # produced the held-lock refusal flagged this caller too -- the
            # profile survives here, so nothing compensates for an aborted
            # acquisition -- but the operator decision taken covered the
            # `login --reset-lock` path only, and widening it unasked would
            # change a second verb's behaviour on the strength of an inference.
            clear_scoped_locks(
                resolved_settings,
                intent.lock_provider_ids,
                bucket_id=bucket_id,
                allow_held=True,
            )
            delete_certificate_source_secrets(
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                settings=resolved_settings,
                bucket_id=bucket_id,
                names=intent.secret_source_names,
            )

            final_effects: dict[str, tuple[str, ...]] = {}

            def finalize(state: WorkflowState) -> tuple[WorkflowState, tuple[BucketEvent, ...]]:
                return _finalize_reset(state, intent=intent, bucket_id=bucket_id, final_effects=final_effects)

            repository.update_with_bucket_events(finalize)
            cleared_provider_ids = final_effects.get("provider_ids", ())
            removed_source_names = final_effects.get("certificate_names", ())
    return AuthResetResult(
        bucket_id=intent.bucket_id,
        providers=intent.provider_ids,
        removed_sessions=len(intent.session_provider_ids),
        cleared_provider_configuration=bool(cleared_provider_ids or removed_source_names or preference_cleared),
        cleared_locks=len(intent.lock_provider_ids),
        removed_certificate_sources=len(removed_source_names),
        removed_certificate_secrets=len(intent.secret_source_names),
    )


def _finalize_reset(
    state: WorkflowState,
    *,
    intent: AuthCleanupIntent,
    bucket_id: str,
    final_effects: dict[str, tuple[str, ...]],
) -> tuple[WorkflowState, tuple[BucketEvent, ...]]:
    current_intent = state.auth.cleanup_intent
    if current_intent is None:
        return state, ()
    if current_intent.operation_id != intent.operation_id:
        raise InternalInvariantError("auth reset intent changed during a serialized reset")
    reset_auth, provider_ids, certificate_names = apply_auth_cleanup_intent(
        state.auth,
        intent,
    )
    final_effects["provider_ids"] = provider_ids
    final_effects["certificate_names"] = certificate_names
    workflow_events: list[tuple[str, str]] = []
    workflow_events.extend(("auth.provider.cleared", provider_id) for provider_id in provider_ids)
    workflow_events.extend(("auth.session.cleared", provider_id) for provider_id in intent.session_provider_ids)
    workflow_events.extend(("auth.lock.cleared", provider_id) for provider_id in intent.lock_provider_ids)
    workflow_events.extend(("auth.certificate_source.removed", name) for name in certificate_names)
    updated = append_auth_bucket_events(
        state.model_copy(update={"auth": reset_auth}),
        tuple(workflow_events),
    )
    durable_events = auth_cleanup_bucket_events(
        intent=intent,
        provider_ids=provider_ids,
        certificate_names=certificate_names,
    )
    if not durable_events:
        return updated, ()
    return updated, _build_bucket_events(
        bucket_id=bucket_id,
        events=durable_events,
    )
