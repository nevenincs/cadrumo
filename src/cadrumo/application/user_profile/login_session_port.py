"""Typed application boundary for profile login-session infrastructure.

The login transaction owns ordering, rollback, and operator-facing outcomes.
Persistence owns the live bucket session, throttle record, acceleration receipt,
and key-buffer wipe.  This module is the single dependency boundary between
those responsibilities: it declares the exact structural DTOs the application
observes and binds one concrete port for an explicit host lifetime.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, TypeGuard
from uuid import UUID

if TYPE_CHECKING:
    from ...core.profile_session import ProfileSessionRefusalReason


class ProfileBucketSessionPort(Protocol):
    """Live bucket-session capability exposed across the application boundary."""

    @property
    def bucket_id(self) -> str:
        """The bucket this live session was opened against."""
        ...

    @property
    def dek(self) -> bytes:
        """The session's bound data-encryption key."""
        ...

    @property
    def idle_deadline(self) -> datetime:
        """The sliding deadline the next activity advances."""
        ...

    @property
    def absolute_deadline(self) -> datetime:
        """The immutable cap no activity can extend."""
        ...

    @property
    def opened_at(self) -> datetime:
        """When this session was authenticated."""
        ...

    @property
    def unsecured_backend(self) -> bool:
        """Whether the session was opened over the explicitly unsecured backend."""
        ...

    @property
    def sealed(self) -> bool:
        """Whether this session has been closed and its key material zeroised."""
        ...

    def touch(self, now: datetime) -> None:
        """Advance the sliding idle deadline."""
        ...

    def is_expired(self, now: datetime) -> bool:
        """Return whether this session has crossed either deadline."""
        ...

    def close(self) -> None:
        """Zeroise and retire this session's local key material."""
        ...


class ProfilePersistedSessionPort(Protocol):
    """Persisted acceleration-receipt fields needed by login orchestration."""

    @property
    def profile_id(self) -> UUID:
        """The profile this receipt accelerates."""
        ...

    @property
    def session_id(self) -> UUID:
        """The receipt's own identity."""
        ...

    @property
    def custody_generation(self) -> int:
        """The custody generation this receipt was minted against."""
        ...

    @property
    def dek_epoch(self) -> str:
        """The DEK epoch this receipt was minted against."""
        ...

    @property
    def issued_at(self) -> datetime:
        """When the receipt was minted."""
        ...

    @property
    def idle_deadline(self) -> datetime:
        """The sliding deadline a resume may advance."""
        ...

    @property
    def absolute_deadline(self) -> datetime:
        """The immutable cap no resume can extend."""
        ...


class ProfileSessionResumeOutcomePort(Protocol):
    """Fail-closed persisted-session evaluation result."""

    @property
    def resumed(self) -> bool:
        """Whether the persisted receipt was accepted."""
        ...

    @property
    def refusal(self) -> ProfileSessionRefusalReason | None:
        """The typed reason a resume was refused, if it was."""
        ...

    @property
    def record(self) -> ProfilePersistedSessionPort | None:
        """The evaluated receipt, present whether or not it was accepted."""
        ...


class ProfileLoginThrottleEvaluationPort(Protocol):
    """Failed-login backoff decision exposed to the application."""

    @property
    def throttled(self) -> bool:
        """Whether the caller must wait before another attempt."""
        ...

    @property
    def remaining_seconds(self) -> int:
        """Seconds left on the current backoff window."""
        ...


class ProfileLoginSessionPort(Protocol):
    """Complete infrastructure capability used by the login-session aggregate.

    Methods return the persistence substrate's existing DTOs through structural
    protocols.  The boundary never copies them: live-session identity is part
    of rollback and the exact receipt instance anchors idle-deadline renewal.
    """

    def current_session(self) -> ProfileBucketSessionPort | None:
        """Return the process-bound live session, if one exists."""
        ...

    def open_resumed_session(
        self,
        *,
        bucket_id: str,
        dek: bytes,
        idle_minutes: int,
        opened_at: datetime,
        idle_deadline: datetime,
        absolute_deadline: datetime,
        storage_root: Path,
    ) -> ProfileBucketSessionPort:
        """Open one live session over the supplied authenticated DEK."""
        ...

    def bind_session(self, session: ProfileBucketSessionPort) -> None:
        """Bind one authenticated session to the process context."""
        ...

    def close_active_session(self) -> None:
        """Close and zeroise the process-bound live session."""
        ...

    def session_serves_bucket(self, session: ProfileBucketSessionPort | None, bucket_id: str) -> bool:
        """Return whether ``session`` serves the exact profile UUID."""
        ...

    def evaluate_throttle(
        self,
        *,
        storage_root: Path,
        bucket_id: str,
        now: datetime,
    ) -> ProfileLoginThrottleEvaluationPort:
        """Evaluate failed-login backoff before password derivation."""
        ...

    def record_login_failure(self, *, storage_root: Path, bucket_id: str, now: datetime) -> None:
        """Record one refused password proof without replacing its refusal."""
        ...

    def reset_throttle(self, *, storage_root: Path, bucket_id: str) -> None:
        """Clear the revocable failed-login backoff cache."""
        ...

    def acceleration_receipt_path(self, *, storage_root: Path, profile_id: UUID) -> Path:
        """Return the exact local receipt locator for one profile."""
        ...

    def mint_acceleration_receipt(
        self,
        *,
        storage_root: Path,
        profile_id: UUID,
        custody_generation: int,
        dek_epoch: str,
        dek: bytes,
        now: datetime,
        idle_minutes: int,
        absolute_minutes: int,
    ) -> ProfilePersistedSessionPort:
        """Mint and return the canonical persisted acceleration receipt."""
        ...

    def resume_acceleration_receipt(
        self,
        *,
        storage_root: Path,
        profile_id: UUID,
        custody_generation: int,
        dek_epoch: str,
        now: datetime,
    ) -> tuple[ProfileSessionResumeOutcomePort, bytearray | None]:
        """Evaluate one receipt and return its owned wipeable DEK buffer."""
        ...

    def delete_acceleration_receipt(self, *, storage_root: Path, profile_id: UUID) -> None:
        """Revoke one profile's split-knowledge acceleration receipt."""
        ...

    def advance_acceleration_idle_deadline(
        self,
        *,
        storage_root: Path,
        profile_id: UUID,
        record: ProfilePersistedSessionPort,
        new_idle_deadline: datetime,
    ) -> ProfilePersistedSessionPort:
        """Advance a receipt while preserving its concrete DTO identity."""
        ...

    def is_persisted_receipt(self, record: object) -> TypeGuard[ProfilePersistedSessionPort]:
        """Narrow a resume record to the canonical persisted receipt DTO."""
        ...

    def zeroise_owned_buffer(self, buffer: bytearray) -> None:
        """Overwrite the exact mutable key buffer owned by the caller."""
        ...


_BOUND_PROFILE_LOGIN_SESSION_PORT: ContextVar[ProfileLoginSessionPort] = ContextVar(
    "cadrumo_profile_login_session_port"
)


@contextmanager
def bind_profile_login_session_port(port: ProfileLoginSessionPort) -> Generator[ProfileLoginSessionPort]:
    """Bind one outward-composed port for the current host execution context."""
    token = _BOUND_PROFILE_LOGIN_SESSION_PORT.set(port)
    try:
        yield port
    finally:
        _BOUND_PROFILE_LOGIN_SESSION_PORT.reset(token)


def profile_login_session_port() -> ProfileLoginSessionPort:
    """Resolve the explicitly composed port for the current host context."""
    try:
        return _BOUND_PROFILE_LOGIN_SESSION_PORT.get()
    except LookupError as error:
        raise RuntimeError("profile login-session infrastructure has not been composed") from error


def profile_session_serves_bucket(session: ProfileBucketSessionPort | None, bucket_id: str) -> bool:
    """Return whether a live bucket session serves the exact profile UUID."""
    return profile_login_session_port().session_serves_bucket(session, bucket_id)


def profile_current_bucket_session() -> ProfileBucketSessionPort | None:
    """Observe the currently bound bucket session through the login-session port."""
    return profile_login_session_port().current_session()


def profile_bind_bucket_session(session: ProfileBucketSessionPort) -> None:
    """Bind one authenticated bucket session through the login-session port."""
    profile_login_session_port().bind_session(session)


def profile_advance_session_idle_deadline(
    *,
    storage_root: Path,
    profile_id: UUID,
    record: ProfilePersistedSessionPort,
    new_idle_deadline: datetime,
) -> ProfilePersistedSessionPort:
    """Advance one receipt without exposing its keychain key to the app."""
    return profile_login_session_port().advance_acceleration_idle_deadline(
        storage_root=storage_root,
        profile_id=profile_id,
        record=record,
        new_idle_deadline=new_idle_deadline,
    )


def profile_is_persisted_session(record: object) -> TypeGuard[ProfilePersistedSessionPort]:
    """Return whether an outcome record is the persistence-owned receipt DTO."""
    return profile_login_session_port().is_persisted_receipt(record)


__all__ = [
    "ProfileBucketSessionPort",
    "ProfileLoginSessionPort",
    "ProfileLoginThrottleEvaluationPort",
    "ProfilePersistedSessionPort",
    "ProfileSessionResumeOutcomePort",
    "bind_profile_login_session_port",
    "profile_advance_session_idle_deadline",
    "profile_bind_bucket_session",
    "profile_current_bucket_session",
    "profile_is_persisted_session",
    "profile_login_session_port",
    "profile_session_serves_bucket",
]
