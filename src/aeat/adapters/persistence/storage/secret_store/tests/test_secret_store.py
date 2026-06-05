"""Unit tests for :class:`aeat.adapters.persistence.storage.secret_store.SecretStore`.

Exercises the put/get/delete/rotate API, the index encryption
invariants, the retention-policy gate, and the blob-cleanup behaviour
of overwrites.
"""

from __future__ import annotations

import json
import logging
import secrets
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ......core.classification import SensitivityClass
from ...blob_store import EncryptedBlobStore
from ...crypto import KEY_SIZE
from ...errors import (
    BlobNotFoundError,
    RetentionPolicyError,
    SecretAlreadyExistsError,
    SecretNotFoundError,
    StorageValidationError,
)
from ...master_key import EphemeralMasterKeyProvider
from .._secret_store import SecretRecord, SecretStore

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]
_STORE_LOGGER_NAME = "aeat.adapters.persistence.storage.secret_store._secret_store"


def _expiry() -> datetime:
    return datetime.now(UTC) + timedelta(hours=1)


@pytest.fixture
def fixed_master_key() -> bytes:
    return secrets.token_bytes(KEY_SIZE)


@pytest.fixture
def store(tmp_path: Path, fixed_master_key: bytes) -> Iterator[SecretStore]:
    provider = EphemeralMasterKeyProvider(key=fixed_master_key)
    blob_store = EncryptedBlobStore(
        root_dir=tmp_path / "blobs",
        master_key_provider=provider,
    )
    yield SecretStore(
        store_dir=tmp_path / "secrets",
        blob_store=blob_store,
        master_key_provider=provider,
    )


def _make_record(
    *,
    key: str = "aeat:test:default",
    value: bytes = b"payload",
    classification: SensitivityClass = SensitivityClass.SECRET,
    expires_at: datetime | None = None,
) -> SecretRecord:
    return SecretRecord(
        key=key,
        value=value,
        classification=classification,
        metadata={"issued_by": "test-suite"},
        created_at=datetime.now(UTC),
        expires_at=expires_at if expires_at is not None else _expiry(),
    )


class TestPutAndGet:
    def test_round_trip(self, store: SecretStore) -> None:
        record = _make_record(value=b"sensitive-payload")
        store.put(record)
        loaded = store.get(record.key)
        assert loaded.value == record.value
        assert loaded.metadata == record.metadata
        assert loaded.classification is SensitivityClass.SECRET

    def test_strict_record_round_trip_preserves_all_fields(self, store: SecretStore) -> None:
        record = SecretRecord(
            key="aeat:test:strict-record",
            value=b"sensitive-payload-strict",
            classification=SensitivityClass.SECRET,
            metadata={"issued_by": "test-suite", "scope": "full-record"},
            created_at=datetime(2026, 5, 21, 11, 0, 0, tzinfo=UTC),
            expires_at=datetime(2026, 5, 21, 12, 0, 0, tzinfo=UTC),
        )

        store.put(record)

        assert store.get(record.key) == record

    def test_json_index_blob_reference_mutation_breaks_roundtrip(
        self,
        tmp_path: Path,
        store: SecretStore,
    ) -> None:
        record = _make_record(key="aeat:test:index-mutation", value=b"indexed-secret")
        store.put(record)
        assert store.get(record.key) == record
        index_path = tmp_path / "secrets" / "index.json"
        index_payload = json.loads(index_path.read_text(encoding="utf-8"))
        digest, entry = next(iter(index_payload["entries"].items()))
        assert len(digest) == 64
        assert entry["blob_sha256_plaintext_hex"] != "0" * 64
        entry["blob_sha256_plaintext_hex"] = "0" * 64
        index_path.write_text(json.dumps(index_payload, sort_keys=True), encoding="utf-8")

        with pytest.raises(BlobNotFoundError):
            store.get(record.key)

    def test_session_class_round_trip(self, store: SecretStore) -> None:
        record = _make_record(
            key="aeat:test:session",
            classification=SensitivityClass.SESSION,
        )
        store.put(record)
        assert store.get(record.key).value == record.value

    def test_missing_key_raises(self, store: SecretStore) -> None:
        with pytest.raises(SecretNotFoundError) as excinfo:
            store.get("never-stored")
        assert "digest" not in str(excinfo.value)

    def test_malformed_index_raises_localized_storage_validation(
        self,
        tmp_path: Path,
        store: SecretStore,
    ) -> None:
        index_path = tmp_path / "secrets" / "index.json"
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text("{not-json", encoding="utf-8")

        with pytest.raises(StorageValidationError, match="secret-store index") as excinfo:
            store.get("aeat:test:index-corrupt")

        assert excinfo.value.translated_message == "errors.integrity.integrity_storage_validation"
        assert "index-corrupt" not in str(excinfo.value)

    def test_index_does_not_leak_key(self, tmp_path: Path, store: SecretStore) -> None:
        record = _make_record(key="aeat:test:plaintext-key")
        store.put(record)
        index_path = tmp_path / "secrets" / "index.json"
        contents = index_path.read_text(encoding="utf-8")
        assert "plaintext-key" not in contents

    def test_index_does_not_leak_value(self, tmp_path: Path, store: SecretStore) -> None:
        secret_value = b"super-leak-canary-value-not-on-disk"
        record = _make_record(value=secret_value)
        store.put(record)
        index_path = tmp_path / "secrets" / "index.json"
        contents = index_path.read_text(encoding="utf-8")
        assert secret_value.decode() not in contents


class TestRetentionPolicy:
    def test_secret_requires_expiry(self, store: SecretStore) -> None:
        # Construct with expires_at=None explicitly so the store's
        # retention policy (not the pydantic validator) is what raises.
        rec = SecretRecord(
            key="aeat:test:no-expiry",
            value=b"x",
            classification=SensitivityClass.SECRET,
            created_at=datetime.now(UTC),
            expires_at=None,
        )
        with pytest.raises(RetentionPolicyError):
            store.put(rec)

    def test_session_requires_expiry(self, store: SecretStore) -> None:
        rec = SecretRecord(
            key="aeat:test:session-no-expiry",
            value=b"x",
            classification=SensitivityClass.SESSION,
            created_at=datetime.now(UTC),
            expires_at=None,
        )
        with pytest.raises(RetentionPolicyError):
            store.put(rec)

    def test_naive_datetime_rejected(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SecretRecord(
                key="x",
                value=b"y",
                classification=SensitivityClass.SECRET,
                created_at=datetime(2026, 4, 27, 12, 0, 0),
                expires_at=None,
            )

    def test_classification_must_be_secret_or_session(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SecretRecord(
                key="x",
                value=b"y",
                classification=SensitivityClass.FINANCIAL,
                created_at=datetime.now(UTC),
                expires_at=None,
            )


class TestOverwrite:
    def test_collision_without_overwrite_raises(self, store: SecretStore) -> None:
        first = _make_record(key="aeat:test:dup", value=b"first")
        store.put(first)
        with pytest.raises(SecretAlreadyExistsError) as excinfo:
            store.put(_make_record(key="aeat:test:dup", value=b"second"))
        assert "digest" not in str(excinfo.value)
        assert first.key not in str(excinfo.value)

    def test_overwrite_replaces_value(self, store: SecretStore) -> None:
        first = _make_record(key="aeat:test:upd", value=b"first")
        store.put(first)
        second = _make_record(key="aeat:test:upd", value=b"second")
        store.put(second, overwrite=True)
        assert store.get("aeat:test:upd").value == b"second"

    def test_overwrite_cleans_stale_blob(self, tmp_path: Path, store: SecretStore) -> None:
        # Two distinct values produce two distinct blobs; overwrite should
        # remove the first one.
        first = _make_record(key="aeat:test:rotate", value=b"first")
        store.put(first)
        manifests_after_first = list(store._blob_store.iter_manifests())
        assert len(manifests_after_first) == 1
        second = _make_record(key="aeat:test:rotate", value=b"second")
        store.put(second, overwrite=True)
        manifests_after_second = list(store._blob_store.iter_manifests())
        assert len(manifests_after_second) == 1

    def test_overwrite_logs_already_missing_stale_blob(
        self,
        caplog: pytest.LogCaptureFixture,
        store: SecretStore,
    ) -> None:
        first = _make_record(key="aeat:test:already-gone", value=b"first")
        first_ref = store.put(first)
        store._blob_store._manifest_path_for(first_ref.sha256_plaintext_hex).unlink()
        second = _make_record(key=first.key, value=b"second")

        caplog.set_level(logging.DEBUG, logger=_STORE_LOGGER_NAME)
        store.put(second, overwrite=True)

        messages = tuple(record.getMessage() for record in caplog.records if record.name == _STORE_LOGGER_NAME)
        assert any("stale secret-store blob cleanup skipped because blob is already absent" in msg for msg in messages)
        assert all(first.key not in msg for msg in messages)
        assert all(first_ref.sha256_plaintext_hex not in msg for msg in messages)


class TestDelete:
    def test_delete_removes_record(self, store: SecretStore) -> None:
        record = _make_record()
        store.put(record)
        store.delete(record.key)
        with pytest.raises(SecretNotFoundError):
            store.get(record.key)

    def test_delete_missing_raises(self, store: SecretStore) -> None:
        with pytest.raises(SecretNotFoundError) as excinfo:
            store.delete("never-stored")
        assert "digest" not in str(excinfo.value)

    def test_delete_logs_already_missing_blob(self, caplog: pytest.LogCaptureFixture, store: SecretStore) -> None:
        record = _make_record(key="aeat:test:delete-already-gone")
        blob_ref = store.put(record)
        store._blob_store._manifest_path_for(blob_ref.sha256_plaintext_hex).unlink()

        caplog.set_level(logging.DEBUG, logger=_STORE_LOGGER_NAME)
        store.delete(record.key)

        messages = tuple(record.getMessage() for record in caplog.records if record.name == _STORE_LOGGER_NAME)
        assert any(
            "secret-store blob cleanup on delete skipped because blob is already absent" in msg for msg in messages
        )
        assert all(record.key not in msg for msg in messages)
        assert all(blob_ref.sha256_plaintext_hex not in msg for msg in messages)
        with pytest.raises(SecretNotFoundError):
            store.get(record.key)


class TestRotate:
    def test_rotate_replaces_value(self, store: SecretStore) -> None:
        original = _make_record(value=b"v1")
        store.put(original)
        store.rotate(original.key, b"v2", expires_at=_expiry())
        assert store.get(original.key).value == b"v2"

    def test_rotate_missing_raises(self, store: SecretStore) -> None:
        with pytest.raises(SecretNotFoundError):
            store.rotate("never-stored", b"x", expires_at=_expiry())


class TestListDigests:
    def test_list_yields_one_digest_per_record(self, store: SecretStore) -> None:
        for i in range(4):
            store.put(_make_record(key=f"aeat:test:k{i}"))
        digests = list(store.list_digests())
        assert len(digests) == 4
        assert all(len(d) == 64 for d in digests)
