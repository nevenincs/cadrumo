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
from .errors import StorageValidationError
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
    message_key: str = Field(min_length=1)
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

        details = "; ".join(issue.message for issue in self.readiness.issues)
        if not details:
            details = "storage runtime reported no detailed readiness issue."
        raise StorageValidationError(
            f"storage runtime is not ready for profile-bound storage: {details}",
            context={"details": _render_readiness_details(self.readiness.issues)},
            translated_message="errors.storage.runtime.not_ready",
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
        )
        engine = create_engine_from_settings(settings)
        return SecureObjectRepository(engine=engine)

    def _require_current_active_session(self) -> None:
        """Refuse repository construction when the live session drifted."""

        active = _active_session.get()
        if active is None:
            raise _runtime_not_ready_error(
                "storage runtime is not ready for profile-bound storage: no active bucket session.",
                message_key="errors.storage.runtime.no_active_session",
            )
        now = datetime.now(UTC)
        if active.sealed:
            raise _runtime_not_ready_error(
                "storage runtime is not ready for profile-bound storage: active bucket session is sealed.",
                message_key="errors.storage.runtime.session_sealed",
            )
        if active.is_expired(now):
            raise _runtime_not_ready_error(
                "storage runtime is not ready for profile-bound storage: active bucket session has expired.",
                message_key="errors.storage.runtime.session_expired",
            )
        if active.unsecured_backend:
            raise _runtime_not_ready_error(
                "storage runtime is not ready for profile-bound storage: active bucket session uses unsecured backend.",
                message_key="errors.storage.runtime.unsecured_backend",
            )
        if active.bucket_id not in _SYNTHETIC_SESSION_BUCKET_IDS and active.bucket_id != self.bucket_id:
            raise _runtime_not_ready_error(
                "storage runtime is not ready for profile-bound storage: active bucket session changed.",
                message_key="errors.storage.runtime.session_changed",
            )


def _runtime_not_ready_error(message: str, *, message_key: str) -> StorageValidationError:
    from ....core.i18n import tr

    return StorageValidationError(
        message,
        context={"details": tr(message_key)},
        translated_message="errors.storage.runtime.not_ready",
    )


def _readiness_issue(
    *,
    code: StorageRuntimeReadinessCode,
    message: str,
    message_key: str,
) -> StorageRuntimeReadinessIssue:
    return StorageRuntimeReadinessIssue(code=code, message=message, message_key=message_key)


def _render_readiness_details(issues: tuple[StorageRuntimeReadinessIssue, ...]) -> str:
    from ....core.i18n import tr

    rendered = tuple(tr(issue.message_key) for issue in issues)
    if not rendered:
        return tr("errors.storage.runtime.no_detail")
    return "; ".join(rendered)


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
            _readiness_issue(
                code=StorageRuntimeReadinessCode.NO_ACTIVE_SESSION,
                message_key="errors.storage.runtime.no_active_session",
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
                _readiness_issue(
                    code=StorageRuntimeReadinessCode.SESSION_SEALED,
                    message_key="errors.storage.runtime.session_sealed",
                    message=(
                        "the active bucket session is sealed; run `aeat config profile switch NAME` "
                        "to re-activate the profile."
                    ),
                )
            )
        elif expired:
            issues.append(
                _readiness_issue(
                    code=StorageRuntimeReadinessCode.SESSION_EXPIRED,
                    message_key="errors.storage.runtime.session_expired",
                    message=(
                        "the active bucket session has expired; run `aeat config profile switch NAME` "
                        "to re-activate the profile."
                    ),
                )
            )
        elif active.unsecured_backend:
            issues.append(
                _readiness_issue(
                    code=StorageRuntimeReadinessCode.UNSECURED_BACKEND,
                    message_key="errors.storage.runtime.unsecured_backend",
                    message=(
                        "the active bucket session uses the unsecured backend; "
                        "production profile-bound storage requires file or keyring custody."
                    ),
                )
            )

    if route.kind is not StorageRouteKind.ACTIVE_BUCKET_DATABASE:
        issues.append(
            _readiness_issue(
                code=StorageRuntimeReadinessCode.ROUTE_NOT_ACTIVE_BUCKET,
                message_key="errors.storage.runtime.route_not_active_bucket",
                message="the primary database route is not attached to an active profile bucket.",
            )
        )
    elif (
        active is not None
        and active.bucket_id not in _SYNTHETIC_SESSION_BUCKET_IDS
        and route.bucket_id != active.bucket_id
    ):
        issues.append(
            _readiness_issue(
                code=StorageRuntimeReadinessCode.ROUTE_BUCKET_MISMATCH,
                message_key="errors.storage.runtime.route_bucket_mismatch",
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


def inspect_bucket_storage_runtime(
    bucket_id: str,
    settings: Settings | None = None,
    *,
    now: datetime | None = None,
) -> StorageRuntime:
    """Return runtime readiness for a named profile bucket.

    Explicit database URLs remain fail-closed: when the live settings
    carry an explicit primary database route, the runtime reports that
    route as unready instead of synthesizing a clean bucket route.
    """

    trimmed = bucket_id.strip()
    if not trimmed:
        raise ValueError("bucket_id must not be blank")
    resolved = settings or load_settings()
    current_route = classify_storage_route(resolved)
    if (
        "aeat_database_url" in resolved.model_fields_set
        and current_route.kind is StorageRouteKind.EXPLICIT_DATABASE_URL
    ):
        return inspect_storage_runtime(resolved, now=now)
    bucket_settings = Settings(
        aeat_local_storage_root=resolved.aeat_local_storage_root,
        aeat_active_profile=trimmed,
        aeat_database_url="",
    )
    explicit_fields = set(bucket_settings.model_fields_set)
    explicit_fields.discard("aeat_database_url")
    object.__setattr__(bucket_settings, "__pydantic_fields_set__", explicit_fields)
    return inspect_storage_runtime(bucket_settings, now=now)


__all__ = [
    "StorageRuntime",
    "StorageRuntimeReadiness",
    "StorageRuntimeReadinessCode",
    "StorageRuntimeReadinessIssue",
    "StorageRuntimeSession",
    "inspect_bucket_storage_runtime",
    "inspect_storage_runtime",
]
