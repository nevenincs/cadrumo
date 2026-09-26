"""Every operation that opens a bucket session seals it or leaves it bound.

A bucket session owns cleartext key material. The process binds at most one,
so a session that is neither bound nor sealed is key material nothing can
reach any more. These cases count such sessions with the garbage collector
after real CLI commands and after the resume door displaces or fails.

The resume door needs an acceleration receipt, and a receipt needs an OS
keychain that test hosts refuse. The resume cases therefore compose the real
login-session adapter and replace only the keychain-backed receipt: its
resume supplies the genuine DEK that the passphrase unlocks, and its renewal
can be made to fail after the resumed session is bound.
"""

from __future__ import annotations

import gc
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import TypeGuard
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_cli_profile
from cadrumo.adapters.persistence.storage.master_key.active_session import current_active_bucket_session
from cadrumo.adapters.persistence.storage.master_key.bucket_session import BucketSession
from cadrumo.adapters.persistence.storage.profile_login_session import build_profile_login_session_port
from cadrumo.adapters.persistence.storage.tests.profile_storage_root_fixture import isolated_profile_storage_fixture
from cadrumo.entrypoints.cli.tests.cli_runner import invoke_cached_cli

from ....application.user_profile.custody_ports import (
    load_profile_custody_password_material,
    unlock_profile_custody_password,
)
from ....application.user_profile.login_handover import ProfileLoginHandoverJournal
from ....application.user_profile.login_session_port import (
    ProfileBucketSessionPort,
    ProfileLoginSessionPort,
    ProfileLoginThrottleEvaluationPort,
    ProfilePersistedSessionPort,
    ProfileSessionResumeOutcomePort,
    bind_profile_login_session_port,
)
from ....application.user_profile.profile_record_repository import profile_record_session_if_authenticated
from ....application.user_profile.session_admission import ProfileSessionAdmissionState, admit_profile_session
from ....core.config import load_settings
from ....core.paths import effective_storage_root
from ....core.profile_session import ProfileSessionRefusalReason
from ....core.time.clock import now
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.authority_artifact import ProfileDecodeContext

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_isolated = isolated_profile_storage_fixture(name="_isolated", dispose_engine_around=True)

_LEDGER_ADD = (
    "app", "ledger", "add", "--date", "2026-03-10", "--amount", "121.00",
    "--direction", "OUTGOING", "--description", "Supplier",
)  # fmt: skip


def _live_sessions() -> list[BucketSession]:
    gc.collect()
    return [candidate for candidate in gc.get_objects() if isinstance(candidate, BucketSession)]


@pytest.fixture
def unreachable_key_holders() -> Callable[[], list[BucketSession]]:
    """Report unsealed, unbound sessions opened since the case started.

    Sessions that already existed belong to other cases in this worker, so
    they are excluded rather than blamed on this one.
    """
    preexisting = _live_sessions()

    def report() -> list[BucketSession]:
        bound = current_active_bucket_session()
        return [
            candidate
            for candidate in _live_sessions()
            if not candidate.sealed
            and candidate is not bound
            and not any(candidate is existing for existing in preexisting)
        ]

    return report


def test_read_write_and_refusal_commands_leave_no_unreachable_session(
    unreachable_key_holders: Callable[[], list[BucketSession]],
) -> None:
    refused = invoke_cached_cli(["--format", "json", "app", "ledger", "list"])
    assert refused.exit_code != 0, refused.output
    assert unreachable_key_holders() == []

    register_cli_profile(label="first", log_in=False)
    first_session = current_active_bucket_session()
    assert first_session is not None

    written = invoke_cached_cli(list(_LEDGER_ADD))
    assert written.exit_code == 0, written.output
    assert unreachable_key_holders() == []

    register_cli_profile(label="second", log_in=False)
    assert first_session.sealed
    assert unreachable_key_holders() == []

    listed = invoke_cached_cli(["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    assert unreachable_key_holders() == []


@dataclass(frozen=True, slots=True)
class _ResumedRecord:
    profile_id: UUID
    session_id: UUID
    custody_generation: int
    dek_epoch: str
    issued_at: datetime
    idle_deadline: datetime
    absolute_deadline: datetime


@dataclass(frozen=True, slots=True)
class _ResumedOutcome:
    resumed: bool
    refusal: ProfileSessionRefusalReason | None
    record: ProfilePersistedSessionPort | None


class _ReceiptResumingPort:
    """The real login-session adapter with only the keychain-backed receipt replaced."""

    def __init__(self, real: ProfileLoginSessionPort, dek: bytes, *, refuse_renewal: bool = False) -> None:
        self._real = real
        self._dek = dek
        self._refuse_renewal = refuse_renewal

    def load_handover_journal(self, *, storage_root: Path) -> ProfileLoginHandoverJournal | None:
        return self._real.load_handover_journal(storage_root=storage_root)

    def save_handover_journal(self, *, storage_root: Path, journal: ProfileLoginHandoverJournal) -> None:
        self._real.save_handover_journal(storage_root=storage_root, journal=journal)

    def clear_handover_journal(self, *, storage_root: Path, journal: ProfileLoginHandoverJournal) -> None:
        self._real.clear_handover_journal(storage_root=storage_root, journal=journal)

    def current_session(self) -> ProfileBucketSessionPort | None:
        return self._real.current_session()

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
        return self._real.open_resumed_session(
            bucket_id=bucket_id,
            dek=dek,
            idle_minutes=idle_minutes,
            opened_at=opened_at,
            idle_deadline=idle_deadline,
            absolute_deadline=absolute_deadline,
            storage_root=storage_root,
        )

    def bind_session(self, session: ProfileBucketSessionPort) -> None:
        self._real.bind_session(session)

    def close_active_session(self) -> None:
        self._real.close_active_session()

    def session_serves_bucket(self, session: ProfileBucketSessionPort | None, bucket_id: str) -> bool:
        return self._real.session_serves_bucket(session, bucket_id)

    def evaluate_throttle(
        self, *, storage_root: Path, bucket_id: str, now: datetime
    ) -> ProfileLoginThrottleEvaluationPort:
        return self._real.evaluate_throttle(storage_root=storage_root, bucket_id=bucket_id, now=now)

    def record_login_failure(self, *, storage_root: Path, bucket_id: str, now: datetime) -> None:
        self._real.record_login_failure(storage_root=storage_root, bucket_id=bucket_id, now=now)

    def reset_throttle(self, *, storage_root: Path, bucket_id: str) -> None:
        self._real.reset_throttle(storage_root=storage_root, bucket_id=bucket_id)

    def acceleration_receipt_path(self, *, storage_root: Path, profile_id: UUID) -> Path:
        return self._real.acceleration_receipt_path(storage_root=storage_root, profile_id=profile_id)

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
        return self._real.mint_acceleration_receipt(
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
        del storage_root
        record = _ResumedRecord(
            profile_id=profile_id,
            session_id=uuid4(),
            custody_generation=custody_generation,
            dek_epoch=dek_epoch,
            issued_at=now,
            idle_deadline=now + timedelta(minutes=5),
            absolute_deadline=now + timedelta(minutes=30),
        )
        return _ResumedOutcome(resumed=True, refusal=None, record=record), bytearray(self._dek)

    def delete_acceleration_receipt(self, *, storage_root: Path, profile_id: UUID) -> None:
        self._real.delete_acceleration_receipt(storage_root=storage_root, profile_id=profile_id)

    def advance_acceleration_idle_deadline(
        self,
        *,
        storage_root: Path,
        profile_id: UUID,
        record: ProfilePersistedSessionPort,
        new_idle_deadline: datetime,
    ) -> ProfilePersistedSessionPort:
        if self._refuse_renewal:
            raise RuntimeError("receipt renewal refused")
        return self._real.advance_acceleration_idle_deadline(
            storage_root=storage_root,
            profile_id=profile_id,
            record=record,
            new_idle_deadline=new_idle_deadline,
        )

    def is_persisted_receipt(self, record: object) -> TypeGuard[ProfilePersistedSessionPort]:
        if self._refuse_renewal and isinstance(record, _ResumedRecord):
            return True
        return self._real.is_persisted_receipt(record)

    def zeroise_owned_buffer(self, buffer: bytearray) -> None:
        self._real.zeroise_owned_buffer(buffer)


@pytest.fixture
def decode_context() -> Iterator[ProfileDecodeContext]:
    with bundled_indexed_authority().operation() as operation:
        yield operation.profile_decode_context()


def _unlocked_dek(profile_id: str) -> bytes:
    material = load_profile_custody_password_material(UUID(profile_id), root=effective_storage_root())
    passphrase = load_settings().cadrumo_dev_test_database_password.get_secret_value()
    return unlock_profile_custody_password(material, password=passphrase).dek


def test_resuming_over_another_profile_seals_the_displaced_session(
    decode_context: ProfileDecodeContext,
    unreachable_key_holders: Callable[[], list[BucketSession]],
) -> None:
    first = register_cli_profile(label="first", log_in=False)
    second = register_cli_profile(label="second", log_in=False)
    displaced = current_active_bucket_session()
    assert displaced is not None
    assert displaced.bucket_id == second

    port = _ReceiptResumingPort(build_profile_login_session_port(), _unlocked_dek(first))
    with bind_profile_login_session_port(port):
        admission = admit_profile_session(bucket_id=first, profile_decode_context=decode_context, now=now())

    assert admission.state is ProfileSessionAdmissionState.RESUMED
    assert displaced.sealed
    resumed = current_active_bucket_session()
    assert resumed is not None
    assert resumed.bucket_id == first
    assert not resumed.sealed
    assert profile_record_session_if_authenticated(first, profile_decode_context=decode_context) is not None
    assert profile_record_session_if_authenticated(second, profile_decode_context=decode_context) is None
    assert unreachable_key_holders() == []


def test_a_resume_that_fails_after_opening_leaves_no_key_holder_and_nothing_bound(
    decode_context: ProfileDecodeContext,
    unreachable_key_holders: Callable[[], list[BucketSession]],
) -> None:
    first = register_cli_profile(label="first", log_in=False)
    second = register_cli_profile(label="second", log_in=False)
    displaced = current_active_bucket_session()
    assert displaced is not None
    assert displaced.bucket_id == second

    # The session opens, binds and activates record authority before the
    # receipt renewal fails with an error the renewal does not tolerate.
    port = _ReceiptResumingPort(build_profile_login_session_port(), _unlocked_dek(first), refuse_renewal=True)
    with bind_profile_login_session_port(port), pytest.raises(RuntimeError, match="receipt renewal refused"):
        admit_profile_session(bucket_id=first, profile_decode_context=decode_context, now=now())

    assert displaced.sealed
    assert current_active_bucket_session() is None
    assert profile_record_session_if_authenticated(first, profile_decode_context=decode_context) is None
    assert profile_record_session_if_authenticated(second, profile_decode_context=decode_context) is None
    assert unreachable_key_holders() == []
