"""Crash-recoverable auth acquisition locks.

The lock protects live auth flows that can create external state,
especially Cl@ve Movil push petitions. It is intentionally
filesystem-backed so separate CLI processes share the same guard.
The lock file stores an :class:`AuthAcquisitionLockRecord` and reports
operator-safe state through :class:`AuthAcquisitionLockStatus`.

Removal goes through :func:`~core.unlink_lockfile`: every peer that finds
the lock taken opens the file to read the record, and on Windows that open
refuses the owner's delete. An abandoned delete would leave a record naming a
live process, blocking acquisition until the record's TTL expires, so the
removal retries. It never raises -- the release runs in a ``finally`` where a
raise would mask the auth flow's own outcome, and the TTL is the backstop.
"""

from __future__ import annotations

import os
import socket
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, ValidationError

from ...core import (
    LOCKFILE_UNLINK_RETRY_SECONDS,
    STRICT_FROZEN_CONFIG,
    ActionEvidenceProvenance,
    AuthProviderKind,
    NoRecoveryOutcome,
    pid_is_alive,
    unlink_lockfile,
)
from ...core.errors.hierarchy import CadrumoError
from ...core.external_constants import UTF_8_ENCODING
from ...core.logging import get_logger
from ...core.time import coerce_utc_aware
from ...core.time import now as _utc_now
from ...core.time import now as clock_now
from ..operator_actions import PreconditionVerdict, no_action_precondition_verdict

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


class AuthAcquisitionLockedError(CadrumoError):
    """Raised when another process is already acquiring AEAT auth."""

    def __init__(
        self,
        *,
        status: AuthAcquisitionLockStatus,
        translated_message: str,
    ) -> None:
        """Retain the observed lock state as an explicit non-actionable verdict.

        A live acquisition must not be cleared or retried automatically: that
        could create the duplicate external petition the lock prevents. The
        status is therefore factual evidence with an operator-decision outcome,
        not a prose-derived recovery command.
        """
        super().__init__(
            translated_message=translated_message,
            context=_status_context(status),
        )
        condition_id = "auth.acquisition_lock.available"
        self._precondition_verdict = no_action_precondition_verdict(
            condition_id=condition_id,
            evidence_id="auth.acquisition_lock.state",
            facts={
                "lock_available": False,
                "lock_recoverable": status.recoverable,
                "lock_state": status.state.value,
            },
            provenance=ActionEvidenceProvenance.APPLICATION_STATE,
            outcome=NoRecoveryOutcome.OPERATOR_DECISION,
        )

    @property
    def terminal_precondition_verdict(self) -> PreconditionVerdict:
        """Expose the application-owned lock conflict to the generic CLI boundary."""
        return self._precondition_verdict


def auth_acquisition_lock_path(
    settings: Settings,
    kind: AuthProviderKind,
    *,
    bucket_id: str | None = None,
) -> Path:
    """Return the profile/provider-scoped lock path."""
    from ...core.bucket_pointer import require_active_bucket_id

    return settings.cadrumo_token_dir / f"{bucket_id or require_active_bucket_id()}-{kind.value}-auth.lock"


def inspect_auth_acquisition_lock(
    settings: Settings,
    kind: AuthProviderKind,
    *,
    now: datetime | None = None,
    bucket_id: str | None = None,
) -> AuthAcquisitionLockStatus:
    """Describe the current acquisition-lock health without mutating it.

    Returns an :class:`AuthAcquisitionLockStatus`.
    """
    status, _observed = _inspect_with_observed_text(settings, kind, now=now, bucket_id=bucket_id)
    return status


def _inspect_with_observed_text(
    settings: Settings,
    kind: AuthProviderKind,
    *,
    now: datetime | None = None,
    bucket_id: str | None = None,
) -> tuple[AuthAcquisitionLockStatus, str | None]:
    """Return the lock status together with the exact text the verdict was read from.

    The removal paths need the bytes the verdict describes, not just the
    verdict: a stale lock can be released and REPLACED by a live one between
    the inspection and the unlink, and deleting on the strength of the earlier
    verdict then destroys a lock its owner believes it holds. Carrying the
    observed text lets the deletion be a compare-and-delete against exactly
    what was judged. ``None`` means the file was absent or unreadable.
    """
    path = auth_acquisition_lock_path(settings, kind, bucket_id=bucket_id)
    reference = coerce_utc_aware(now) if now is not None else clock_now()
    try:
        observed = path.read_text(encoding=UTF_8_ENCODING)
    except FileNotFoundError:
        return AuthAcquisitionLockStatus(state=AuthAcquisitionLockState.ABSENT, path=path), None
    except OSError as exc:
        _log.debug(
            "auth acquisition lock file is unreadable; marking lock recoverable (%s: %s)",
            type(exc).__name__,
            exc,
        )
        return (
            AuthAcquisitionLockStatus(
                state=AuthAcquisitionLockState.CORRUPT,
                path=path,
                reason=f"invalid lock metadata: {type(exc).__name__}",
                recoverable=True,
            ),
            None,
        )
    try:
        record = AuthAcquisitionLockRecord.model_validate_json(observed)
    except (OSError, ValidationError, ValueError) as exc:
        _log.debug(
            "auth acquisition lock metadata is unreadable; marking lock recoverable (%s: %s)",
            type(exc).__name__,
            exc,
        )
        return (
            AuthAcquisitionLockStatus(
                state=AuthAcquisitionLockState.CORRUPT,
                path=path,
                reason=f"invalid lock metadata: {type(exc).__name__}",
                recoverable=True,
            ),
            observed,
        )

    if record.expires_at <= reference:
        return (
            AuthAcquisitionLockStatus(
                state=AuthAcquisitionLockState.STALE,
                path=path,
                record=record,
                reason="lock expired",
                recoverable=True,
            ),
            observed,
        )
    if _same_host(record.hostname) and not _pid_is_running(record.pid):
        return (
            AuthAcquisitionLockStatus(
                state=AuthAcquisitionLockState.STALE,
                path=path,
                record=record,
                reason="lock owner process is not running",
                recoverable=True,
            ),
            observed,
        )
    return (
        AuthAcquisitionLockStatus(state=AuthAcquisitionLockState.HELD, path=path, record=record),
        observed,
    )


def clear_auth_acquisition_lock(
    settings: Settings,
    kind: AuthProviderKind,
    *,
    reason: str = "operator-reset",
    bucket_id: str | None = None,
    allow_held: bool = False,
) -> AuthAcquisitionLockStatus:
    """Remove the acquisition lock and return the pre-reset status.

    Returns an :class:`AuthAcquisitionLockStatus` reflecting the state
    observed immediately before the file was removed.

    A HELD lock refuses unless the caller passes ``allow_held``. This function
    used to delete on any state but ABSENT, so a live holder's record was
    removed under the reason ``stale_reclaim`` and the next acquisition
    succeeded while the first holder was still authenticating -- two processes
    each believing they held the lock, which is a second petition to AEAT and
    a second prompt on the taxpayer's phone. The compare-and-delete below does
    not catch it: it guards against the bytes CHANGING, and a live holder's
    bytes are unchanged.

    Only a caller that is destroying the profile wholesale may pass
    ``allow_held``: there the lock is going with everything else, and refusing
    would strand the erase. A caller whose profile SURVIVES -- an auth reset,
    or ``login --reset-lock`` -- must not, because nothing there compensates
    for the aborted acquisition and the duplicate petition follows immediately.
    """
    status, observed = _inspect_with_observed_text(settings, kind, bucket_id=bucket_id)
    if status.state is AuthAcquisitionLockState.HELD and not allow_held:
        raise AuthAcquisitionLockedError(
            translated_message="application.auth.acquisition_lock.errors.lock_held",
            status=status,
        )
    if status.state is not AuthAcquisitionLockState.ABSENT:
        if not _remove_lock_file_if_unchanged(status.path, observed):
            # A replacement landed after the operator's snapshot; report the
            # live lock rather than deleting a record they never saw.
            return inspect_auth_acquisition_lock(settings, kind, bucket_id=bucket_id)
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
) -> Generator[AuthAcquisitionLockRecord]:
    """Acquire a crash-recoverable auth lock or raise a typed conflict.

    Yields an :class:`AuthAcquisitionLockRecord` while the lock is held.

    Stale/corrupt locks are removed automatically before a second
    atomic-create attempt. A live lock is never waited on or retried:
    callers fail early so they do not issue a duplicate Cl@ve petition.
    """
    path = auth_acquisition_lock_path(settings, kind)
    path.parent.mkdir(parents=True, exist_ok=True)
    now = _utc_now()
    from ...core.bucket_pointer import require_active_bucket_id

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
        except (FileExistsError, PermissionError):
            # Windows refuses this open with ``ERROR_ACCESS_DENIED`` while a
            # peer's removal of the same lock file is in flight. That is the
            # lock being contended, not a fault, so it routes to the same
            # inspect-and-maybe-reclaim branch as an outright collision.
            status, observed = _inspect_with_observed_text(settings, kind)
            if status.recoverable:
                # Compare-and-delete: when the stale record was replaced by a
                # live one after the verdict, retry the create rather than
                # destroying the replacement.
                _remove_lock_file_if_unchanged(path, observed)
                continue
            raise AuthAcquisitionLockedError(
                translated_message="application.auth.acquisition_lock.errors.lock_held",
                status=status,
            ) from None
        try:
            with os.fdopen(fd, "w", encoding=UTF_8_ENCODING) as file:
                file.write(record.model_dump_json(indent=2))
                file.write("\n")
        except Exception:  # BROAD-EXCEPT-RATIONALE-ACQUISITION-LOCK-TEARDOWN
            _remove_lock_file(path, reason="write_failure_teardown")
            raise
        acquired = True
        break
    if not acquired:
        status = inspect_auth_acquisition_lock(settings, kind)
        raise AuthAcquisitionLockedError(
            translated_message="application.auth.acquisition_lock.errors.acquire_failed",
            status=status,
        )

    try:
        yield record
    finally:
        _release_if_owner(path, record)


def auth_lock_ttl_seconds(settings: Settings, kind: AuthProviderKind) -> int:
    """Return the acquisition-lock TTL for a provider."""
    if kind is AuthProviderKind.CLAVE_MOVIL:
        return int(settings.cadrumo_clave_movil_timeout_ms / 1000) + settings.cadrumo_auth_clave_movil_lock_buffer_s
    return settings.cadrumo_auth_certificate_lock_ttl_s


def _status_context(status: AuthAcquisitionLockStatus) -> Mapping[str, object]:
    # Builds a structured context dict passed to CadrumoError(context=...).
    # dict[str, object] is the concrete type; Mapping is the narrowest correct
    # annotation since CadrumoError accepts Mapping[str, object] | None.
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
        _remove_lock_file(path, reason="release")


def _remove_lock_file(path: Path, *, reason: str) -> bool:
    """Delete the lock file, waiting out a peer that holds it open for inspection.

    Every caller that finds the lock taken opens it to read the record, and on
    Windows that open blocks this delete. Failing to delete strands a lock whose
    recorded PID is a live process, which blocks every later Cl@ve or
    certificate acquisition until the TTL in the record expires -- so the
    removal retries rather than giving up on the first refusal.

    Returns:
        ``True`` when the file is gone, ``False`` when a peer's handle outlasted
        the retry window and the record was left on disk.
    """
    if unlink_lockfile(path, retry_seconds=LOCKFILE_UNLINK_RETRY_SECONDS, reason=reason):
        return True
    _log.warning(
        "auth acquisition lock file could not be removed; it is held open by another process "
        "and will block acquisition until its recorded TTL expires (reason=%s path=%s)",
        reason,
        path,
    )
    return False


def _remove_lock_file_if_unchanged(path: Path, expected: str | None) -> bool:
    """Delete ``path`` only while it still holds ``expected``; report whether it went.

    A stale or corrupt verdict authorises removing THOSE bytes, not whatever
    the file happens to hold when the unlink runs. Without the comparison a
    lock released and reacquired between the inspection and the deletion is
    destroyed while its new owner believes it holds it -- that owner then
    issues a second Cl@ve petition, which is exactly what this lock exists to
    prevent.

    Returns:
        ``True`` when the file was removed or was already gone, ``False`` when
        it was left in place -- either because the content changed under the
        verdict, or because a peer's open handle kept the removal refused.
    """
    try:
        current = path.read_text(encoding=UTF_8_ENCODING)
    except FileNotFoundError:
        return True
    except OSError:
        # Unreadable now as well: the bytes cannot have been replaced by a
        # record a live owner is relying on, so removal stays authorised.
        return _remove_lock_file(path, reason="unreadable_reclaim")
    if expected is not None and current != expected:
        _log.debug("auth acquisition lock changed between inspection and removal; leaving it in place")
        return False
    return _remove_lock_file(path, reason="stale_reclaim")


def _same_host(hostname: str) -> bool:
    return hostname.lower() == socket.gethostname().lower()


def _pid_is_running(pid: int) -> bool:
    if pid == os.getpid():
        return True
    return pid_is_alive(pid)


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
