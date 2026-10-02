"""Existing encrypted human receipt proof across the application boundary."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo.adapters.persistence.storage.custody import acceleration_receipt as receipt
from cadrumo.adapters.persistence.storage.custody.capsule import load_committed_profile_password_material
from cadrumo.adapters.persistence.storage.master_key.active_session import current_active_bucket_session
from cadrumo.adapters.persistence.storage.profile_custody import build_profile_custody_port
from cadrumo.adapters.persistence.storage.profile_login_session import build_profile_login_session_port
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    derive_test_bucket_key,
    profile_authority_contexts,
    publish_test_profile_capsule,
)
from cadrumo.application.user_profile.custody_ports import bind_profile_custody_port
from cadrumo.application.user_profile.login_session import (
    ProfileReceiptRefusedError,
    borrow_profile_receipt_key,
    resume_profile_candidate,
)
from cadrumo.application.user_profile.login_session_port import bind_profile_login_session_port
from cadrumo.core.config import override_settings
from cadrumo.core.profile_session import ProfileSessionRefusalReason

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


class _KeyringError(Exception):
    """Controlled existing human keyring failure."""


class _HumanKeyring:
    """Exact service/account in-memory keyring for the real receipt writer."""

    def __init__(self) -> None:
        self.entries: dict[tuple[str, str], str] = {}
        self.reads = 0

    def get_password(self, service_name: str, username: str) -> str | None:
        """Read one exact human account."""
        self.reads += 1
        return self.entries.get((service_name, username))

    def set_password(self, service_name: str, username: str, password: str) -> None:
        """Store one exact human account."""
        self.entries[(service_name, username)] = password

    def delete_password(self, service_name: str, username: str) -> None:
        """Remove one exact human account."""
        self.entries.pop((service_name, username), None)


@pytest.fixture
def human_keyring(monkeypatch: pytest.MonkeyPatch) -> _HumanKeyring:
    """Compose the real receipt crypto/filesystem with a controlled store."""
    keyring = _HumanKeyring()
    monkeypatch.setattr(receipt, "_keyring", lambda: (keyring, _KeyringError, _KeyringError))
    return keyring


def test_supplied_proof_is_non_destructive_and_uses_no_keyring_lookup(
    tmp_path: Path, human_keyring: _HumanKeyring
) -> None:
    profile_id = uuid4()
    other_id = uuid4()
    opened = datetime(2026, 9, 27, 12, tzinfo=UTC)
    dek = bytes(range(32))
    record = receipt.mint_profile_session(
        storage_root=tmp_path,
        profile_id=profile_id,
        custody_generation=3,
        dek_epoch="epoch-3",
        dek=dek,
        now=opened,
        idle_minutes=15,
        absolute_minutes=240,
    )
    other_record = receipt.mint_profile_session(
        storage_root=tmp_path,
        profile_id=other_id,
        custody_generation=3,
        dek_epoch="epoch-3",
        dek=bytes(reversed(range(32))),
        now=opened,
        idle_minutes=15,
        absolute_minutes=240,
    )
    path = receipt.profile_session_path(storage_root=tmp_path, profile_id=profile_id)
    other_path = receipt.profile_session_path(storage_root=tmp_path, profile_id=other_id)
    original = path.read_bytes()
    other_original = other_path.read_bytes()
    account = (receipt.PROFILE_SESSION_KEYCHAIN_SERVICE, f"{profile_id}:{record.session_id}")
    other_account = (receipt.PROFILE_SESSION_KEYCHAIN_SERVICE, f"{other_id}:{other_record.session_id}")
    assert account in human_keyring.entries
    borrowed, key = receipt.borrow_profile_session_key(
        storage_root=tmp_path,
        profile_id=profile_id,
        custody_generation=3,
        dek_epoch="epoch-3",
        now=opened + timedelta(minutes=1),
    )
    assert borrowed.resumed and key is not None and len(key) == 32
    reads = human_keyring.reads
    for supplied, target, generation, instant, reason in (
        (bytearray(b"x" * 32), profile_id, 3, opened + timedelta(minutes=1), ProfileSessionRefusalReason.TAMPERED),
        (key, profile_id, 4, opened + timedelta(minutes=1), ProfileSessionRefusalReason.CUSTODY_CHANGED),
        (key, profile_id, 3, opened + timedelta(minutes=15), ProfileSessionRefusalReason.EXPIRED_IDLE),
        (key, other_id, 3, opened + timedelta(minutes=1), ProfileSessionRefusalReason.TAMPERED),
    ):
        refused, no_dek = receipt.resume_profile_session_with_key(
            storage_root=tmp_path,
            profile_id=target,
            custody_generation=generation,
            dek_epoch="epoch-3",
            now=instant,
            receipt_key=supplied,
        )
        assert refused.refusal is reason and no_dek is None
        assert path.read_bytes() == original and account in human_keyring.entries
        assert other_path.read_bytes() == other_original and other_account in human_keyring.entries
    accepted, recovered = receipt.resume_profile_session_with_key(
        storage_root=tmp_path,
        profile_id=profile_id,
        custody_generation=3,
        dek_epoch="epoch-3",
        now=opened + timedelta(minutes=2),
        receipt_key=key,
    )
    assert accepted.record == record and recovered == dek
    assert path.read_bytes() == original
    assert human_keyring.reads == reads
    assert recovered is not None
    receipt._zeroise(recovered)
    receipt._zeroise(key)


def test_application_borrow_and_candidate_preserve_ambient_session_and_deadlines(
    tmp_path: Path, human_keyring: _HumanKeyring
) -> None:
    profile_id = uuid4()
    opened = datetime.now(UTC)
    with override_settings(cadrumo_local_storage_root=tmp_path):
        publish_test_profile_capsule(profile_id, label="Human", root=tmp_path)
        material = load_committed_profile_password_material(profile_id, root=tmp_path)
        dek = derive_test_bucket_key(str(profile_id), purpose="dek")
        persisted = receipt.mint_profile_session(
            storage_root=tmp_path,
            profile_id=profile_id,
            custody_generation=material.envelope.password_generation,
            dek_epoch=material.envelope.dek_epoch,
            dek=dek,
            now=opened,
            idle_minutes=15,
            absolute_minutes=240,
        )
        _, decode = profile_authority_contexts()
        with (
            bind_profile_custody_port(build_profile_custody_port()),
            bind_profile_login_session_port(build_profile_login_session_port()),
        ):
            ambient = current_active_bucket_session()
            with borrow_profile_receipt_key(bucket_id=profile_id, now=opened + timedelta(minutes=1)) as key:
                assert len(key) == 32
                reads = human_keyring.reads
                with resume_profile_candidate(
                    bucket_id=profile_id,
                    receipt_key=key,
                    profile_decode_context=decode,
                    now=opened + timedelta(minutes=2),
                ) as candidate:
                    assert candidate.outcome.session_persisted
                    assert candidate.outcome.authenticated_at == opened
                    assert candidate.outcome.idle_deadline == persisted.idle_deadline
                    assert candidate.outcome.absolute_deadline == persisted.absolute_deadline
                    assert candidate.session.dek == dek
                    assert current_active_bucket_session() is ambient
                    assert human_keyring.reads == reads
                assert candidate.session.sealed
                wrong = bytearray(b"w" * 32)
                with (
                    pytest.raises(ProfileReceiptRefusedError) as caught,
                    resume_profile_candidate(
                        bucket_id=profile_id,
                        receipt_key=wrong,
                        profile_decode_context=decode,
                        now=opened + timedelta(minutes=2),
                    ),
                ):
                    pass
                assert caught.value.reason is ProfileSessionRefusalReason.TAMPERED
                interrupted_keys: list[bytearray] = []
                with (
                    pytest.raises(RuntimeError),
                    borrow_profile_receipt_key(
                        bucket_id=profile_id, now=opened + timedelta(minutes=2)
                    ) as interrupted_key,
                ):
                    interrupted_keys.append(interrupted_key)
                    raise RuntimeError("protected IPC failed")
                assert interrupted_keys == [bytearray(32)]
                receipt.mint_profile_session(
                    storage_root=tmp_path,
                    profile_id=profile_id,
                    custody_generation=material.envelope.password_generation + 1,
                    dek_epoch=material.envelope.dek_epoch,
                    dek=dek,
                    now=opened,
                    idle_minutes=15,
                    absolute_minutes=240,
                )
                with (
                    pytest.raises(ProfileReceiptRefusedError) as changed,
                    resume_profile_candidate(
                        bucket_id=profile_id,
                        receipt_key=key,
                        profile_decode_context=decode,
                        now=opened + timedelta(minutes=2),
                    ),
                ):
                    pass
                assert changed.value.reason is ProfileSessionRefusalReason.CUSTODY_CHANGED
            assert key == bytearray(32)
            assert current_active_bucket_session() is ambient
            assert receipt.profile_session_path(storage_root=tmp_path, profile_id=profile_id).exists()
            assert human_keyring.entries
