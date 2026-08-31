"""Storage runtime readiness models.

The runtime is the public diagnostic boundary for profile-bound secure
storage. It reports whether the current process is attached to an active
profile bucket and has an unlocked bucket session, without exposing key
material or constructing repositories. The :class:`SecureObjectRepository`
factories are layered on top of this readiness contract.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ....core.config import (
    Settings,
    StorageRouteKind,
    classify_storage_route,
    load_settings,
    settings_for_active_profile_bucket,
)
from ....core.time.clock import now as _utc_now
from .errors import (
    storage_validation_error as _storage_validation_error,
)
from .master_key.active_session import current_active_bucket_session, session_serves_bucket
from .namespace_registry import STORAGE_NAMESPACE_REGISTRY
from .runtime_readiness import (
    StorageRuntimeReadiness,
    StorageRuntimeReadinessCode,
    StorageRuntimeReadinessIssue,
    StorageRuntimeSession,
    readiness_error,
    readiness_issue,
    runtime_not_ready_error,
)

if TYPE_CHECKING:
    from .sql.secure_objects import SecureObjectRepository

from ....core.identity import BucketId
from ....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN

_SYNTHETIC_SESSION_BUCKET_IDS = frozenset({"ephemeral"})


class StorageRuntime(BaseModel):
    """Current secure-storage runtime state.

    This model deliberately carries only redacted diagnostics: route kind,
    active-session state, and readiness. It does not expose KEK/DEK bytes,
    profile UUIDs, database URLs, database paths, or storage-root paths.
    """

    model_config = _STRICT_FROZEN

    route_kind: StorageRouteKind
    route_attached_to_active_bucket: bool
    route_has_database_path: bool
    storage_root: Path = Field(exclude=True, repr=False)
    bucket_id: BucketId | None = Field(default=None, exclude=True, repr=False)
    active_session: StorageRuntimeSession | None
    readiness: StorageRuntimeReadiness

    def require_ready(self) -> None:
        """Raise when this runtime cannot serve profile-bound storage."""
        if self.readiness.ready:
            return

        raise readiness_error(self.readiness)

    def secure_object_repository(self) -> SecureObjectRepository:
        """Create a :class:`SecureObjectRepository` attached to this runtime's bucket."""
        self.require_ready()
        self._require_current_active_session()
        from .sql.secure_objects import SecureObjectRepository

        active = current_active_bucket_session()
        assert active is not None
        bucket_id = self.bucket_id
        assert bucket_id is not None
        # The active bucket session owns the engine lifecycle: acquire the
        # engine through it so the handle is registered on the session and
        # disposed on session close/switch, rather than left to a caller.
        #
        # The route is passed as a factory because the session caches its
        # engine after the first storage access, and every later access
        # discarded this Settings unread. Building it eagerly cost a full
        # model validation -- which re-resolves every configured path against
        # the filesystem -- on each of the three repository constructions a
        # single profile write performs.
        engine = active.acquire_engine(
            lambda: Settings(
                cadrumo_local_storage_root=self.storage_root,
                cadrumo_active_profile=bucket_id,
            ),
        )
        return SecureObjectRepository(
            engine=engine,
            namespace_registry=STORAGE_NAMESPACE_REGISTRY,
            active_session_bucket_id=active.bucket_id,
            require_secure_active_session=True,
        )

    def _require_current_active_session(self) -> None:
        """Refuse repository construction when the live session drifted."""
        active = current_active_bucket_session()
        if active is None:
            raise runtime_not_ready_error(StorageRuntimeReadinessCode.NO_ACTIVE_SESSION)
        now = _utc_now()
        if active.sealed:
            raise runtime_not_ready_error(StorageRuntimeReadinessCode.SESSION_SEALED)
        if active.is_expired(now):
            raise runtime_not_ready_error(StorageRuntimeReadinessCode.SESSION_EXPIRED)
        if active.unsecured_backend:
            raise runtime_not_ready_error(StorageRuntimeReadinessCode.UNSECURED_BACKEND)
        bucket_id = self.bucket_id
        if bucket_id is None:
            raise runtime_not_ready_error(StorageRuntimeReadinessCode.ROUTE_NOT_ACTIVE_BUCKET)
        if active.bucket_id not in _SYNTHETIC_SESSION_BUCKET_IDS and not session_serves_bucket(active, bucket_id):
            raise runtime_not_ready_error(StorageRuntimeReadinessCode.SESSION_CHANGED)


def inspect_storage_runtime(
    settings: Settings | None = None,
    *,
    now: datetime | None = None,
) -> StorageRuntime:
    """Return the current profile-bound secure-storage :class:`StorageRuntime` state."""
    resolved = settings or load_settings()
    route = classify_storage_route(resolved)
    checked_at = now or _utc_now()
    active = current_active_bucket_session()
    session = None
    issues: list[StorageRuntimeReadinessIssue] = []

    if active is None:
        issues.append(
            readiness_issue(
                code=StorageRuntimeReadinessCode.NO_ACTIVE_SESSION,
            ),
        )
    else:
        expired = active.is_expired(checked_at)
        session = StorageRuntimeSession(
            active=True,
            idle_deadline=active.idle_deadline,
            sealed=active.sealed,
            expired=expired,
            unsecured_backend=active.unsecured_backend,
        )
        if active.sealed:
            issues.append(
                readiness_issue(
                    code=StorageRuntimeReadinessCode.SESSION_SEALED,
                ),
            )
        elif expired:
            issues.append(
                readiness_issue(
                    code=StorageRuntimeReadinessCode.SESSION_EXPIRED,
                ),
            )
        elif active.unsecured_backend:
            issues.append(
                readiness_issue(
                    code=StorageRuntimeReadinessCode.UNSECURED_BACKEND,
                ),
            )

    if route.kind is not StorageRouteKind.ACTIVE_BUCKET_DATABASE:
        issues.append(
            readiness_issue(
                code=StorageRuntimeReadinessCode.ROUTE_NOT_ACTIVE_BUCKET,
            ),
        )
    elif (
        active is not None
        and active.bucket_id not in _SYNTHETIC_SESSION_BUCKET_IDS
        and route.bucket_id != active.bucket_id
    ):
        issues.append(
            readiness_issue(
                code=StorageRuntimeReadinessCode.ROUTE_BUCKET_MISMATCH,
            ),
        )

    ready = not issues
    readiness_code = StorageRuntimeReadinessCode.READY if ready else issues[0].code
    return StorageRuntime(
        route_kind=route.kind,
        route_attached_to_active_bucket=route.kind is StorageRouteKind.ACTIVE_BUCKET_DATABASE,
        route_has_database_path=route.database_path is not None,
        storage_root=resolved.cadrumo_local_storage_root,
        bucket_id=route.bucket_id if ready else None,
        active_session=session,
        readiness=StorageRuntimeReadiness(
            ready=ready,
            code=readiness_code,
            issues=tuple(issues),
        ),
    )


def inspect_bucket_storage_runtime(
    bucket_id: str,
    settings: Settings | None = None,
    *,
    now: datetime | None = None,
) -> StorageRuntime:
    """Return a :class:`StorageRuntime` with readiness diagnostics for a named profile bucket.

    Explicit database URLs remain fail-closed: when the live settings
    carry an explicit primary database route, the runtime reports that
    route as unready instead of synthesizing a clean bucket route.
    """
    trimmed = bucket_id.strip()
    if not trimmed:
        raise _storage_validation_error("bucket_id must not be blank")
    resolved = settings or load_settings()
    current_route = classify_storage_route(resolved)
    if (
        "cadrumo_database_url" in resolved.model_fields_set
        and current_route.kind is StorageRouteKind.EXPLICIT_DATABASE_URL
    ):
        return inspect_storage_runtime(resolved, now=now)
    return inspect_storage_runtime(_bucket_route_settings(trimmed, resolved), now=now)


def _bucket_route_settings(bucket_id: str, source: Settings) -> Settings:
    """Return ``source`` routed to ``bucket_id``, through the session memo when one owns it.

    The derivation itself stays in the core settings boundary
    (:func:`~core.config.settings_for_active_profile_bucket`); this only
    chooses whether to recompute it. When the live bucket session is the one
    being routed to, it holds the previous answer for exactly the lifetime
    that answer stays valid, so the repeated repository constructions behind
    one write share a single derivation.

    Anything else -- no session, or a session bound to a DIFFERENT bucket --
    derives fresh. A session only ever memoises its own bucket's route, so
    inspecting bucket B while bucket A is unlocked can never be served A's
    answer.
    """
    session = current_active_bucket_session()
    if session_serves_bucket(session, bucket_id) and not session.sealed:
        return session.routed_settings(source)
    return settings_for_active_profile_bucket(bucket_id, source)


__all__ = [
    "StorageRuntime",
    "StorageRuntimeReadiness",
    "StorageRuntimeReadinessCode",
    "StorageRuntimeReadinessIssue",
    "StorageRuntimeSession",
    "inspect_bucket_storage_runtime",
    "inspect_storage_runtime",
    "runtime_not_ready_error",
]
