"""Runtime receipt admission over real encrypted custody and inherited deadlines."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo.adapters.persistence.storage.custody import acceleration_receipt as receipt
from cadrumo.adapters.persistence.storage.custody.capsule import (
    load_committed_profile_password_material,
    replace_committed_profile_custody_envelope,
)
from cadrumo.adapters.persistence.storage.custody.records import ProfileCustodyEnvelope
from cadrumo.adapters.persistence.storage.custody.tests.receipt_sign_in import (
    RECEIPT_LOGIN_ID,
    committed_sign_in,
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
    ProfileLoginCandidate,
    ProfileReceiptRefusedError,
    borrow_profile_receipt_key,
)
from cadrumo.application.user_profile.login_session_port import bind_profile_login_session_port
from cadrumo.application.user_profile.profile_pointer import active_profile_pointer_transaction
from cadrumo.core.config import override_settings
from cadrumo.core.profile_session import ProfileSessionRefusalReason, ReceiptBindingRefusal

from ..profile_receipt import resume_profile_candidate

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


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


def test_receipt_admission_preserves_ambient_session_and_deadlines(
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
                    original_bytes = receipt.profile_session_path(
                        storage_root=tmp_path, profile_id=profile_id
                    ).read_bytes()
                    generation = committed_sign_in(tmp_path, profile_id).observe().current
                    assert generation is not None
                    assert not candidate.mints_receipt
                    assert candidate.persist_acceleration_receipt(
                        login_id=RECEIPT_LOGIN_ID,
                        binding=committed_sign_in(tmp_path, profile_id).binding,
                        sign_in=generation,
                    )
                    assert (
                        receipt.profile_session_path(storage_root=tmp_path, profile_id=profile_id).read_bytes()
                        == original_bytes
                    )
                    assert candidate.session.dek == dek
                    assert current_active_bucket_session() is ambient
                    assert human_keyring.reads == reads
                assert candidate.session.sealed
                interrupted_candidates: list[ProfileLoginCandidate] = []
                with (
                    pytest.raises(RuntimeError, match="admission interrupted"),
                    resume_profile_candidate(
                        bucket_id=profile_id,
                        receipt_key=key,
                        profile_decode_context=decode,
                        login_id=RECEIPT_LOGIN_ID,
                        sign_in_binding=committed_sign_in(tmp_path, profile_id).binding,
                        now=opened + timedelta(minutes=2),
                    ) as interrupted,
                ):
                    interrupted_candidates.append(interrupted)
                    raise RuntimeError("admission interrupted")
                assert len(interrupted_candidates) == 1
                assert interrupted_candidates[0].session.sealed
                assert current_active_bucket_session() is ambient
                assert (
                    receipt.profile_session_path(storage_root=tmp_path, profile_id=profile_id).read_bytes()
                    == original_bytes
                )
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
            assert key == bytearray(32)
            assert current_active_bucket_session() is ambient


@pytest.mark.parametrize(
    ("case", "reason"),
    [
        ("expired_idle", ProfileSessionRefusalReason.EXPIRED_IDLE),
        ("expired_absolute", ProfileSessionRefusalReason.EXPIRED_ABSOLUTE),
        ("login_mismatch", ProfileSessionRefusalReason.ABSENT),
        ("generation_changed", ProfileSessionRefusalReason.ABSENT),
        ("custody_changed", ProfileSessionRefusalReason.CUSTODY_CHANGED),
        ("wrong_dek", ProfileSessionRefusalReason.TAMPERED),
    ],
)
def test_receipt_admission_refuses_without_binding_custody(
    tmp_path: Path,
    human_keyring: _HumanKeyring,
    case: str,
    reason: ProfileSessionRefusalReason,
) -> None:
    profile_id = uuid4()
    opened = datetime.now(UTC)
    with override_settings(cadrumo_local_storage_root=tmp_path):
        publish_test_profile_capsule(profile_id, label="Refused receipt", root=tmp_path)
        material = load_committed_profile_password_material(profile_id, root=tmp_path)
        sign_in = committed_sign_in(tmp_path, profile_id)
        receipt.mint_profile_session(
            storage_root=tmp_path,
            profile_id=profile_id,
            custody_generation=material.envelope.password_generation,
            dek_epoch=material.envelope.dek_epoch,
            dek=bytes(32) if case == "wrong_dek" else derive_test_bucket_key(str(profile_id), purpose="dek"),
            now=opened,
            idle_minutes=300 if case == "expired_absolute" else 15,
            absolute_minutes=240,
            login_id=RECEIPT_LOGIN_ID,
            sign_in=sign_in,
            generation=sign_in.establish().current,
        )
        _, decode = profile_authority_contexts()
        with (
            bind_profile_custody_port(build_profile_custody_port()),
            bind_profile_login_session_port(build_profile_login_session_port()),
            borrow_profile_receipt_key(bucket_id=profile_id) as key,
        ):
            ambient = current_active_bucket_session()
            reads = human_keyring.reads
            if case == "generation_changed":
                sign_in.advance()
            if case == "custody_changed":
                original = material.envelope
                successor = ProfileCustodyEnvelope.create(
                    profile_id=profile_id,
                    password_generation=original.password_generation + 1,
                    dek_epoch=original.dek_epoch,
                    kdf=original.kdf,
                    wrapped_dek=original.wrapped_dek,
                    previous_envelope_digest=original.self_digest,
                )
                with active_profile_pointer_transaction(tmp_path):
                    replace_committed_profile_custody_envelope(
                        profile_id,
                        successor.canonical_json_bytes(),
                        expected_sha256="sha256:" + sha256(original.canonical_json_bytes()).hexdigest(),
                        root=tmp_path,
                    )
            offset = 240 if case == "expired_absolute" else 15 if case == "expired_idle" else 1
            with (
                pytest.raises(ProfileReceiptRefusedError) as caught,
                resume_profile_candidate(
                    bucket_id=profile_id,
                    receipt_key=key,
                    profile_decode_context=decode,
                    login_id="another-os-login" if case == "login_mismatch" else RECEIPT_LOGIN_ID,
                    sign_in_binding=sign_in.binding,
                    now=opened + timedelta(minutes=offset),
                ),
            ):
                pytest.fail("refused proof yielded a candidate")
            assert caught.value.reason is reason
            assert current_active_bucket_session() is ambient
            if case == "wrong_dek":
                assert human_keyring.reads == reads
            else:
                # Revocation reads the exact stored account to verify deletion;
                # it does not use that key to admit the presenting connection.
                assert human_keyring.entries == {}
                assert not receipt.profile_session_path(storage_root=tmp_path, profile_id=profile_id).exists()
            if case == "login_mismatch":
                assert caught.value.binding is ReceiptBindingRefusal.LOGIN_MISMATCH
            if case == "generation_changed":
                assert caught.value.binding is ReceiptBindingRefusal.GENERATION_CHANGED
        assert key == bytearray(32)
