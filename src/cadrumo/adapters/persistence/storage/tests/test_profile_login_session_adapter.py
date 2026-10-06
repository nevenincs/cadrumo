"""Exact-object contract for the concrete profile login-session adapter."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from cadrumo.core.profile_session import ProfileSessionRefusalReason

from ..custody.acceleration_receipt import ProfileSessionResumeOutcome, profile_session_path
from ..custody.acceleration_receipt_crypto import PersistedProfileSession
from ..custody.tests.receipt_sign_in import RECEIPT_LOGIN_ID, sign_in_custody
from ..errors import KeyringUnavailableError
from ..master_key.bucket_session import BucketSession
from ..master_key.login_throttle import ThrottleEvaluation
from ..profile_login_session import build_profile_login_session_port

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_PROFILE_ID = UUID("11111111-1111-4111-8111-111111111111")
_NOW = datetime(2026, 8, 25, 12, tzinfo=UTC)
_DEK = bytes(range(32))


def test_live_session_throttle_and_buffer_wipe_delegate_to_the_real_authorities(tmp_path: Path) -> None:
    port = build_profile_login_session_port()
    session = port.open_resumed_session(
        bucket_id=str(_PROFILE_ID),
        dek=_DEK,
        idle_minutes=15,
        opened_at=_NOW,
        idle_deadline=_NOW + timedelta(minutes=15),
        absolute_deadline=_NOW + timedelta(hours=4),
        storage_root=tmp_path,
    )

    assert isinstance(session, BucketSession)
    port.bind_session(session)
    assert port.current_session() is session
    assert port.session_serves_bucket(session, str(_PROFILE_ID)) is True

    initial = port.evaluate_throttle(storage_root=tmp_path, bucket_id=str(_PROFILE_ID), now=_NOW)
    assert isinstance(initial, ThrottleEvaluation)
    assert initial.throttled is False
    port.record_login_failure(storage_root=tmp_path, bucket_id=str(_PROFILE_ID), now=_NOW)
    refused = port.evaluate_throttle(storage_root=tmp_path, bucket_id=str(_PROFILE_ID), now=_NOW)
    assert refused.throttled is True
    port.reset_throttle(storage_root=tmp_path, bucket_id=str(_PROFILE_ID))
    assert port.evaluate_throttle(storage_root=tmp_path, bucket_id=str(_PROFILE_ID), now=_NOW).throttled is False

    owned = bytearray(_DEK)
    port.zeroise_owned_buffer(owned)
    assert owned == bytearray(32)

    port.close_active_session()
    assert session.sealed is True
    assert port.current_session() is None


def test_receipt_lifecycle_preserves_exact_metadata_and_wipeable_key_buffer(tmp_path: Path) -> None:
    port = build_profile_login_session_port()
    receipt_path = port.acceleration_receipt_path(storage_root=tmp_path, profile_id=_PROFILE_ID)
    sign_in = sign_in_custody(tmp_path, _PROFILE_ID, custody_generation=3)
    captured = sign_in.establish().current
    try:
        minted = port.mint_acceleration_receipt(
            storage_root=tmp_path,
            profile_id=_PROFILE_ID,
            custody_generation=3,
            dek_epoch="epoch-3",
            dek=_DEK,
            now=_NOW,
            idle_minutes=15,
            absolute_minutes=240,
            login_id=RECEIPT_LOGIN_ID,
            sign_in_binding=sign_in.binding,
            sign_in_generation=captured,
        )
    except KeyringUnavailableError:
        assert not receipt_path.exists()
        return

    try:
        assert isinstance(minted, PersistedProfileSession)
        assert minted.sign_in == captured == sign_in.observe().current
        assert minted.profile_id == _PROFILE_ID
        assert minted.custody_generation == 3
        assert minted.dek_epoch == "epoch-3"
        assert minted.issued_at == _NOW
        assert minted.idle_deadline == _NOW + timedelta(minutes=15)
        assert minted.absolute_deadline == _NOW + timedelta(hours=4)

        borrowed, proof = port.borrow_acceleration_receipt_key(storage_root=tmp_path, profile_id=_PROFILE_ID)
        assert borrowed.resumed and proof is not None
        resumed, key_buffer = port.resume_acceleration_receipt_with_key(
            storage_root=tmp_path,
            profile_id=_PROFILE_ID,
            custody_generation=3,
            dek_epoch="epoch-3",
            now=_NOW + timedelta(minutes=1),
            receipt_key=proof,
            login_id=RECEIPT_LOGIN_ID,
            sign_in_binding=sign_in.binding,
        )
        port.zeroise_owned_buffer(proof)
        assert isinstance(resumed, ProfileSessionResumeOutcome)
        assert resumed.resumed is True
        assert resumed.refusal is None
        assert resumed.record == minted
        assert isinstance(key_buffer, bytearray)
        assert key_buffer == _DEK
        port.zeroise_owned_buffer(key_buffer)
        assert key_buffer == bytearray(32)

        # Reading a receipt cannot extend its lifetime; the original expiry wins.
        borrowed, proof = port.borrow_acceleration_receipt_key(storage_root=tmp_path, profile_id=_PROFILE_ID)
        assert borrowed.resumed and proof is not None
        expired, expired_key = port.resume_acceleration_receipt_with_key(
            storage_root=tmp_path,
            profile_id=_PROFILE_ID,
            custody_generation=3,
            dek_epoch="epoch-3",
            now=_NOW + timedelta(minutes=16),
            receipt_key=proof,
            login_id=RECEIPT_LOGIN_ID,
            sign_in_binding=sign_in.binding,
        )
        port.zeroise_owned_buffer(proof)
        assert not expired.resumed and expired_key is None
        assert expired.refusal is ProfileSessionRefusalReason.EXPIRED_IDLE
        assert port.is_persisted_receipt(minted) is True
        assert port.is_persisted_receipt(object()) is False
    finally:
        port.delete_acceleration_receipt(storage_root=tmp_path, profile_id=_PROFILE_ID)

    assert not receipt_path.exists()


def test_receipt_path_and_absent_delete_use_the_canonical_custody_location(tmp_path: Path) -> None:
    port = build_profile_login_session_port()

    assert port.acceleration_receipt_path(
        storage_root=tmp_path,
        profile_id=_PROFILE_ID,
    ) == profile_session_path(storage_root=tmp_path, profile_id=_PROFILE_ID)
    port.delete_acceleration_receipt(storage_root=tmp_path, profile_id=_PROFILE_ID)


def test_receipt_mint_reports_none_when_the_captured_generation_moved(tmp_path: Path) -> None:
    port = build_profile_login_session_port()
    sign_in = sign_in_custody(tmp_path, _PROFILE_ID, custody_generation=3)
    captured = sign_in.establish().current
    advanced = sign_in.advance().current

    minted = port.mint_acceleration_receipt(
        storage_root=tmp_path,
        profile_id=_PROFILE_ID,
        custody_generation=3,
        dek_epoch="epoch-3",
        dek=_DEK,
        now=_NOW,
        idle_minutes=15,
        absolute_minutes=240,
        login_id=RECEIPT_LOGIN_ID,
        sign_in_binding=sign_in.binding,
        sign_in_generation=captured,
    )

    assert minted is None
    assert not port.acceleration_receipt_path(storage_root=tmp_path, profile_id=_PROFILE_ID).exists()
    assert sign_in.observe().current == advanced
