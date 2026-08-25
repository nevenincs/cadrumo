"""Exact-object contract for the concrete profile login-session adapter."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from .. import _profile_login_session as adapter_module
from .. import build_profile_login_session_port, custody, master_key

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_PROFILE_ID = UUID("11111111-1111-4111-8111-111111111111")
_SESSION_ID = UUID("22222222-2222-4222-8222-222222222222")
_NOW = datetime(2026, 8, 25, 12, tzinfo=UTC)
_DEK = bytes(range(32))


def _receipt() -> custody.PersistedProfileSession:
    return custody.wrap_profile_session_dek(
        session_key=bytes(range(32, 64)),
        dek=_DEK,
        profile_id=_PROFILE_ID,
        session_id=_SESSION_ID,
        custody_generation=3,
        dek_epoch="epoch-3",
        issued_at=_NOW,
        idle_deadline=_NOW + timedelta(minutes=15),
        absolute_deadline=_NOW + timedelta(hours=4),
    )


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

    assert isinstance(session, master_key.BucketSession)
    port.bind_session(session)
    assert port.current_session() is session
    assert port.session_serves_bucket(session, str(_PROFILE_ID)) is True

    initial = port.evaluate_throttle(storage_root=tmp_path, bucket_id=str(_PROFILE_ID), now=_NOW)
    assert isinstance(initial, master_key.ThrottleEvaluation)
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


def test_receipt_delegation_preserves_dto_and_key_buffer_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    port = build_profile_login_session_port()
    record = _receipt()
    outcome = custody.ProfileSessionResumeOutcome(resumed=True, record=record)
    resumed_dek = bytearray(_DEK)
    advanced = record.model_copy(update={"idle_deadline": _NOW + timedelta(minutes=20)})

    monkeypatch.setattr(adapter_module.custody, "mint_profile_session", lambda **_kwargs: record)
    monkeypatch.setattr(
        adapter_module.custody,
        "resume_profile_session",
        lambda **_kwargs: (outcome, resumed_dek),
    )
    monkeypatch.setattr(
        adapter_module.custody,
        "advance_persisted_profile_session_idle_deadline",
        lambda **_kwargs: advanced,
    )

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
    resumed, key_buffer = port.resume_acceleration_receipt(
        storage_root=tmp_path,
        profile_id=_PROFILE_ID,
        custody_generation=3,
        dek_epoch="epoch-3",
        now=_NOW,
    )
    renewed = port.advance_acceleration_idle_deadline(
        storage_root=tmp_path,
        profile_id=_PROFILE_ID,
        record=record,
        new_idle_deadline=_NOW + timedelta(minutes=20),
    )

    assert minted is record
    assert resumed is outcome
    assert key_buffer is resumed_dek
    assert renewed is advanced
    assert port.is_persisted_receipt(record) is True
    assert port.is_persisted_receipt(object()) is False


def test_receipt_path_and_absent_delete_use_the_canonical_custody_location(tmp_path: Path) -> None:
    port = build_profile_login_session_port()

    assert port.acceleration_receipt_path(
        storage_root=tmp_path,
        profile_id=_PROFILE_ID,
    ) == custody.profile_session_path(storage_root=tmp_path, profile_id=_PROFILE_ID)
    port.delete_acceleration_receipt(storage_root=tmp_path, profile_id=_PROFILE_ID)
