"""Canonical durable auth cleanup planning and application helpers."""

from __future__ import annotations

from datetime import datetime

from ...core.auth_provider import AuthProviderKind
from ...core.config import Settings
from ...core.external_constants import UTF_8_ENCODING
from ...core.hashing import sha256_hex
from ._mutation import AuthBucketEventSpec as _BucketEventSpec
from .acquisition_lock import (
    AuthAcquisitionLockState,
    clear_auth_acquisition_lock,
    inspect_auth_acquisition_lock,
)
from .catalogue import get_auth_provider
from .certificate_secret_backend import SecureStorageCertificateSecretBackend
from .models import (
    AuthCleanupCertificateSource,
    AuthCleanupIntent,
    AuthCleanupOperationKind,
    AuthState,
    CertificateSourceRecord,
)
from .operator_results import AuthOperationScopeConflictError
from .sessions import delete_persisted_session, persisted_session_exists


def implemented_kind(provider_id: str) -> AuthProviderKind | None:
    """Resolve an implemented provider id without accepting unknown values."""
    try:
        return AuthProviderKind(provider_id)
    except ValueError:
        return None


def delete_scoped_sessions(
    settings: Settings,
    provider_ids: tuple[str, ...],
    *,
    bucket_id: str,
) -> tuple[int, tuple[str, ...]]:
    """Delete sessions for the requested providers within one profile bucket."""
    removed = 0
    affected: list[str] = []
    for provider_id in provider_ids:
        kind = implemented_kind(provider_id)
        if kind is None:
            continue
        removed_for_provider = len(delete_persisted_session(settings, kind=kind, bucket_id=bucket_id))
        removed += removed_for_provider
        if removed_for_provider:
            affected.append(provider_id)
    return removed, tuple(affected)


def clear_scoped_locks(
    settings: Settings,
    provider_ids: tuple[str, ...],
    *,
    bucket_id: str,
    allow_held: bool = False,
) -> tuple[int, tuple[str, ...]]:
    """Clear acquisition locks for the requested providers and bucket."""
    cleared = 0
    affected: list[str] = []
    for provider_id in provider_ids:
        kind = implemented_kind(provider_id)
        if kind is None:
            continue
        status = clear_auth_acquisition_lock(
            settings,
            kind,
            reason="operator-auth-reset",
            bucket_id=bucket_id,
            allow_held=allow_held,
        )
        if status.state is not AuthAcquisitionLockState.ABSENT:
            cleared += 1
            affected.append(provider_id)
    return cleared, tuple(affected)


def clear_operator_auth_acquisition_locks(
    settings: Settings,
    *,
    bucket_id: str,
    allow_held: bool = False,
) -> tuple[str, ...]:
    """Clear every provider's acquisition lock for ``bucket_id`` without its key.

    The lock is a plaintext file under the token directory, outside the profile
    capsule, so clearing it needs no custody session -- and destroying the
    capsule does not reap it, which is why a caller erasing a profile clears it
    explicitly rather than leaving it to the deletion.

    Every implemented provider kind is swept because the workflow state naming
    the configured provider lives INSIDE the capsule and is unreadable while the
    profile is locked. Clearing an absent lock is a no-op, so the sweep costs a
    stat per kind and reports only the locks that were actually there.

    Returns:
        The provider ids whose lock was present and has been cleared.
    """
    _, affected = clear_scoped_locks(
        settings,
        tuple(kind.value for kind in AuthProviderKind),
        bucket_id=bucket_id,
        allow_held=allow_held,
    )
    return affected


def delete_certificate_source_secrets(bucket_id: str, names: tuple[str, ...]) -> int:
    """Delete the named certificate secrets from one bucket's secure backend."""
    backend = SecureStorageCertificateSecretBackend(bucket_id=bucket_id)
    return sum(backend.remove(name) for name in names)


def assert_logout_request_matches(
    intent: AuthCleanupIntent,
    *,
    provider: str | None,
    all_providers: bool,
) -> None:
    """Refuse when a durable logout intent differs from the current request."""
    if intent.operation_kind is not AuthCleanupOperationKind.LOGOUT:
        matches = False
    elif all_providers:
        matches = intent.all_providers
    elif provider is not None:
        matches = not intent.all_providers and intent.provider_ids == (get_auth_provider(provider).id,)
    else:
        matches = not intent.all_providers
    if not matches:
        raise AuthOperationScopeConflictError(
            translated_message="application.auth.operator.errors.scope_conflict",
        )


def auth_cleanup_intent_has_effects(intent: AuthCleanupIntent) -> bool:
    """Return whether a durable cleanup intent still names removable state."""
    if intent.operation_kind is AuthCleanupOperationKind.LOGOUT:
        return bool(intent.session_provider_ids or intent.had_session_state)
    return bool(
        intent.provider_configuration_ids
        or intent.session_provider_ids
        or intent.lock_provider_ids
        or intent.certificate_sources
        or intent.secret_source_names
    )


def assert_reset_request_matches(
    intent: AuthCleanupIntent,
    *,
    provider: str | None,
    all_providers: bool,
) -> None:
    """Refuse when a durable reset intent differs from the current request."""
    if intent.operation_kind is not AuthCleanupOperationKind.RESET:
        matches = False
    elif all_providers:
        matches = intent.all_providers
    elif provider is not None:
        matches = not intent.all_providers and intent.provider_ids == (get_auth_provider(provider).id,)
    else:
        matches = not intent.all_providers
    if not matches:
        raise AuthOperationScopeConflictError(
            translated_message="application.auth.operator.errors.scope_conflict",
        )


def _certificate_source_witnesses(
    auth: AuthState,
    *,
    certificate_targeted: bool,
) -> tuple[AuthCleanupCertificateSource, ...]:
    """Snapshot the certificate-source witnesses (sorted by name) when targeted."""
    if not certificate_targeted:
        return ()
    return tuple(
        AuthCleanupCertificateSource(name=record.name, registered_at=record.registered_at)
        for record in sorted(auth.certificate_sources.values(), key=lambda item: item.name)
    )


def _session_scoped_provider_ids(
    settings: Settings,
    provider_ids: tuple[str, ...],
    *,
    bucket_id: str,
) -> tuple[str, ...]:
    """Return the scoped providers that currently hold a persisted session."""
    return tuple(
        provider_id
        for provider_id in provider_ids
        if (kind := implemented_kind(provider_id)) is not None
        and persisted_session_exists(settings, kind, bucket_id=bucket_id)
    )


def _lock_scoped_provider_ids(
    settings: Settings,
    provider_ids: tuple[str, ...],
    *,
    bucket_id: str,
    destructive_reset: bool,
) -> tuple[str, ...]:
    """Return the scoped providers holding an acquisition lock (reset only)."""
    if not destructive_reset:
        return ()
    return tuple(
        provider_id
        for provider_id in provider_ids
        if (kind := implemented_kind(provider_id)) is not None
        and inspect_auth_acquisition_lock(settings, kind, bucket_id=bucket_id).state
        is not AuthAcquisitionLockState.ABSENT
    )


def _secret_scoped_source_names(
    bucket_id: str,
    certificate_sources: tuple[AuthCleanupCertificateSource, ...],
    *,
    certificate_targeted: bool,
) -> tuple[str, ...]:
    """Return the witnessed certificate sources whose secret exists (targeted only)."""
    if not certificate_targeted:
        return ()
    return tuple(
        source.name for source in certificate_sources if _certificate_source_secret_exists(bucket_id, source.name)
    )


def _configuration_scoped_provider_ids(
    auth: AuthState,
    provider_ids: tuple[str, ...],
    *,
    destructive_reset: bool,
    certificate_targeted: bool,
) -> tuple[str, ...]:
    """Return the provider configurations a reset clears (current + certificate custody)."""
    if not destructive_reset:
        return ()
    return tuple(
        dict.fromkeys(
            (
                *((auth.provider,) if auth.provider is not None and auth.provider in provider_ids else ()),
                *(
                    (AuthProviderKind.CERTIFICATE.value,)
                    if certificate_targeted
                    and (
                        auth.certificate_path is not None
                        or auth.certificate_sources
                        or auth.active_certificate_source is not None
                    )
                    else ()
                ),
            ),
        ),
    )


def _cleanup_operation_id(
    *,
    bucket_id: str,
    operation_kind: AuthCleanupOperationKind,
    provider_ids: tuple[str, ...],
    all_providers: bool,
    started_at: datetime,
) -> str:
    """Derive the durable cleanup identity (idempotent across resumes).

    The join format, field ordering, and ``started_at.isoformat()`` are the
    frozen identity material; a resume of the same operation must hash to the
    same ``operation_id``. ``started_at`` is a parameter read back off the
    persisted intent at the resume path, never a derivation-time clock read, so
    folding it in is what makes the address stable across resumes.
    """
    operation_material = "|".join(
        (
            bucket_id,
            operation_kind.value,
            ",".join(provider_ids),
            str(all_providers),
            started_at.isoformat(),
        ),
    )
    return sha256_hex(operation_material.encode(UTF_8_ENCODING))


def build_auth_cleanup_intent(
    *,
    settings: Settings,
    bucket_id: str,
    auth: AuthState,
    provider_ids: tuple[str, ...],
    all_providers: bool,
    operation_kind: AuthCleanupOperationKind,
    started_at: datetime,
) -> AuthCleanupIntent:
    destructive_reset = operation_kind is AuthCleanupOperationKind.RESET
    certificate_targeted = destructive_reset and AuthProviderKind.CERTIFICATE.value in provider_ids
    certificate_sources = _certificate_source_witnesses(auth, certificate_targeted=certificate_targeted)
    return AuthCleanupIntent(
        operation_id=_cleanup_operation_id(
            bucket_id=bucket_id,
            operation_kind=operation_kind,
            provider_ids=provider_ids,
            all_providers=all_providers,
            started_at=started_at,
        ),
        operation_kind=operation_kind,
        bucket_id=bucket_id,
        provider_ids=provider_ids,
        all_providers=all_providers,
        started_at=started_at,
        provider_at_start=auth.provider,
        configured_at_at_start=auth.configured_at,
        authenticated_at_at_start=auth.authenticated_at,
        had_session_state=(
            auth.provider in provider_ids and (auth.authenticated_at is not None or auth.subject is not None)
        ),
        certificate_path_at_start=auth.certificate_path,
        active_certificate_source_at_start=auth.active_certificate_source,
        certificate_sources=certificate_sources,
        provider_configuration_ids=_configuration_scoped_provider_ids(
            auth,
            provider_ids,
            destructive_reset=destructive_reset,
            certificate_targeted=certificate_targeted,
        ),
        session_provider_ids=_session_scoped_provider_ids(settings, provider_ids, bucket_id=bucket_id),
        lock_provider_ids=_lock_scoped_provider_ids(
            settings,
            provider_ids,
            bucket_id=bucket_id,
            destructive_reset=destructive_reset,
        ),
        secret_source_names=_secret_scoped_source_names(
            bucket_id,
            certificate_sources,
            certificate_targeted=certificate_targeted,
        ),
    )


def _clear_current_provider_state(
    auth: AuthState,
    intent: AuthCleanupIntent,
    updates: dict[str, object],
) -> str | None:
    """Clear the current provider's session state when its snapshot is unchanged.

    Records the clearing keys into ``updates`` and returns the cleared provider
    id, or ``None`` when the provider is out of scope or its readiness moved
    since the intent was witnessed.
    """
    provider_snapshot_unchanged = (
        auth.provider == intent.provider_at_start
        and auth.configured_at == intent.configured_at_at_start
        and auth.authenticated_at == intent.authenticated_at_at_start
    )
    if auth.provider in intent.provider_ids and provider_snapshot_unchanged:
        updates.update(
            provider=None,
            configured_at=None,
            authenticated_at=None,
            subject=None,
        )
        return auth.provider
    return None


def _prune_certificate_sources(
    auth: AuthState,
    intent: AuthCleanupIntent,
) -> tuple[dict[str, CertificateSourceRecord], list[str]]:
    """Drop each witnessed certificate source whose (name + ``registered_at``) still matches.

    Returns the pruned source map and the removed source names.
    """
    sources = dict(auth.certificate_sources)
    removed_certificate_names: list[str] = []
    for witness in intent.certificate_sources:
        current = sources.get(witness.name)
        if current is None or current.registered_at != witness.registered_at:
            continue
        del sources[witness.name]
        removed_certificate_names.append(witness.name)
    return sources, removed_certificate_names


def _clear_certificate_custody(
    auth: AuthState,
    intent: AuthCleanupIntent,
    updates: dict[str, object],
) -> tuple[list[str], bool]:
    """Remove witnessed certificate sources, secrets, and path from custody.

    Records certificate-configuration keys into ``updates`` and returns the
    removed certificate-source names and whether any certificate configuration
    changed. A certificate source is removed only when its witness (name +
    ``registered_at``) still matches; the ``certificate_path`` is cleared only
    when no active source survives.
    """
    if AuthProviderKind.CERTIFICATE.value not in intent.provider_ids:
        return [], False
    sources, removed_certificate_names = _prune_certificate_sources(auth, intent)
    if sources != auth.certificate_sources:
        updates["certificate_sources"] = sources
    active_source = auth.active_certificate_source
    if active_source == intent.active_certificate_source_at_start and active_source in removed_certificate_names:
        active_source = None
        updates["active_certificate_source"] = None
    surviving_active = active_source is not None and active_source in sources
    if (
        intent.certificate_path_at_start is not None
        and auth.certificate_path == intent.certificate_path_at_start
        and not surviving_active
    ):
        updates["certificate_path"] = None
    certificate_configuration_changed = any(
        key in updates
        for key in (
            "certificate_sources",
            "active_certificate_source",
            "certificate_path",
        )
    )
    return removed_certificate_names, certificate_configuration_changed


def apply_auth_cleanup_intent(
    auth: AuthState,
    intent: AuthCleanupIntent,
) -> tuple[AuthState, tuple[str, ...], tuple[str, ...]]:
    """Apply one validated cleanup intent to the encrypted auth state."""
    updates: dict[str, object] = {"cleanup_intent": None}
    cleared_provider_ids: list[str] = []
    cleared_current = _clear_current_provider_state(auth, intent, updates)
    if cleared_current is not None:
        cleared_provider_ids.append(cleared_current)

    removed_certificate_names, certificate_configuration_changed = _clear_certificate_custody(auth, intent, updates)
    if certificate_configuration_changed:
        cleared_provider_ids.append(AuthProviderKind.CERTIFICATE.value)

    return (
        auth.model_copy(update=updates),
        tuple(dict.fromkeys(cleared_provider_ids)),
        tuple(removed_certificate_names),
    )


def auth_cleanup_bucket_events(
    *,
    intent: AuthCleanupIntent,
    provider_ids: tuple[str, ...],
    certificate_names: tuple[str, ...],
) -> tuple[_BucketEventSpec, ...]:
    """Project durable bucket events for one completed auth cleanup intent."""
    from ...domain.buckets.event import BucketEventType

    common = {"operation": "reset", "operation_id": intent.operation_id}
    events: list[_BucketEventSpec] = []
    events.extend(
        _BucketEventSpec(
            BucketEventType.AUTH_PROVIDER_CLEARED,
            provider_id,
            {**common, "provider_id": provider_id},
            intent.started_at,
        )
        for provider_id in provider_ids
    )
    events.extend(
        _BucketEventSpec(
            BucketEventType.AUTH_SESSION_CLEARED,
            provider_id,
            {**common, "provider_id": provider_id},
            intent.started_at,
        )
        for provider_id in intent.session_provider_ids
    )
    events.extend(
        _BucketEventSpec(
            BucketEventType.AUTH_LOCK_CLEARED,
            provider_id,
            {**common, "provider_id": provider_id},
            intent.started_at,
        )
        for provider_id in intent.lock_provider_ids
    )
    events.extend(
        _BucketEventSpec(
            BucketEventType.AUTH_CERTIFICATE_SOURCE_REMOVED,
            name,
            {**common, "name": name},
            intent.started_at,
        )
        for name in certificate_names
    )
    events.extend(
        _BucketEventSpec(
            BucketEventType.AUTH_CERTIFICATE_SOURCE_SECRET_REMOVED,
            name,
            {**common, "name": name},
            intent.started_at,
        )
        for name in intent.secret_source_names
    )
    return tuple(events)


def _certificate_source_secret_exists(bucket_id: str, name: str) -> bool:
    return SecureStorageCertificateSecretBackend(bucket_id=bucket_id).get(name) is not None


__all__ = [
    "apply_auth_cleanup_intent",
    "assert_logout_request_matches",
    "assert_reset_request_matches",
    "auth_cleanup_bucket_events",
    "auth_cleanup_intent_has_effects",
    "clear_operator_auth_acquisition_locks",
    "clear_scoped_locks",
    "delete_certificate_source_secrets",
    "delete_scoped_sessions",
    "implemented_kind",
]
