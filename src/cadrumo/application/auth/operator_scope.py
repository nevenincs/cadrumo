"""Settings and active-profile storage scopes for auth operator services.

This module uses :class:`Settings` to derive the auth operator configuration.
"""

from __future__ import annotations

import os
import threading
from collections.abc import Generator
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel

from ...adapters.persistence.storage.bucket import acquire_lock, bucket_paths, release_lock
from ...adapters.persistence.storage.master_key import current_active_bucket_session, session_serves_bucket
from ...core import STRICT_FROZEN_CONFIG
from ...core.config import LIVE_READ_TEST_OPT_IN_SETTINGS_FIELD, Settings, load_settings
from ...core.identity import BucketId
from .catalogue import get_auth_provider, known_auth_provider_ids
from .operator_results import (
    AuthCleanupInProgressError,
    AuthOperationRequiresCustodySessionError,
    AuthOperationScopeConflictError,
    AuthProviderNotConfiguredError,
    CertificateSecretMutationInProgressError,
)

if TYPE_CHECKING:
    from ...adapters.persistence.storage.master_key import BucketSession
    from ..workflow import WorkflowState

_AUTH_OPERATOR_SETTINGS_SCOPE_FIELDS = (
    "cadrumo_local_storage_root",
    "cadrumo_active_profile",
    "cadrumo_secret_store_backend",
    "cadrumo_secret_store_dir",
    "cadrumo_blob_store_dir",
    "cadrumo_secret_passphrase",
    "cadrumo_token_dir",
    "cadrumo_auth_provider",
    LIVE_READ_TEST_OPT_IN_SETTINGS_FIELD,
    "cadrumo_certificate_path",
    "cadrumo_certificate_password_secret",
    "cadrumo_certificate_friendly_name",
    "cadrumo_cert_warn_days",
    "cadrumo_cert_critical_days",
    "cadrumo_clave_movil_dni_nie",
    "cadrumo_clave_movil_dni_fecha",
    "cadrumo_clave_movil_nie_soporte",
    "cadrumo_clave_prefer_non_qr",
    "cadrumo_clave_movil_timeout_ms",
)


@contextmanager
def auth_operator_settings_scope(settings: Settings | None) -> Generator[Settings]:
    """Yield a :class:`Settings` for auth-operator probes.

    Uses the supplied settings when provided, otherwise loads from the
    default path.
    """
    from ...core.config import override_settings

    if settings is None:
        yield load_settings()
        return
    overrides = {
        field: getattr(settings, field)
        for field in _AUTH_OPERATOR_SETTINGS_SCOPE_FIELDS
        if field in settings.model_fields_set
    }
    for route_field in ("cadrumo_local_storage_root", "cadrumo_active_profile"):
        if route_field not in overrides:
            overrides[route_field] = getattr(load_settings(), route_field)
    with override_settings(**overrides) as scoped:
        yield scoped


def active_bucket_id_from_settings(settings: Settings) -> str | None:
    """Resolve the active bucket for ``settings`` without falling through to process globals."""
    from ..user_profile.profile_pointer import observe_active_profile_pointer

    override = (settings.cadrumo_active_profile or "").strip()
    if override:
        return override
    return observe_active_profile_pointer(settings.cadrumo_local_storage_root).bucket_id


def _canonical_storage_root(root: Path) -> str:
    """Return the comparison key for one local-storage root."""
    return os.path.normcase(str(root.expanduser().resolve(strict=False)))


def _is_explicitly_routed(
    settings: Settings | None,
    *,
    ambient_settings: Settings,
    ambient_storage_root: str,
) -> bool:
    """Report whether ``settings`` explicitly routes to a non-ambient storage root or profile.

    An explicit route is a caller-set storage root that differs from the
    ambient root, or a caller-set active profile that differs from the
    ambient profile.
    """
    if settings is None:
        return False
    return (
        "cadrumo_local_storage_root" in settings.model_fields_set
        and _canonical_storage_root(settings.cadrumo_local_storage_root) != ambient_storage_root
    ) or (
        "cadrumo_active_profile" in settings.model_fields_set
        and settings.cadrumo_active_profile != ambient_settings.cadrumo_active_profile
    )


def _can_reuse_active_session(
    active_session: BucketSession | None,
    *,
    bucket_id: str,
    target_storage_root: str,
    ambient_storage_root: str,
    explicitly_routed: bool,
) -> bool:
    """Report whether the current bucket session already serves the target.

    Reuse requires the same bucket. A session with a recorded storage root
    reuses only on an exact root match; a session without one reuses only when
    the caller did not explicitly route and the ambient root matches the target.
    """
    if not session_serves_bucket(active_session, bucket_id):
        return False
    if active_session.storage_root is not None:
        return _canonical_storage_root(active_session.storage_root) == target_storage_root
    return not explicitly_routed and ambient_storage_root == target_storage_root


@contextmanager
def active_profile_storage_span(
    settings: Settings | None = None,
    *,
    target_bucket_id: str | None = None,
):
    """Return a storage context for the explicit target or active profile.

    Yields the resolved bucket id when the ambient :class:`BucketSession`
    already serves the target, and ``None`` when no target resolves at all.
    Anything else is a refusal: an auth operation aimed at a profile whose
    custody session is not open cannot borrow one, because opening it needs
    the operator's password. The caller is told to authenticate into that
    profile rather than silently reading whichever bucket happens to be bound.

    Raises:
        AuthOperationRequiresCustodySessionError: When a target bucket resolves
            but the ambient session does not serve it on the target root.
    """
    ambient_settings = load_settings()
    ambient_storage_root = _canonical_storage_root(ambient_settings.cadrumo_local_storage_root)
    explicitly_routed = _is_explicitly_routed(
        settings,
        ambient_settings=ambient_settings,
        ambient_storage_root=ambient_storage_root,
    )
    with auth_operator_settings_scope(settings) as resolved_settings:
        target_storage_root = _canonical_storage_root(resolved_settings.cadrumo_local_storage_root)
        bucket_id = target_bucket_id or active_bucket_id_from_settings(resolved_settings)
        if bucket_id is None:
            with nullcontext():
                yield None
            return
        active_session = current_active_bucket_session()
        if _can_reuse_active_session(
            active_session,
            bucket_id=bucket_id,
            target_storage_root=target_storage_root,
            ambient_storage_root=ambient_storage_root,
            explicitly_routed=explicitly_routed,
        ):
            with nullcontext():
                yield bucket_id
            return
        raise AuthOperationRequiresCustodySessionError(
            translated_message="application.auth.operator.errors.requires_custody_session",
            context={
                "bucket_id": bucket_id,
                "storage_root": target_storage_root,
            },
        )


def operator_auth_revocation_is_reachable(
    settings: Settings | None = None,
    *,
    bucket_id: str,
) -> bool:
    """Report whether an auth revocation for ``bucket_id`` could open its store.

    Asks :func:`active_profile_storage_span` instead of re-deriving its reuse
    test, so "is this profile's custody session open" keeps one authority.
    Entering the span yields a null context and performs no mutation, so this
    is a question rather than a half-executed operation.

    A caller erasing a profile it has NOT unlocked uses this to choose between
    a real revocation and the key-free half, rather than driving control flow
    off a caught refusal.
    """
    try:
        with active_profile_storage_span(settings, target_bucket_id=bucket_id) as resolved:
            return resolved is not None
    except AuthOperationRequiresCustodySessionError:
        return False


@dataclass(slots=True)
class _AuthMutationOwnership:
    root: Path
    bucket_id: str
    pid: int
    thread_id: int
    depth: int


_AUTH_MUTATION_OWNERSHIP = threading.local()


@contextmanager
def auth_mutation_span(*, settings: Settings, bucket_id: str) -> Generator[None]:
    """Acquire or re-enter the canonical per-bucket auth mutation span."""
    root = settings.cadrumo_local_storage_root.expanduser().resolve(strict=False)
    current_pid = os.getpid()
    current_thread_id = threading.get_ident()
    ownership = getattr(_AUTH_MUTATION_OWNERSHIP, "current", None)
    if isinstance(ownership, _AuthMutationOwnership):
        if (
            ownership.root != root
            or ownership.bucket_id != bucket_id
            or ownership.pid != current_pid
            or ownership.thread_id != current_thread_id
        ):
            raise RuntimeError("nested auth mutation targets a different bucket or execution owner")
        ownership.depth += 1
        try:
            yield
        finally:
            ownership.depth -= 1
        return

    paths = bucket_paths(root, bucket_id)
    acquire_lock(paths, wait_seconds=settings.cadrumo_file_lock_timeout_s)
    ownership = _AuthMutationOwnership(
        root=root,
        bucket_id=bucket_id,
        pid=current_pid,
        thread_id=current_thread_id,
        depth=1,
    )
    _AUTH_MUTATION_OWNERSHIP.current = ownership
    try:
        yield
    finally:
        ownership.depth = 0
        del _AUTH_MUTATION_OWNERSHIP.current
        release_lock(paths)


def assert_auth_cleanup_not_in_progress(state: WorkflowState) -> None:
    """Refuse a new auth mutation while logout/reset recovery is pending."""
    intent = state.auth.cleanup_intent
    if intent is None:
        return
    raise AuthCleanupInProgressError(
        translated_message="application.auth.operator.errors.cleanup_in_progress",
        context={
            "operation": intent.operation_kind.value,
            "bucket_id": intent.bucket_id,
        },
    )


def assert_certificate_secret_mutation_not_in_progress(state: WorkflowState) -> None:
    """Refuse an auth mutation while certificate-secret recovery is pending."""
    intent = state.auth.certificate_secret_mutation_intent
    if intent is None:
        return
    raise CertificateSecretMutationInProgressError(
        translated_message="application.auth.operator.errors.certificate_secret_mutation_in_progress",
        context={
            "operation": intent.event_kind.value,
            "name": intent.source_name,
            "bucket_id": intent.bucket_id,
        },
    )


def assert_auth_recovery_not_in_progress(state: WorkflowState) -> None:
    """Refuse a new auth mutation while any durable auth recovery is pending."""
    assert_auth_cleanup_not_in_progress(state)
    assert_certificate_secret_mutation_not_in_progress(state)


class AuthOperationScope(BaseModel):
    """Resolved bucket and provider ids for an operator auth mutation."""

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    provider_ids: tuple[str, ...]


def resolve_auth_operation_scope(
    *,
    bucket_id: str,
    current_provider: str | None,
    provider: str | None,
    all_providers: bool,
) -> AuthOperationScope:
    """Resolve one explicit provider, every known provider, or the configured provider."""
    if provider is not None and all_providers:
        raise AuthOperationScopeConflictError(
            translated_message="application.auth.operator.errors.scope_conflict",
        )
    if all_providers:
        provider_ids = known_auth_provider_ids()
    elif provider is not None:
        provider_ids = (get_auth_provider(provider).id,)
    elif current_provider:
        provider_ids = (get_auth_provider(current_provider).id,)
    else:
        raise AuthProviderNotConfiguredError(
            translated_message="application.auth.operator.errors.provider_not_configured",
        )
    return AuthOperationScope(bucket_id=bucket_id, provider_ids=provider_ids)


__all__ = [
    "AuthOperationScope",
    "active_bucket_id_from_settings",
    "active_profile_storage_span",
    "assert_auth_cleanup_not_in_progress",
    "assert_auth_recovery_not_in_progress",
    "assert_certificate_secret_mutation_not_in_progress",
    "auth_mutation_span",
    "auth_operator_settings_scope",
    "operator_auth_revocation_is_reachable",
    "resolve_auth_operation_scope",
]
