"""Existing encrypted human receipt proof across the application boundary."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.persistence.storage.custody import acceleration_receipt as receipt
from cadrumo.adapters.persistence.storage.custody.acceleration_receipt_crypto import (
    PersistedProfileSession,
    wrap_profile_session_dek,
)
from cadrumo.adapters.persistence.storage.custody.capsule import load_committed_profile_password_material
from cadrumo.adapters.persistence.storage.custody.tests.receipt_sign_in import (
    OTHER_LOGIN_ID,
    RECEIPT_LOGIN_ID,
    committed_sign_in,
    sign_in_custody,
)
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
            login_id=RECEIPT_LOGIN_ID,
            sign_in=committed_sign_in(tmp_path, profile_id),
            generation=committed_sign_in(tmp_path, profile_id).establish().current,
        )
        _, decode = profile_authority_contexts()
        with (
            bind_profile_custody_port(build_profile_custody_port()),
            bind_profile_login_session_port(build_profile_login_session_port()),
        ):
            ambient = current_active_bucket_session()
            with borrow_profile_receipt_key(bucket_id=profile_id) as key:
                assert len(key) == 32
                reads = human_keyring.reads
                with resume_profile_candidate(
                    bucket_id=profile_id,
                    receipt_key=key,
                    profile_decode_context=decode,
                    login_id=RECEIPT_LOGIN_ID,
                    sign_in_binding=committed_sign_in(tmp_path, profile_id).binding,
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
                        login_id=RECEIPT_LOGIN_ID,
                        sign_in_binding=committed_sign_in(tmp_path, profile_id).binding,
                        now=opened + timedelta(minutes=2),
                    ),
                ):
                    pass
                assert caught.value.reason is ProfileSessionRefusalReason.TAMPERED
                interrupted_keys: list[bytearray] = []
                with (
                    pytest.raises(RuntimeError),
                    borrow_profile_receipt_key(bucket_id=profile_id) as interrupted_key,
                ):
                    interrupted_keys.append(interrupted_key)
                    raise RuntimeError("protected IPC failed")
                assert interrupted_keys == [bytearray(32)]
                # A receipt from custody newer than the committed capsule; only
                # its plaintext custody generation is evaluated, so no keychain
                # half is needed.
                receipt_path = receipt.profile_session_path(storage_root=tmp_path, profile_id=profile_id)
                receipt._write_acceleration_receipt(
                    storage_root=tmp_path,
                    profile_id=profile_id,
                    record=wrap_profile_session_dek(
                        session_key=bytes(32),
                        dek=dek,
                        profile_id=profile_id,
                        session_id=uuid4(),
                        custody_generation=material.envelope.password_generation + 1,
                        dek_epoch=material.envelope.dek_epoch,
                        login_id=RECEIPT_LOGIN_ID,
                        sign_in=persisted.sign_in,
                        issued_at=opened,
                        idle_deadline=persisted.idle_deadline,
                        absolute_deadline=persisted.absolute_deadline,
                    ),
                    predecessor=receipt_path.read_bytes(),
                )
                with (
                    pytest.raises(ProfileReceiptRefusedError) as changed,
                    resume_profile_candidate(
                        bucket_id=profile_id,
                        receipt_key=key,
                        profile_decode_context=decode,
                        login_id=RECEIPT_LOGIN_ID,
                        sign_in_binding=committed_sign_in(tmp_path, profile_id).binding,
                        now=opened + timedelta(minutes=2),
                    ),
                ):
                    pass
                assert changed.value.reason is ProfileSessionRefusalReason.CUSTODY_CHANGED
            assert key == bytearray(32)
            assert current_active_bucket_session() is ambient
            # The runtime-side reader, not the borrowing frontend, deleted the
            # receipt that changed custody had revoked.
            assert not receipt.profile_session_path(storage_root=tmp_path, profile_id=profile_id).exists()
