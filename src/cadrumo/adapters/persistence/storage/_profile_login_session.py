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
from . import custody, master_key


def _bucket_session(session: ProfileBucketSessionPort) -> master_key.BucketSession:
    if not isinstance(session, master_key.BucketSession):
        raise TypeError("bucket session is not owned by the persistence substrate")
    return session


def _persisted_receipt(record: ProfilePersistedSessionPort) -> custody.PersistedProfileSession:
    if not isinstance(record, custody.PersistedProfileSession):
        raise TypeError("acceleration receipt is not owned by the persistence substrate")
    return record


class _PersistenceProfileLoginSession:
    """Delegate the aggregate port to the canonical custody/session authorities."""

    def current_session(self) -> ProfileBucketSessionPort | None:
        return master_key.current_active_bucket_session()

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
        return master_key.BucketSession.open_resumed(
            bucket_id=bucket_id,
            dek=dek,
            idle_minutes=idle_minutes,
            opened_at=opened_at,
            idle_deadline=idle_deadline,
            absolute_deadline=absolute_deadline,
            storage_root=storage_root,
        )

    def bind_session(self, session: ProfileBucketSessionPort) -> None:
        master_key.bind_active_bucket_session(_bucket_session(session))

    def close_active_session(self) -> None:
        master_key.close_active_bucket_session()

    def session_serves_bucket(self, session: ProfileBucketSessionPort | None, bucket_id: str) -> bool:
        resolved = None if session is None else _bucket_session(session)
        return master_key.session_serves_bucket(resolved, bucket_id)

    def evaluate_throttle(
        self,
        *,
        storage_root: Path,
        bucket_id: str,
        now: datetime,
    ) -> ProfileLoginThrottleEvaluationPort:
        return master_key.evaluate_login_throttle(storage_root=storage_root, bucket_id=bucket_id, now=now)

    def record_login_failure(self, *, storage_root: Path, bucket_id: str, now: datetime) -> None:
        master_key.record_login_failure(storage_root=storage_root, bucket_id=bucket_id, now=now)

    def reset_throttle(self, *, storage_root: Path, bucket_id: str) -> None:
        master_key.reset_login_throttle(storage_root=storage_root, bucket_id=bucket_id)

    def acceleration_receipt_path(self, *, storage_root: Path, profile_id: UUID) -> Path:
        return custody.profile_session_path(storage_root=storage_root, profile_id=profile_id)

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
        return custody.mint_profile_session(
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
        return custody.resume_profile_session(
            storage_root=storage_root,
            profile_id=profile_id,
            custody_generation=custody_generation,
            dek_epoch=dek_epoch,
            now=now,
        )

    def delete_acceleration_receipt(self, *, storage_root: Path, profile_id: UUID) -> None:
        custody.delete_profile_session(storage_root=storage_root, profile_id=profile_id)

    def advance_acceleration_idle_deadline(
        self,
        *,
        storage_root: Path,
        profile_id: UUID,
        record: ProfilePersistedSessionPort,
        new_idle_deadline: datetime,
    ) -> ProfilePersistedSessionPort:
        return custody.advance_persisted_profile_session_idle_deadline(
            storage_root=storage_root,
            profile_id=profile_id,
            record=_persisted_receipt(record),
            new_idle_deadline=new_idle_deadline,
        )

    def is_persisted_receipt(self, record: object) -> TypeGuard[ProfilePersistedSessionPort]:
        return isinstance(record, custody.PersistedProfileSession)

    def zeroise_owned_buffer(self, buffer: bytearray) -> None:
        custody.zeroise(buffer)


def build_profile_login_session_port() -> ProfileLoginSessionPort:
    """Build a stateless adapter over the existing persistence authorities."""
    return _PersistenceProfileLoginSession()


__all__ = ["build_profile_login_session_port"]
