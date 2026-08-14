"""Application ports for custody records supplied to profile lifecycle actions."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID


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

    def touch(self, now: datetime) -> None:
        """Advance the sliding idle deadline."""
        ...

    def is_expired(self, now: datetime) -> bool:
        """Return whether this session has crossed either deadline."""
        ...

    def close(self) -> None:
        """Zeroise and retire this session's local key material."""
        ...


class ProfileCustodyEnvelopePort(Protocol):
    """Opaque password-envelope contract accepted by custody transactions."""

    profile_id: UUID
    password_generation: int
    self_digest: str
    dek_epoch: str


class ProfileCustodySentinelPort(Protocol):
    """Opaque DEK-sentinel contract accepted by custody transactions."""

    profile_id: UUID


class ProfileCustodyRecoveryEnvelopePort(Protocol):
    """Opaque recovery-envelope contract forwarded to custody storage."""


__all__ = [
    "ProfileBucketSessionPort",
    "ProfileCustodyEnvelopePort",
    "ProfileCustodyRecoveryEnvelopePort",
    "ProfileCustodySentinelPort",
]
