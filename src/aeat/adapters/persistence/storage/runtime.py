"""Storage runtime readiness models.

The runtime is the public diagnostic boundary for profile-bound secure
storage. It reports whether the current process is attached to an active
profile bucket and has an unlocked bucket session, without exposing key
material or constructing repositories. Repository factories are layered on
top of this contract in later plan steps.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from ....core.config import (
    Settings,
    StorageRouteKind,
    classify_storage_route,
    load_settings,
)
from .master_key._active_session import _active_session

if TYPE_CHECKING:
    from .sql.secure_objects import SecureObjectRepository

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")
_SYNTHETIC_SESSION_BUCKET_IDS = frozenset({"ephemeral"})


class StorageRuntimeReadinessCode(StrEnum):
    """Machine-readable secure-storage runtime readiness states."""

    READY = "ready"
    NO_ACTIVE_SESSION = "no_active_session"
    SESSION_SEALED = "session_sealed"
    SESSION_EXPIRED = "session_expired"
    UNSECURED_BACKEND = "unsecured_backend"
    ROUTE_NOT_ACTIVE_BUCKET = "route_not_active_bucket"
    ROUTE_BUCKET_MISMATCH = "route_bucket_mismatch"


class StorageRuntimeReadinessIssue(BaseModel):
    """One reason the runtime is not ready for profile-bound storage."""

    model_config = _STRICT_FROZEN

    code: StorageRuntimeReadinessCode
    message: str = Field(min_length=1)


class StorageRuntimeSession(BaseModel):
    """Key-material-free projection of the active bucket session."""

    model_config = _STRICT_FROZEN

    active: bool
    idle_deadline: datetime
    sealed: bool
    expired: bool
    unsecured_backend: bool


class StorageRuntimeReadiness(BaseModel):
    """Profile-bound storage readiness result."""

    model_config = _STRICT_FROZEN

    ready: bool
    code: StorageRuntimeReadinessCode
    issues: tuple[StorageRuntimeReadinessIssue, ...] = ()


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
    bucket_id: str = Field(default="", exclude=True, repr=False)
    active_session: StorageRuntimeSession | None
    readiness: StorageRuntimeReadiness

    def require_ready(self) -> None:
        """Raise when this runtime cannot serve profile-bound storage."""

        if self.readiness.ready:
            return
        from .errors import StorageValidationError

        details = "; ".join(issue.message for issue in self.readiness.issues)
        if not details:
            details = "storage runtime reported no detailed readiness issue."
        raise StorageValidationError(
            f"storage runtime is not ready for profile-bound storage: {details}",
        )

    def secure_object_repository(self) -> SecureObjectRepository:
        """Create a bucket-attached secure-object repository for this runtime."""

        self.require_ready()
        self._require_current_active_session()
        from .sql.engine import create_engine_from_settings
        from .sql.secure_objects import SecureObjectRepository

        settings = Settings(
            aeat_local_storage_root=self.storage_root,
            aeat_active_profile=self.bucket_id,
            aeat_database_url="",
        )
        engine = create_engine_from_settings(settings)
        return SecureObjectRepository(engine=engine)

    def _require_current_active_session(self) -> None:
        """Refuse repository construction when the live session drifted."""

        from .errors import StorageValidationError

        active = _active_session.get()
        if active is None:
            raise StorageValidationError(
                "storage runtime is not ready for profile-bound storage: no active bucket session.",
            )
        now = datetime.now(UTC)
        if active.sealed:
            raise StorageValidationError(
                "storage runtime is not ready for profile-bound storage: active bucket session is sealed.",
            )
        if active.is_expired(now):
            raise StorageValidationError(
                "storage runtime is not ready for profile-bound storage: active bucket session has expired.",
            )
        if active.unsecured_backend:
            raise StorageValidationError(
                "storage runtime is not ready for profile-bound storage: active bucket session uses unsecured backend.",
            )
        if active.bucket_id not in _SYNTHETIC_SESSION_BUCKET_IDS and active.bucket_id != self.bucket_id:
            raise StorageValidationError(
                "storage runtime is not ready for profile-bound storage: active bucket session changed.",
            )


def inspect_storage_runtime(
    settings: Settings | None = None,
    *,
    now: datetime | None = None,
) -> StorageRuntime:
    """Return the current profile-bound secure-storage runtime state."""

    resolved = settings or load_settings()
    route = classify_storage_route(resolved)
    checked_at = now or datetime.now(UTC)
    active = _active_session.get()
    session = None
    issues: list[StorageRuntimeReadinessIssue] = []

    if active is None:
        issues.append(
            StorageRuntimeReadinessIssue(
                code=StorageRuntimeReadinessCode.NO_ACTIVE_SESSION,
                message=(
                    "no active bucket session; run `aeat config profile switch NAME` "
                    "to unlock a profile before invoking profile-bound storage."
                ),
            )
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
                StorageRuntimeReadinessIssue(
                    code=StorageRuntimeReadinessCode.SESSION_SEALED,
                    message=(
                        "the active bucket session is sealed; run `aeat config profile switch NAME` "
                        "to re-activate the profile."
                    ),
                )
            )
        elif expired:
            issues.append(
                StorageRuntimeReadinessIssue(
                    code=StorageRuntimeReadinessCode.SESSION_EXPIRED,
                    message=(
                        "the active bucket session has expired; run `aeat config profile switch NAME` "
                        "to re-activate the profile."
                    ),
                )
            )
        elif active.unsecured_backend:
            issues.append(
                StorageRuntimeReadinessIssue(
                    code=StorageRuntimeReadinessCode.UNSECURED_BACKEND,
                    message=(
                        "the active bucket session uses the unsecured backend; "
                        "production profile-bound storage requires file or keyring custody."
                    ),
                )
            )

    if route.kind is not StorageRouteKind.ACTIVE_BUCKET_DATABASE:
        issues.append(
            StorageRuntimeReadinessIssue(
                code=StorageRuntimeReadinessCode.ROUTE_NOT_ACTIVE_BUCKET,
                message="the primary database route is not attached to an active profile bucket.",
            )
        )
    elif (
        active is not None
        and active.bucket_id not in _SYNTHETIC_SESSION_BUCKET_IDS
        and route.bucket_id != active.bucket_id
    ):
        issues.append(
            StorageRuntimeReadinessIssue(
                code=StorageRuntimeReadinessCode.ROUTE_BUCKET_MISMATCH,
                message="the primary database route does not match the active bucket session.",
            )
        )

    ready = not issues
    readiness_code = StorageRuntimeReadinessCode.READY if ready else issues[0].code
    return StorageRuntime(
        route_kind=route.kind,
        route_attached_to_active_bucket=route.kind is StorageRouteKind.ACTIVE_BUCKET_DATABASE,
        route_has_database_path=route.database_path is not None,
        storage_root=resolved.aeat_local_storage_root,
        bucket_id=route.bucket_id if ready else "",
        active_session=session,
        readiness=StorageRuntimeReadiness(
            ready=ready,
            code=readiness_code,
            issues=tuple(issues),
        ),
    )


__all__ = [
    "StorageRuntime",
    "StorageRuntimeReadiness",
    "StorageRuntimeReadinessCode",
    "StorageRuntimeReadinessIssue",
    "StorageRuntimeSession",
    "inspect_storage_runtime",
]
