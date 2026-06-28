"""Crash-recoverable auth acquisition locks.

The lock protects live auth flows that can create external state,
especially Cl@ve Movil push petitions. It is intentionally
filesystem-backed so separate CLI processes share the same guard.
The lock file stores an :class:`AuthAcquisitionLockRecord` and reports
operator-safe state through :class:`AuthAcquisitionLockStatus`.
"""

from __future__ import annotations

import os
import socket
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, ValidationError

from ...core import STRICT_FROZEN_CONFIG
from ...core.errors import AeatError
from ...core.external_constants import UTF_8_ENCODING
from ...core.i18n import tr
from ...core.logging import get_logger
from ...core.time import now as _utc_now
from ...core.time._utc import coerce_utc_aware
from . import AuthProviderKind

if TYPE_CHECKING:
    from ...core.config import Settings

_log = get_logger(__name__)


class AuthAcquisitionLockState(StrEnum):
    """Observable states for the auth acquisition lock file."""

    ABSENT = "absent"
    HELD = "held"
    STALE = "stale"
    CORRUPT = "corrupt"


class AuthAcquisitionLockRecord(BaseModel):
    """Metadata written into an auth acquisition lock file."""

    model_config = STRICT_FROZEN_CONFIG

    provider_kind: AuthProviderKind
    profile_name: str = Field(min_length=1)
    pid: int = Field(gt=0)
    hostname: str = Field(min_length=1)
    created_at: datetime
    expires_at: datetime
    operation: str = Field(min_length=1)


class AuthAcquisitionLockStatus(BaseModel):
    """Safe health/status view of an auth acquisition lock."""

    model_config = STRICT_FROZEN_CONFIG

    state: AuthAcquisitionLockState
    path: Path
    record: AuthAcquisitionLockRecord | None = None
    reason: str | None = None
    recoverable: bool = False

    @property
    def locked(self) -> bool:
        """Return True when another live process should block auth acquisition."""
        return self.state is AuthAcquisitionLockState.HELD


class AuthAcquisitionLockedError(AeatError):
    """Raised when another process is already acquiring AEAT auth."""


def auth_acquisition_lock_path(settings: Settings, kind: AuthProviderKind) -> Path:
    """Return the profile/provider-scoped lock path."""
    from ...core import require_active_bucket_id

    return settings.aeat_token_dir / f"{require_active_bucket_id()}-{kind.value}-auth.lock"


def inspect_auth_acquisition_lock(
    settings: Settings,
    kind: AuthProviderKind,
    *,
    now: datetime | None = None,
) -> AuthAcquisitionLockStatus:
    """Describe the current acquisition-lock health without mutating it.

    Returns an :class:`AuthAcquisitionLockStatus`.
    """
    path = auth_acquisition_lock_path(settings, kind)
    reference = coerce_utc_aware(now) if now is not None else datetime.now(UTC)
    if not path.exists():
        return AuthAcquisitionLockStatus(state=AuthAcquisitionLockState.ABSENT, path=path)
    try:
        record = AuthAcquisitionLockRecord.model_validate_json(path.read_text(encoding=UTF_8_ENCODING))
    except (OSError, ValidationError, ValueError) as exc:
        _log.debug(
            "auth acquisition lock metadata is unreadable; marking lock recoverable (%s: %s)",
            type(exc).__name__,
            exc,
        )
        return AuthAcquisitionLockStatus(
            state=AuthAcquisitionLockState.CORRUPT,
            path=path,
            reason=f"invalid lock metadata: {type(exc).__name__}",
            recoverable=True,
        )

    if record.expires_at <= reference:
        return AuthAcquisitionLockStatus(
            state=AuthAcquisitionLockState.STALE,
            path=path,
            record=record,
            reason="lock expired",
            recoverable=True,
        )
    if _same_host(record.hostname) and not _pid_is_running(record.pid):
        return AuthAcquisitionLockStatus(
            state=AuthAcquisitionLockState.STALE,
            path=path,
            record=record,
            reason="lock owner process is not running",
            recoverable=True,
        )
    return AuthAcquisitionLockStatus(state=AuthAcquisitionLockState.HELD, path=path, record=record)


def clear_auth_acquisition_lock(
    settings: Settings,
    kind: AuthProviderKind,
    *,
    reason: str = "operator-reset",
) -> AuthAcquisitionLockStatus:
    """Remove the acquisition lock and return the pre-reset status.

    Returns an :class:`AuthAcquisitionLockStatus` reflecting the state
    observed immediately before the file was removed.
    """
    status = inspect_auth_acquisition_lock(settings, kind)
    if status.state is not AuthAcquisitionLockState.ABSENT:
        _remove_lock_file(status.path)
        return status.model_copy(
            update={
                "reason": reason if status.reason is None else f"{status.reason}; reset={reason}",
                "recoverable": True,
            },
        )
    return status


@contextmanager
def acquire_auth_acquisition_lock(
    settings: Settings,
    kind: AuthProviderKind,
    *,
    ttl_seconds: int,
    operation: str = "auth-login",
) -> Iterator[AuthAcquisitionLockRecord]:
    """Acquire a crash-recoverable auth lock or raise a typed conflict.

    Yields an :class:`AuthAcquisitionLockRecord` while the lock is held.

    Stale/corrupt locks are removed automatically before a second
    atomic-create attempt. A live lock is never waited on or retried:
    callers fail early so they do not issue a duplicate Cl@ve petition.
    """
    path = auth_acquisition_lock_path(settings, kind)
    path.parent.mkdir(parents=True, exist_ok=True)
    now = _utc_now()
    from ...core import require_active_bucket_id

    record = AuthAcquisitionLockRecord(
        provider_kind=kind,
        profile_name=require_active_bucket_id(),
        pid=os.getpid(),
        hostname=socket.gethostname(),
        created_at=now,
        expires_at=now + timedelta(seconds=max(1, ttl_seconds)),
        operation=operation,
    )

    acquired = False
    for _attempt in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            status = inspect_auth_acquisition_lock(settings, kind)
            if status.recoverable:
                _remove_lock_file(path)
                continue
            raise AuthAcquisitionLockedError(
                translated_message="application.auth.acquisition_lock.errors.lock_held",
                context=_status_context(status),
                suggestion=tr("application.auth.acquisition_lock.errors.lock_held_suggestion"),
            ) from None
        try:
            with os.fdopen(fd, "w", encoding=UTF_8_ENCODING) as file:
                file.write(record.model_dump_json(indent=2))
                file.write("\n")
        except Exception:  # BROAD-EXCEPT-RATIONALE-ACQUISITION-LOCK-TEARDOWN
            _remove_lock_file(path)
            raise
        acquired = True
        break
    if not acquired:
        status = inspect_auth_acquisition_lock(settings, kind)
        raise AuthAcquisitionLockedError(
            translated_message="application.auth.acquisition_lock.errors.acquire_failed",
            context=_status_context(status),
        )

    try:
        yield record
    finally:
        _release_if_owner(path, record)


def auth_lock_ttl_seconds(settings: Settings, kind: AuthProviderKind) -> int:
    """Return the acquisition-lock TTL for a provider."""
    if kind is AuthProviderKind.CLAVE_MOVIL:
        return int(settings.aeat_clave_movil_timeout_ms / 1000) + settings.aeat_auth_clave_movil_lock_buffer_s
    return settings.aeat_auth_certificate_lock_ttl_s


def _status_context(status: AuthAcquisitionLockStatus) -> Mapping[str, object]:
    # Builds a structured context dict passed to AeatError(context=...).
    # dict[str, object] is the concrete type; Mapping is the narrowest correct
    # annotation since AeatError accepts Mapping[str, object] | None.
    context: dict[str, object] = {
        "state": status.state.value,
        "path": str(status.path),
        "recoverable": status.recoverable,
    }
    if status.reason is not None:
        context["reason"] = status.reason
    if status.record is not None:
        context.update(
            {
                "provider_kind": status.record.provider_kind.value,
                "profile_name": status.record.profile_name,
                "pid": status.record.pid,
                "hostname": status.record.hostname,
                "created_at": status.record.created_at.isoformat(),
                "expires_at": status.record.expires_at.isoformat(),
                "operation": status.record.operation,
            },
        )
    return context


def _release_if_owner(path: Path, expected: AuthAcquisitionLockRecord) -> None:
    try:
        observed = AuthAcquisitionLockRecord.model_validate_json(path.read_text(encoding=UTF_8_ENCODING))
    except (OSError, ValidationError, ValueError) as exc:
        _log.debug(
            "auth acquisition lock release skipped because owner metadata is unreadable (%s: %s)",
            type(exc).__name__,
            exc,
        )
        return
    if observed == expected:
        _remove_lock_file(path)


def _remove_lock_file(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return


def _same_host(hostname: str) -> bool:
    return hostname.lower() == socket.gethostname().lower()


def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if os.name == "nt":
        return _pid_is_running_windows(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _pid_is_running_windows(pid: int) -> bool:
    import ctypes

    process_query_limited_information = 0x1000
    still_active = 259
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        return False
    try:
        exit_code = ctypes.c_ulong()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return True
        return exit_code.value == still_active
    finally:
        kernel32.CloseHandle(handle)


__all__ = [
    "AuthAcquisitionLockRecord",
    "AuthAcquisitionLockState",
    "AuthAcquisitionLockStatus",
    "AuthAcquisitionLockedError",
    "acquire_auth_acquisition_lock",
    "auth_acquisition_lock_path",
    "auth_lock_ttl_seconds",
    "clear_auth_acquisition_lock",
    "inspect_auth_acquisition_lock",
]
