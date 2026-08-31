"""Exact-object contract for the concrete profile login-session adapter."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from .._profile_login_session import build_profile_login_session_port
from ..custody.acceleration_receipt import ProfileSessionResumeOutcome, profile_session_path
from ..custody.acceleration_receipt_crypto import PersistedProfileSession
from ..errors import KeyringUnavailableError
from ..master_key.bucket_session import BucketSession
from ..master_key.login_throttle import ThrottleEvaluation

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
        )
    except KeyringUnavailableError:
        assert not receipt_path.exists()
        return

    try:
        assert isinstance(minted, PersistedProfileSession)
        assert minted.profile_id == _PROFILE_ID
        assert minted.custody_generation == 3
        assert minted.dek_epoch == "epoch-3"
        assert minted.issued_at == _NOW
        assert minted.idle_deadline == _NOW + timedelta(minutes=15)
        assert minted.absolute_deadline == _NOW + timedelta(hours=4)

        resumed, key_buffer = port.resume_acceleration_receipt(
            storage_root=tmp_path,
            profile_id=_PROFILE_ID,
            custody_generation=3,
            dek_epoch="epoch-3",
            now=_NOW + timedelta(minutes=1),
        )
        assert isinstance(resumed, ProfileSessionResumeOutcome)
        assert resumed.resumed is True
        assert resumed.refusal is None
        assert resumed.record == minted
        assert isinstance(key_buffer, bytearray)
        assert key_buffer == _DEK
        port.zeroise_owned_buffer(key_buffer)
        assert key_buffer == bytearray(32)

        renewed = port.advance_acceleration_idle_deadline(
            storage_root=tmp_path,
            profile_id=_PROFILE_ID,
            record=minted,
            new_idle_deadline=_NOW + timedelta(minutes=20),
        )
        assert isinstance(renewed, PersistedProfileSession)
        assert renewed.session_id == minted.session_id
        assert renewed.issued_at == minted.issued_at
        assert renewed.idle_deadline == _NOW + timedelta(minutes=20)
        assert renewed.absolute_deadline == minted.absolute_deadline

        resumed_after_renewal, renewed_key_buffer = port.resume_acceleration_receipt(
            storage_root=tmp_path,
            profile_id=_PROFILE_ID,
            custody_generation=3,
            dek_epoch="epoch-3",
            now=_NOW + timedelta(minutes=16),
        )
        assert isinstance(resumed_after_renewal, ProfileSessionResumeOutcome)
        assert resumed_after_renewal.resumed is True
        assert resumed_after_renewal.record == renewed
        assert isinstance(renewed_key_buffer, bytearray)
        assert renewed_key_buffer == _DEK
        port.zeroise_owned_buffer(renewed_key_buffer)
        assert renewed_key_buffer == bytearray(32)
        assert port.is_persisted_receipt(renewed) is True
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
