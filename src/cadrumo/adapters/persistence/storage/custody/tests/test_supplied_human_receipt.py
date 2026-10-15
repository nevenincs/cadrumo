"""Existing encrypted human receipt proof across the application boundary."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.persistence.storage.custody import acceleration_receipt as receipt
from cadrumo.adapters.persistence.storage.custody.acceleration_receipt_crypto import (
    PersistedProfileSession,
)
from cadrumo.adapters.persistence.storage.custody.tests.receipt_sign_in import (
    OTHER_LOGIN_ID,
    RECEIPT_LOGIN_ID,
    sign_in_custody,
)
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


def _mint_receipt(root: Path, profile_id: UUID, opened: datetime, dek: bytes) -> PersistedProfileSession:
    sign_in = sign_in_custody(root, profile_id, custody_generation=3)
    return receipt.mint_profile_session(
        storage_root=root,
        profile_id=profile_id,
        custody_generation=3,
        dek_epoch="epoch-3",
        dek=dek,
        now=opened,
        idle_minutes=15,
        absolute_minutes=240,
        login_id=RECEIPT_LOGIN_ID,
        sign_in=sign_in,
        generation=sign_in.establish().current,
    )


def _resume_with_key(
    root: Path,
    profile_id: UUID,
    key: bytearray,
    *,
    now: datetime,
    custody_generation: int = 3,
    login_id: str = RECEIPT_LOGIN_ID,
) -> tuple[receipt.ProfileSessionResumeOutcome, bytearray | None]:
    return receipt.resume_profile_session_with_key(
        storage_root=root,
        profile_id=profile_id,
        custody_generation=custody_generation,
        dek_epoch="epoch-3",
        now=now,
        receipt_key=key,
        login_id=login_id,
        sign_in=sign_in_custody(root, profile_id, custody_generation=3),
    )


def test_a_wrong_proof_is_non_destructive_and_uses_no_keyring_lookup(
    tmp_path: Path, human_keyring: _HumanKeyring
) -> None:
    profile_id = uuid4()
    other_id = uuid4()
    opened = datetime(2026, 9, 27, 12, tzinfo=UTC)
    dek = bytes(range(32))
    record = _mint_receipt(tmp_path, profile_id, opened, dek)
    other_record = _mint_receipt(tmp_path, other_id, opened, bytes(reversed(range(32))))
    path = receipt.profile_session_path(storage_root=tmp_path, profile_id=profile_id)
    other_path = receipt.profile_session_path(storage_root=tmp_path, profile_id=other_id)
    original = path.read_bytes()
    other_original = other_path.read_bytes()
    account = (receipt.PROFILE_SESSION_KEYCHAIN_SERVICE, f"{profile_id}:{record.session_id}")
    other_account = (receipt.PROFILE_SESSION_KEYCHAIN_SERVICE, f"{other_id}:{other_record.session_id}")
    borrowed, key = receipt.borrow_profile_session_key(storage_root=tmp_path, profile_id=profile_id)
    assert borrowed.resumed and borrowed.record is None and key is not None and len(key) == 32
    reads = human_keyring.reads
    # A proof that does not unwrap cannot tell a stale key from a corrupt
    # record, so neither the target's nor any other receipt is touched.
    for supplied, target in ((bytearray(b"x" * 32), profile_id), (key, other_id)):
        refused, no_dek = _resume_with_key(tmp_path, target, supplied, now=opened + timedelta(minutes=1))
        assert refused.refusal is ProfileSessionRefusalReason.TAMPERED and no_dek is None
        assert refused.deletion is receipt.ReceiptDeletion.NOT_REQUIRED
        assert path.read_bytes() == original and account in human_keyring.entries
        assert other_path.read_bytes() == other_original and other_account in human_keyring.entries
    accepted, recovered = _resume_with_key(tmp_path, profile_id, key, now=opened + timedelta(minutes=2))
    assert accepted.record == record and recovered == dek
    assert path.read_bytes() == original
    assert human_keyring.reads == reads
    assert recovered is not None
    receipt._zeroise(recovered)
    receipt._zeroise(key)


def test_a_wrong_proof_under_another_login_deletes_nothing_and_the_sign_in_survives(
    tmp_path: Path, human_keyring: _HumanKeyring
) -> None:
    profile_id = uuid4()
    opened = datetime(2026, 9, 27, 12, tzinfo=UTC)
    dek = bytes(range(32))
    record = _mint_receipt(tmp_path, profile_id, opened, dek)
    path = receipt.profile_session_path(storage_root=tmp_path, profile_id=profile_id)
    original = path.read_bytes()
    account = (receipt.PROFILE_SESSION_KEYCHAIN_SERVICE, f"{profile_id}:{record.session_id}")
    _, key = receipt.borrow_profile_session_key(storage_root=tmp_path, profile_id=profile_id)
    assert key is not None

    # Which login presents a proof says nothing about whether the proof is the
    # person's, so a caller that cannot unwrap the receipt cannot retire it.
    refused, no_dek = _resume_with_key(
        tmp_path,
        profile_id,
        bytearray(b"x" * 32),
        now=opened + timedelta(minutes=1),
        login_id=OTHER_LOGIN_ID,
    )

    assert refused.refusal is ProfileSessionRefusalReason.TAMPERED and no_dek is None
    assert refused.deletion is receipt.ReceiptDeletion.NOT_REQUIRED
    assert path.read_bytes() == original and account in human_keyring.entries
    accepted, recovered = _resume_with_key(tmp_path, profile_id, key, now=opened + timedelta(minutes=2))
    assert accepted.record == record and recovered == dek
    assert path.read_bytes() == original and account in human_keyring.entries
    assert recovered is not None
    receipt._zeroise(recovered)
    receipt._zeroise(key)


@pytest.mark.parametrize(
    ("case", "reason", "binding"),
    [
        ("expired_idle", ProfileSessionRefusalReason.EXPIRED_IDLE, None),
        ("custody_changed", ProfileSessionRefusalReason.CUSTODY_CHANGED, None),
        ("login_mismatch", ProfileSessionRefusalReason.ABSENT, receipt.ReceiptBindingRefusal.LOGIN_MISMATCH),
        ("generation_changed", ProfileSessionRefusalReason.ABSENT, receipt.ReceiptBindingRefusal.GENERATION_CHANGED),
        ("generation_missing", ProfileSessionRefusalReason.ABSENT, receipt.ReceiptBindingRefusal.GENERATION_MISSING),
    ],
)
def test_the_runtime_reader_deletes_a_receipt_its_own_bytes_refuse(
    tmp_path: Path,
    human_keyring: _HumanKeyring,
    case: str,
    reason: ProfileSessionRefusalReason,
    binding: receipt.ReceiptBindingRefusal | None,
) -> None:
    profile_id = uuid4()
    opened = datetime(2026, 9, 27, 12, tzinfo=UTC)
    record = _mint_receipt(tmp_path, profile_id, opened, bytes(range(32)))
    path = receipt.profile_session_path(storage_root=tmp_path, profile_id=profile_id)
    account = (receipt.PROFILE_SESSION_KEYCHAIN_SERVICE, f"{profile_id}:{record.session_id}")
    _, key = receipt.borrow_profile_session_key(storage_root=tmp_path, profile_id=profile_id)
    assert key is not None
    instant = opened + timedelta(minutes=15 if case == "expired_idle" else 1)
    if case == "generation_changed":
        sign_in_custody(tmp_path, profile_id).advance()
    if case == "generation_missing":
        sign_in_custody(tmp_path, profile_id).path.unlink()

    refused, dek = _resume_with_key(
        tmp_path,
        profile_id,
        key,
        now=instant,
        custody_generation=4 if case == "custody_changed" else 3,
        login_id=OTHER_LOGIN_ID if case == "login_mismatch" else RECEIPT_LOGIN_ID,
    )

    assert dek is None
    assert refused.refusal is reason and refused.binding is binding
    assert refused.deletion is receipt.ReceiptDeletion.DELETED
    assert not path.exists() and account not in human_keyring.entries
    receipt._zeroise(key)
