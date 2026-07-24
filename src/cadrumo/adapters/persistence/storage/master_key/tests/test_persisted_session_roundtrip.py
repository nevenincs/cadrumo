"""Persisted profile-session roundtrip, refusal, and anti-tautology proofs.

Real adapters throughout: the platform OS keychain (no mocks), real files
under a per-test storage root, and the real AES-256-GCM wrap. The suite
covers the AAD single-field-mutation matrix, the keychain custody
lifecycle, every fail-closed resume refusal branch, the strict
save-to-load equality roundtrip, and the anti-tautology proofs (corrupt
an on-disk deadline, orphan the keychain entry, bump the schema version).
"""

from __future__ import annotations

import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ......core import ProfileSessionRefusalReason
from ......core.config import SecretStoreBackend
from ......core.errors import CoreValidationError
from ...errors import (
    DecryptionError,
    EncryptionError,
    StorageValidationError,
)
from .. import (
    PROFILE_SESSION_SCHEMA_VERSION,
    PersistedProfileSession,
    advance_profile_session_idle_deadline,
    delete_profile_session,
    delete_profile_session_key,
    load_profile_session_key,
    mint_profile_session,
    profile_session_path,
    resume_profile_session,
    store_profile_session_key,
    unwrap_profile_session_dek,
    wrap_profile_session_dek,
    write_profile_session,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_NOW = datetime(2026, 7, 24, 12, 0, 0, tzinfo=UTC)
_IDLE_MINUTES = 15
_ABSOLUTE_MINUTES = 240


def _fresh_bucket_id() -> str:
    """Return a collision-free synthetic bucket id for keychain isolation."""
    return f"test-profile-session-{uuid.uuid4()}"


def _wrap(
    *,
    session_key: bytes,
    dek: bytes,
    bucket_id: str,
) -> PersistedProfileSession:
    return wrap_profile_session_dek(
        session_key=session_key,
        dek=dek,
        bucket_id=bucket_id,
        backend_kind=SecretStoreBackend.FILE,
        authenticated_at=_NOW,
        idle_deadline=_NOW + timedelta(minutes=_IDLE_MINUTES),
        absolute_deadline=_NOW + timedelta(minutes=_ABSOLUTE_MINUTES),
    )


class TestSessionWrapAadMatrix:
    """Every metadata field is AAD-bound: any single mutation fails the tag."""

    def test_roundtrip_recovers_dek(self) -> None:
        session_key = secrets.token_bytes(32)
        dek = secrets.token_bytes(32)
        record = _wrap(session_key=session_key, dek=dek, bucket_id="bucket-a")
        assert unwrap_profile_session_dek(session_key=session_key, record=record) == dek

    @pytest.mark.parametrize(
        "mutation",
        [
            {"schema_version": PROFILE_SESSION_SCHEMA_VERSION + 1},
            {"bucket_id": "bucket-b"},
            {"backend_kind": SecretStoreBackend.KEYRING},
            {"authenticated_at": _NOW - timedelta(minutes=1)},
            {"idle_deadline": _NOW + timedelta(minutes=_IDLE_MINUTES + 60)},
            {"absolute_deadline": _NOW + timedelta(minutes=_ABSOLUTE_MINUTES + 60)},
        ],
        ids=[
            "schema_version",
            "bucket_id",
            "backend_kind",
            "authenticated_at",
            "idle_deadline",
            "absolute_deadline",
        ],
    )
    def test_single_metadata_field_mutation_fails_tag(self, mutation: dict[str, object]) -> None:
        session_key = secrets.token_bytes(32)
        record = _wrap(session_key=session_key, dek=secrets.token_bytes(32), bucket_id="bucket-a")
        tampered = record.model_copy(update=mutation)
        with pytest.raises(DecryptionError):
            unwrap_profile_session_dek(session_key=session_key, record=tampered)

    def test_ciphertext_and_tag_mutation_fail(self) -> None:
        session_key = secrets.token_bytes(32)
        record = _wrap(session_key=session_key, dek=secrets.token_bytes(32), bucket_id="bucket-a")
        flipped_cipher = bytes([record.ciphertext[0] ^ 0x01]) + record.ciphertext[1:]
        with pytest.raises(DecryptionError):
            unwrap_profile_session_dek(
                session_key=session_key,
                record=record.model_copy(update={"ciphertext": flipped_cipher}),
            )
        flipped_tag = bytes([record.tag[0] ^ 0x01]) + record.tag[1:]
        with pytest.raises(DecryptionError):
            unwrap_profile_session_dek(
                session_key=session_key,
                record=record.model_copy(update={"tag": flipped_tag}),
            )

    def test_wrong_key_lengths_refused(self) -> None:
        with pytest.raises(EncryptionError):
            _wrap(session_key=b"short", dek=secrets.token_bytes(32), bucket_id="bucket-a")
        with pytest.raises(EncryptionError):
            _wrap(session_key=secrets.token_bytes(32), dek=b"short", bucket_id="bucket-a")

    def test_idle_past_absolute_refused(self) -> None:
        with pytest.raises(EncryptionError):
            wrap_profile_session_dek(
                session_key=secrets.token_bytes(32),
                dek=secrets.token_bytes(32),
                bucket_id="bucket-a",
                backend_kind=SecretStoreBackend.FILE,
                authenticated_at=_NOW,
                idle_deadline=_NOW + timedelta(minutes=300),
                absolute_deadline=_NOW + timedelta(minutes=240),
            )

    def test_naive_datetime_refused(self) -> None:
        with pytest.raises(CoreValidationError):
            wrap_profile_session_dek(
                session_key=secrets.token_bytes(32),
                dek=secrets.token_bytes(32),
                bucket_id="bucket-a",
                backend_kind=SecretStoreBackend.FILE,
                authenticated_at=datetime(2026, 7, 24, 12, 0, 0),
                idle_deadline=_NOW + timedelta(minutes=15),
                absolute_deadline=_NOW + timedelta(minutes=240),
            )

    def test_advance_idle_deadline_rewraps_and_clamps(self) -> None:
        session_key = secrets.token_bytes(32)
        dek = secrets.token_bytes(32)
        record = _wrap(session_key=session_key, dek=dek, bucket_id="bucket-a")
        past_cap = record.absolute_deadline + timedelta(minutes=30)
        advanced = advance_profile_session_idle_deadline(
            record=record,
            session_key=session_key,
            new_idle_deadline=past_cap,
        )
        assert advanced.idle_deadline == record.absolute_deadline
        assert advanced.nonce != record.nonce
        assert unwrap_profile_session_dek(session_key=session_key, record=advanced) == dek


class TestKeychainCustody:
    """Real platform-keychain set, get, delete, and absent-entry behavior."""

    def test_store_load_delete_roundtrip(self) -> None:
        bucket_id = _fresh_bucket_id()
        session_key = secrets.token_bytes(32)
        try:
            store_profile_session_key(bucket_id=bucket_id, session_key=session_key)
            assert load_profile_session_key(bucket_id=bucket_id) == session_key
        finally:
            delete_profile_session_key(bucket_id=bucket_id)
        assert load_profile_session_key(bucket_id=bucket_id) is None

    def test_absent_entry_loads_none(self) -> None:
        assert load_profile_session_key(bucket_id=_fresh_bucket_id()) is None

    def test_delete_is_idempotent(self) -> None:
        bucket_id = _fresh_bucket_id()
        delete_profile_session_key(bucket_id=bucket_id)
        delete_profile_session_key(bucket_id=bucket_id)

    def test_malformed_entry_treated_absent_and_deleted(self) -> None:
        import keyring

        from .._persisted_session import PROFILE_SESSION_KEYCHAIN_SERVICE

        bucket_id = _fresh_bucket_id()
        keyring.set_password(PROFILE_SESSION_KEYCHAIN_SERVICE, bucket_id, "not-base64!!")
        try:
            assert load_profile_session_key(bucket_id=bucket_id) is None
            assert keyring.get_password(PROFILE_SESSION_KEYCHAIN_SERVICE, bucket_id) is None
        finally:
            delete_profile_session_key(bucket_id=bucket_id)

    def test_empty_bucket_id_refused(self) -> None:
        with pytest.raises(StorageValidationError):
            store_profile_session_key(bucket_id="", session_key=secrets.token_bytes(32))
        with pytest.raises(StorageValidationError):
            load_profile_session_key(bucket_id="")


class TestMintResumeRoundtrip:
    """Strict save-to-load equality plus the no-plaintext-on-disk invariant."""

    def test_mint_then_resume_returns_equal_record_and_dek(self, tmp_path: Path) -> None:
        bucket_id = _fresh_bucket_id()
        dek = secrets.token_bytes(32)
        try:
            minted = mint_profile_session(
                storage_root=tmp_path,
                bucket_id=bucket_id,
                backend_kind=SecretStoreBackend.KEYRING,
                dek=dek,
                now=_NOW,
                idle_minutes=_IDLE_MINUTES,
                absolute_minutes=_ABSOLUTE_MINUTES,
            )
            outcome, resumed_dek = resume_profile_session(
                storage_root=tmp_path,
                bucket_id=bucket_id,
                now=_NOW + timedelta(minutes=5),
            )
            assert outcome.resumed is True
            assert outcome.refusal is None
            assert outcome.record == minted
            assert resumed_dek == dek
        finally:
            delete_profile_session(storage_root=tmp_path, bucket_id=bucket_id)

    def test_no_plaintext_key_bytes_on_disk(self, tmp_path: Path) -> None:
        import base64

        bucket_id = _fresh_bucket_id()
        dek = secrets.token_bytes(32)
        try:
            mint_profile_session(
                storage_root=tmp_path,
                bucket_id=bucket_id,
                backend_kind=SecretStoreBackend.FILE,
                dek=dek,
                now=_NOW,
                idle_minutes=_IDLE_MINUTES,
                absolute_minutes=_ABSOLUTE_MINUTES,
            )
            on_disk = [p for p in tmp_path.rglob("*") if p.is_file()]
            assert on_disk, "mint must persist the session record"
            dek_b64 = base64.b64encode(dek)
            for path in on_disk:
                payload = path.read_bytes()
                assert dek not in payload, f"plaintext DEK bytes found in {path}"
                assert dek_b64 not in payload, f"base64 DEK found in {path}"
        finally:
            delete_profile_session(storage_root=tmp_path, bucket_id=bucket_id)

    def test_mint_refuses_nonpositive_windows(self, tmp_path: Path) -> None:
        for idle, absolute in ((0, _ABSOLUTE_MINUTES), (_IDLE_MINUTES, 0)):
            with pytest.raises(StorageValidationError):
                mint_profile_session(
                    storage_root=tmp_path,
                    bucket_id=_fresh_bucket_id(),
                    backend_kind=SecretStoreBackend.FILE,
                    dek=secrets.token_bytes(32),
                    now=_NOW,
                    idle_minutes=idle,
                    absolute_minutes=absolute,
                )

    def test_write_refuses_bucket_mismatch(self, tmp_path: Path) -> None:
        record = _wrap(
            session_key=secrets.token_bytes(32),
            dek=secrets.token_bytes(32),
            bucket_id="bucket-a",
        )
        with pytest.raises(StorageValidationError):
            write_profile_session(storage_root=tmp_path, bucket_id="bucket-b", record=record)


class TestResumeRefusalBranches:
    """Every fail-closed refusal branch deletes stale artefacts and refuses."""

    def _mint(self, tmp_path: Path, bucket_id: str) -> bytes:
        dek = secrets.token_bytes(32)
        mint_profile_session(
            storage_root=tmp_path,
            bucket_id=bucket_id,
            backend_kind=SecretStoreBackend.FILE,
            dek=dek,
            now=_NOW,
            idle_minutes=_IDLE_MINUTES,
            absolute_minutes=_ABSOLUTE_MINUTES,
        )
        return dek

    def test_absent_record_is_logged_out(self, tmp_path: Path) -> None:
        outcome, dek = resume_profile_session(
            storage_root=tmp_path,
            bucket_id=_fresh_bucket_id(),
            now=_NOW,
        )
        assert outcome.resumed is False
        assert outcome.refusal is ProfileSessionRefusalReason.ABSENT
        assert dek is None

    def test_garbage_record_refused_malformed_and_deleted(self, tmp_path: Path) -> None:
        bucket_id = _fresh_bucket_id()
        path = profile_session_path(storage_root=tmp_path, bucket_id=bucket_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"not json at all")
        outcome, dek = resume_profile_session(storage_root=tmp_path, bucket_id=bucket_id, now=_NOW)
        assert outcome.refusal is ProfileSessionRefusalReason.MALFORMED
        assert dek is None
        assert not path.is_file()

    def test_idle_expiry_refused_and_deleted(self, tmp_path: Path) -> None:
        bucket_id = _fresh_bucket_id()
        try:
            self._mint(tmp_path, bucket_id)
            outcome, dek = resume_profile_session(
                storage_root=tmp_path,
                bucket_id=bucket_id,
                now=_NOW + timedelta(minutes=_IDLE_MINUTES, seconds=1),
            )
            assert outcome.refusal is ProfileSessionRefusalReason.EXPIRED_IDLE
            assert dek is None
            assert not profile_session_path(storage_root=tmp_path, bucket_id=bucket_id).is_file()
            assert load_profile_session_key(bucket_id=bucket_id) is None
        finally:
            delete_profile_session(storage_root=tmp_path, bucket_id=bucket_id)

    def test_absolute_expiry_refused_and_deleted(self, tmp_path: Path) -> None:
        bucket_id = _fresh_bucket_id()
        try:
            self._mint(tmp_path, bucket_id)
            outcome, dek = resume_profile_session(
                storage_root=tmp_path,
                bucket_id=bucket_id,
                now=_NOW + timedelta(minutes=_ABSOLUTE_MINUTES, seconds=1),
            )
            assert outcome.refusal is ProfileSessionRefusalReason.EXPIRED_ABSOLUTE
            assert dek is None
            assert not profile_session_path(storage_root=tmp_path, bucket_id=bucket_id).is_file()
        finally:
            delete_profile_session(storage_root=tmp_path, bucket_id=bucket_id)

    def test_orphaned_keychain_entry_treated_logged_out(self, tmp_path: Path) -> None:
        bucket_id = _fresh_bucket_id()
        try:
            self._mint(tmp_path, bucket_id)
            delete_profile_session_key(bucket_id=bucket_id)
            outcome, dek = resume_profile_session(
                storage_root=tmp_path,
                bucket_id=bucket_id,
                now=_NOW + timedelta(minutes=1),
            )
            assert outcome.refusal is ProfileSessionRefusalReason.KEYCHAIN_ENTRY_MISSING
            assert dek is None
            assert not profile_session_path(storage_root=tmp_path, bucket_id=bucket_id).is_file()
        finally:
            delete_profile_session(storage_root=tmp_path, bucket_id=bucket_id)

    def test_on_disk_deadline_extension_refused_tampered(self, tmp_path: Path) -> None:
        """Anti-tautology: editing the persisted idle deadline breaks the tag."""
        bucket_id = _fresh_bucket_id()
        try:
            self._mint(tmp_path, bucket_id)
            path = profile_session_path(storage_root=tmp_path, bucket_id=bucket_id)
            document = json.loads(path.read_text(encoding="utf-8"))
            extended = _NOW + timedelta(minutes=_IDLE_MINUTES + 120)
            document["idle_deadline"] = extended.isoformat()
            path.write_text(json.dumps(document), encoding="utf-8")
            outcome, dek = resume_profile_session(
                storage_root=tmp_path,
                bucket_id=bucket_id,
                now=_NOW + timedelta(minutes=_IDLE_MINUTES + 60),
            )
            assert outcome.refusal is ProfileSessionRefusalReason.TAMPERED
            assert dek is None
            assert not path.is_file()
            assert load_profile_session_key(bucket_id=bucket_id) is None
        finally:
            delete_profile_session(storage_root=tmp_path, bucket_id=bucket_id)

    def test_schema_version_bump_refused_and_deleted(self, tmp_path: Path) -> None:
        """Anti-tautology: a non-current schema version forces re-login."""
        bucket_id = _fresh_bucket_id()
        try:
            self._mint(tmp_path, bucket_id)
            path = profile_session_path(storage_root=tmp_path, bucket_id=bucket_id)
            document = json.loads(path.read_text(encoding="utf-8"))
            document["schema_version"] = PROFILE_SESSION_SCHEMA_VERSION + 1
            path.write_text(json.dumps(document), encoding="utf-8")
            outcome, dek = resume_profile_session(
                storage_root=tmp_path,
                bucket_id=bucket_id,
                now=_NOW + timedelta(minutes=1),
            )
            assert outcome.refusal is ProfileSessionRefusalReason.SCHEMA_VERSION_MISMATCH
            assert dek is None
            assert not path.is_file()
            assert load_profile_session_key(bucket_id=bucket_id) is None
        finally:
            delete_profile_session(storage_root=tmp_path, bucket_id=bucket_id)

    def test_record_naming_another_bucket_refused_tampered(self, tmp_path: Path) -> None:
        bucket_a = _fresh_bucket_id()
        bucket_b = _fresh_bucket_id()
        try:
            self._mint(tmp_path, bucket_a)
            source = profile_session_path(storage_root=tmp_path, bucket_id=bucket_a)
            target = profile_session_path(storage_root=tmp_path, bucket_id=bucket_b)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
            outcome, dek = resume_profile_session(
                storage_root=tmp_path,
                bucket_id=bucket_b,
                now=_NOW + timedelta(minutes=1),
            )
            assert outcome.refusal is ProfileSessionRefusalReason.TAMPERED
            assert dek is None
            assert not target.is_file()
        finally:
            delete_profile_session(storage_root=tmp_path, bucket_id=bucket_a)
            delete_profile_session(storage_root=tmp_path, bucket_id=bucket_b)
