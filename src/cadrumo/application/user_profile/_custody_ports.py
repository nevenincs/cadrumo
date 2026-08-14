"""Application ports for custody records supplied to profile lifecycle actions."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID


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
    "ProfileCustodyEnvelopePort",
    "ProfileCustodyRecoveryEnvelopePort",
    "ProfileCustodySentinelPort",
]
