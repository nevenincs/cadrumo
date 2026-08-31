"""Concrete persistence adapter for the application login-session port."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TypeGuard
from uuid import UUID

from ....application.user_profile.login_session_port import (
    ProfileBucketSessionPort,
    ProfileLoginSessionPort,
    ProfileLoginThrottleEvaluationPort,
    ProfilePersistedSessionPort,
    ProfileSessionResumeOutcomePort,
)
from .custody.acceleration_receipt import (
    advance_persisted_profile_session_idle_deadline,
    delete_profile_session,
    mint_profile_session,
    profile_session_path,
    resume_profile_session,
)
from .custody.acceleration_receipt_crypto import PersistedProfileSession
from .custody.zeroise import zeroise
from .master_key.active_session import (
    bind_active_bucket_session,
    close_active_bucket_session,
    current_active_bucket_session,
    session_serves_bucket,
)
from .master_key.bucket_session import BucketSession
from .master_key.login_throttle import evaluate_login_throttle, record_login_failure, reset_login_throttle


def bucket_session(session: ProfileBucketSessionPort) -> BucketSession:
    if not isinstance(session, BucketSession):
        raise TypeError("bucket session is not owned by the persistence substrate")
    return session


def _persisted_receipt(record: ProfilePersistedSessionPort) -> PersistedProfileSession:
    if not isinstance(record, PersistedProfileSession):
        raise TypeError("acceleration receipt is not owned by the persistence substrate")
    return record


class _PersistenceProfileLoginSession:
    """Delegate the aggregate port to the canonical custody/session authorities."""

    def current_session(self) -> ProfileBucketSessionPort | None:
        return current_active_bucket_session()

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
        return BucketSession.open_resumed(
            bucket_id=bucket_id,
            dek=dek,
            idle_minutes=idle_minutes,
            opened_at=opened_at,
            idle_deadline=idle_deadline,
            absolute_deadline=absolute_deadline,
            storage_root=storage_root,
        )

    def bind_session(self, session: ProfileBucketSessionPort) -> None:
        bind_active_bucket_session(bucket_session(session))

    def close_active_session(self) -> None:
        close_active_bucket_session()

    def session_serves_bucket(self, session: ProfileBucketSessionPort | None, bucket_id: str) -> bool:
        resolved = None if session is None else bucket_session(session)
        return session_serves_bucket(resolved, bucket_id)

    def evaluate_throttle(
        self,
        *,
        storage_root: Path,
        bucket_id: str,
        now: datetime,
    ) -> ProfileLoginThrottleEvaluationPort:
        return evaluate_login_throttle(storage_root=storage_root, bucket_id=bucket_id, now=now)

    def record_login_failure(self, *, storage_root: Path, bucket_id: str, now: datetime) -> None:
        record_login_failure(storage_root=storage_root, bucket_id=bucket_id, now=now)

    def reset_throttle(self, *, storage_root: Path, bucket_id: str) -> None:
        reset_login_throttle(storage_root=storage_root, bucket_id=bucket_id)

    def acceleration_receipt_path(self, *, storage_root: Path, profile_id: UUID) -> Path:
        return profile_session_path(storage_root=storage_root, profile_id=profile_id)

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
        return mint_profile_session(
            storage_root=storage_root,
            profile_id=profile_id,
            custody_generation=custody_generation,
            dek_epoch=dek_epoch,
            dek=dek,
            now=now,
            idle_minutes=idle_minutes,
            absolute_minutes=absolute_minutes,
        )

    def resume_acceleration_receipt(
        self,
        *,
        storage_root: Path,
        profile_id: UUID,
        custody_generation: int,
        dek_epoch: str,
        now: datetime,
    ) -> tuple[ProfileSessionResumeOutcomePort, bytearray | None]:
        return resume_profile_session(
            storage_root=storage_root,
            profile_id=profile_id,
            custody_generation=custody_generation,
            dek_epoch=dek_epoch,
            now=now,
        )

    def delete_acceleration_receipt(self, *, storage_root: Path, profile_id: UUID) -> None:
        delete_profile_session(storage_root=storage_root, profile_id=profile_id)

    def advance_acceleration_idle_deadline(
        self,
        *,
        storage_root: Path,
        profile_id: UUID,
        record: ProfilePersistedSessionPort,
        new_idle_deadline: datetime,
    ) -> ProfilePersistedSessionPort:
        return advance_persisted_profile_session_idle_deadline(
            storage_root=storage_root,
            profile_id=profile_id,
            record=_persisted_receipt(record),
            new_idle_deadline=new_idle_deadline,
        )

    def is_persisted_receipt(self, record: object) -> TypeGuard[ProfilePersistedSessionPort]:
        return isinstance(record, PersistedProfileSession)

    def zeroise_owned_buffer(self, buffer: bytearray) -> None:
        zeroise(buffer)


def build_profile_login_session_port() -> ProfileLoginSessionPort:
    """Build a stateless adapter over the existing persistence authorities."""
    return _PersistenceProfileLoginSession()


__all__ = ["build_profile_login_session_port"]
