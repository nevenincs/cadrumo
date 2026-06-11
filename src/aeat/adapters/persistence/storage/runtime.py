"""Storage runtime readiness models.

The runtime is the public diagnostic boundary for profile-bound secure
storage. It reports whether the current process is attached to an active
profile bucket and has an unlocked bucket session, without exposing key
material or constructing repositories. The :class:`SecureObjectRepository`
factories are layered on top of this readiness contract.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, Field

from ....core.config import (
    Settings,
    StorageRouteKind,
    classify_storage_route,
    load_settings,
    settings_for_active_profile_bucket,
)
from ....core.external_constants import DEFAULT_OUTPUT_LANGUAGE
from ....core.logging import get_logger
from ....core.time import now as _utc_now
from ._namespace_registry import STORAGE_NAMESPACE_REGISTRY
from .errors import StorageValidationError
from .master_key._active_session import _active_session

if TYPE_CHECKING:
    from .sql.secure_objects import SecureObjectRepository

from ....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN

_SYNTHETIC_SESSION_BUCKET_IDS = frozenset({"ephemeral"})
_STORAGE_VALIDATION_MESSAGE_KEY: Final[str] = "errors.integrity.integrity_storage_validation"
_log = get_logger(__name__)


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
        """Create a :class:`SecureObjectRepository` attached to this runtime's bucket."""
        self.require_ready()
        self._require_current_active_session()
        from .sql.engine import get_engine
        from .sql.secure_objects import SecureObjectRepository

        active = _active_session.get()
        assert active is not None
        settings = Settings(
            aeat_local_storage_root=self.storage_root,
            aeat_active_profile=self.bucket_id,
        )
        engine = get_engine(settings)
        return SecureObjectRepository(
            engine=engine,
            namespace_registry=STORAGE_NAMESPACE_REGISTRY,
            active_session_bucket_id=active.bucket_id,
            require_secure_active_session=True,
        )

    def _require_current_active_session(self) -> None:
        """Refuse repository construction when the live session drifted."""
        active = _active_session.get()
        if active is None:
            raise _runtime_not_ready_error(
                "storage runtime is not ready for profile-bound storage: no active bucket session.",
                message_key="errors.storage.runtime.no_active_session",
            )
        now = _utc_now()
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


def runtime_not_ready_error(message: str, *, message_key: str) -> StorageValidationError:
    """Build a localized storage-runtime readiness failure returning a :class:`StorageValidationError`."""
    from ....core.i18n import tr

    return StorageValidationError(
        message,
        context={"details": tr(message_key, locale=_settings_output_language())},
        translated_message="errors.storage.runtime.not_ready",
    )


_runtime_not_ready_error = runtime_not_ready_error


def _storage_validation_error(message: str) -> StorageValidationError:
    return StorageValidationError(message, translated_message=_STORAGE_VALIDATION_MESSAGE_KEY)


def _readiness_issue(
    *,
    code: StorageRuntimeReadinessCode,
    message: str,
    message_key: str,
) -> StorageRuntimeReadinessIssue:
    return StorageRuntimeReadinessIssue(code=code, message=message, message_key=message_key)


def _render_readiness_details(issues: tuple[StorageRuntimeReadinessIssue, ...]) -> str:
    from ....core.i18n import tr

    locale = _settings_output_language()
    rendered = tuple(tr(issue.message_key, locale=locale) for issue in issues)
    if not rendered:
        return tr("errors.storage.runtime.no_detail", locale=locale)
    return "; ".join(rendered)


def _settings_output_language() -> str:
    """Resolve locale without consulting active-profile storage."""
    try:
        language = load_settings().aeat_output_language or DEFAULT_OUTPUT_LANGUAGE
    except (AttributeError, KeyError, ValueError):
        _log.debug("storage runtime could not resolve output language; using default", exc_info=True)
        return DEFAULT_OUTPUT_LANGUAGE.value
    return getattr(language, "value", str(language))


def inspect_storage_runtime(
    settings: Settings | None = None,
    *,
    now: datetime | None = None,
) -> StorageRuntime:
    """Return the current profile-bound secure-storage :class:`StorageRuntime` state."""
    resolved = settings or load_settings()
    route = classify_storage_route(resolved)
    checked_at = now or _utc_now()
    active = _active_session.get()
    session = None
    issues: list[StorageRuntimeReadinessIssue] = []

    if active is None:
        issues.append(
            _readiness_issue(
                code=StorageRuntimeReadinessCode.NO_ACTIVE_SESSION,
                message_key="errors.storage.runtime.no_active_session",
                message=(
                    "no active bucket session; run `aeat config switch NAME` "
                    "to unlock a profile before invoking profile-bound storage."
                ),
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
                _readiness_issue(
                    code=StorageRuntimeReadinessCode.SESSION_SEALED,
                    message_key="errors.storage.runtime.session_sealed",
                    message=(
                        "the active bucket session is sealed; run `aeat config switch NAME` to re-activate the profile."
                    ),
                ),
            )
        elif expired:
            issues.append(
                _readiness_issue(
                    code=StorageRuntimeReadinessCode.SESSION_EXPIRED,
                    message_key="errors.storage.runtime.session_expired",
                    message=(
                        "the active bucket session has expired; run `aeat config switch NAME` "
                        "to re-activate the profile."
                    ),
                ),
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
                ),
            )

    if route.kind is not StorageRouteKind.ACTIVE_BUCKET_DATABASE:
        issues.append(
            _readiness_issue(
                code=StorageRuntimeReadinessCode.ROUTE_NOT_ACTIVE_BUCKET,
                message_key="errors.storage.runtime.route_not_active_bucket",
                message="the primary database route is not attached to an active profile bucket.",
            ),
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
            ),
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
        "aeat_database_url" in resolved.model_fields_set
        and current_route.kind is StorageRouteKind.EXPLICIT_DATABASE_URL
    ):
        return inspect_storage_runtime(resolved, now=now)
    bucket_settings = settings_for_active_profile_bucket(trimmed, resolved)
    return inspect_storage_runtime(bucket_settings, now=now)


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
