"""Unit tests for :class:`cadrumo.adapters.persistence.storage.secret_store.SecretStore`.

Exercises the put/get/delete/rotate API, the index encryption
invariants, the retention-policy gate, and the blob-cleanup behaviour
of overwrites.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

import pytest
from pydantic import ValidationError

from ......core.directory_scan import DirectoryEntryKind, scan_directory
from ......core.classification import SensitivityClass
from ......core.external_constants import UTF_8_ENCODING
from ......tests.master_key import EphemeralMasterKeyProvider
from ......tests.path_obstruction import obstructed_path
from ...blob_store import EncryptedBlobStore
from ...errors import (
    BlobNotFoundError,
    RetentionPolicyError,
    SecretAlreadyExistsError,
    SecretNotFoundError,
    StorageValidationError,
)
from .._secret_store import SecretRecord, SecretStore

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]
_STORE_LOGGER_NAME = "cadrumo.adapters.persistence.storage.secret_store._secret_store"

_SECRET_CREATED_AT = datetime(2026, 5, 28, 11, 55, 0, tzinfo=UTC)
_SECRET_EXPIRES_AT = datetime(2099, 5, 28, 11, 55, 0, tzinfo=UTC)


@pytest.fixture
def store(tmp_path: Path, fixed_master_key: bytes) -> Iterator[SecretStore]:
    provider = EphemeralMasterKeyProvider(key=fixed_master_key)
    blob_store = EncryptedBlobStore(
        root_dir=tmp_path / "store-root",
        master_key_provider=provider,
    )
    yield SecretStore(
        store_dir=tmp_path / "fallback-store",
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
        created_at=_SECRET_CREATED_AT,
        expires_at=expires_at if expires_at is not None else _SECRET_EXPIRES_AT,
    )


class _SecretRecordKwargs(TypedDict, total=False):
    """The :class:`SecretRecord` constructor keywords this parametrize overrides.

    A plain ``dict[str, object]`` cannot be ``**``-unpacked against
    ``SecretRecord``'s heterogeneously-typed fields (``key: str``,
    ``value: bytes``, ``classification: SensitivityClass``, ``metadata:
    dict[str, str]``, ``created_at``/``expires_at: datetime | None``): the
    checker cannot prove the dict carries only correctly-typed values per
    key. This TypedDict names every field so the ``**`` unpack matches
    per-key against the real constructor.
    """

    key: str
    value: bytes
    classification: SensitivityClass
    metadata: dict[str, str]
    created_at: datetime
    expires_at: datetime | None


def test_secret_record_validation_rejects_invalid_fields() -> None:
    cases: tuple[tuple[str, _SecretRecordKwargs], ...] = (
        (
            "naive-created-at",
            {
                "classification": SensitivityClass.SECRET,
                "created_at": datetime(2026, 4, 27, 12, 0, 0),
            },
        ),
        (
            "unsupported-classification",
            {
                "classification": SensitivityClass.FINANCIAL,
                "created_at": _SECRET_CREATED_AT,
            },
        ),
    )
    for case_id, overrides in cases:
        record_kwargs: _SecretRecordKwargs = {
            "key": "x",
            "value": b"y",
            "classification": SensitivityClass.SECRET,
            "created_at": _SECRET_CREATED_AT,
            "expires_at": None,
        }
        record_kwargs.update(overrides)
        with pytest.raises(ValidationError) as excinfo:
            SecretRecord(**record_kwargs)
        assert excinfo.value.errors(), case_id


def test_missing_record_write_operations_raise(store: SecretStore) -> None:
    with pytest.raises(SecretNotFoundError) as delete_exc:
        store.delete("never-stored")
    assert "digest" not in str(delete_exc.value)

    with pytest.raises(SecretNotFoundError) as rotate_exc:
        store.rotate("never-stored", b"x", expires_at=_SECRET_EXPIRES_AT)
    assert "digest" not in str(rotate_exc.value)


class TestPutAndGet:
    def test_secret_and_session_round_trip(self, store: SecretStore) -> None:
        for classification in (SensitivityClass.SECRET, SensitivityClass.SESSION):
            record = _make_record(
                key=f"aeat:test:{classification.value}",
                value=f"sensitive-payload-{classification.value}".encode(),
                classification=classification,
            )
            store.put(record)
            loaded = store.get(record.key)
            assert loaded.value == record.value, classification.value
            assert loaded.metadata == record.metadata, classification.value
            assert loaded.classification is classification, classification.value

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
        index_path = tmp_path / "fallback-store" / "index.json"
        index_payload = json.loads(index_path.read_text(encoding="utf-8"))
        digest, entry = next(iter(index_payload["entries"].items()))
        assert len(digest) == 64
        assert entry["blob_sha256_plaintext_hex"] != "0" * 64
        entry["blob_sha256_plaintext_hex"] = "0" * 64
        index_path.write_text(json.dumps(index_payload, sort_keys=True), encoding="utf-8")

        with pytest.raises(BlobNotFoundError):
            store.get(record.key)

    def test_missing_key_raises(self, store: SecretStore) -> None:
        with pytest.raises(SecretNotFoundError) as excinfo:
            store.get("never-stored")
        assert "digest" not in str(excinfo.value)

    def test_malformed_index_raises_localized_storage_validation(
        self,
        tmp_path: Path,
        store: SecretStore,
    ) -> None:
        index_path = tmp_path / "fallback-store" / "index.json"
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text("{not-json", encoding="utf-8")

        with pytest.raises(StorageValidationError, match="secret-store index") as excinfo:
            store.get("aeat:test:index-corrupt")

        assert excinfo.value.translated_message == "errors.integrity.integrity_storage_validation"
        assert "index-corrupt" not in str(excinfo.value)

    def test_index_does_not_leak_plaintext_key_or_value(self, tmp_path: Path, store: SecretStore) -> None:
        secret_value = b"super-leak-canary-value-not-on-disk"
        record = _make_record(key="aeat:test:plaintext-key", value=secret_value)
        store.put(record)
        index_path = tmp_path / "fallback-store" / "index.json"
        contents = index_path.read_text(encoding="utf-8")
        assert "plaintext-key" not in contents
        assert secret_value.decode() not in contents


class TestRetentionPolicy:
    def test_secret_and_session_require_expiry(self, store: SecretStore) -> None:
        for classification in (SensitivityClass.SECRET, SensitivityClass.SESSION):
            # Construct with expires_at=None explicitly so the store's
            # retention policy (not the pydantic validator) is what raises.
            rec = SecretRecord(
                key=f"aeat:test:{classification.value}:no-expiry",
                value=b"x",
                classification=classification,
                created_at=_SECRET_CREATED_AT,
                expires_at=None,
            )
            with pytest.raises(RetentionPolicyError):
                store.put(rec)


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
        store.rotate(original.key, b"v2", expires_at=_SECRET_EXPIRES_AT)
        assert store.get(original.key).value == b"v2"


class TestListDigests:
    def test_list_yields_one_digest_per_record(self, store: SecretStore) -> None:
        for i in range(4):
            store.put(_make_record(key=f"aeat:test:k{i}"))
        digests = list(store.list_digests())
        assert len(digests) == 4
        assert all(len(d) == 64 for d in digests)


def _payload_paths(blob_root: Path) -> list[Path]:
    """Return the encrypted payload files the blob store has written."""
    return list(scan_directory(blob_root, pattern="*.enc", recursive=True, select=DirectoryEntryKind.FILES))


class TestNaturalKeyBinding:
    """The encrypted record must answer for the key it was addressed by."""

    def test_get_refuses_a_valid_record_filed_under_another_key(self, store: SecretStore, tmp_path: Path) -> None:
        """Repointing one index entry at another entry's blob must not resolve.

        The index bound a digest to a blob reference, but nothing bound the
        encrypted record back to the key it was filed under. Both records are
        the same class, so the index/envelope/record classification triad saw
        no disagreement and the store returned a perfectly valid record for a
        different key.
        """
        store.put(_make_record(key="wave7:A", value=b"payload-A"))
        store.put(_make_record(key="wave7:B", value=b"payload-B"))

        index_path = tmp_path / "fallback-store" / "index.json"
        index = json.loads(index_path.read_text(encoding=UTF_8_ENCODING))
        a_digest, b_digest = list(index["entries"])
        index["entries"][a_digest]["blob_sha256_plaintext_hex"] = index["entries"][b_digest][
            "blob_sha256_plaintext_hex"
        ]
        index_path.write_text(json.dumps(index, indent=2), encoding=UTF_8_ENCODING)

        with pytest.raises(StorageValidationError):
            store.get("wave7:A")

    def test_get_still_returns_an_untampered_record(self, store: SecretStore) -> None:
        """Positive control: the binding check discriminates rather than always refusing."""
        store.put(_make_record(key="wave7:A", value=b"payload-A"))
        store.put(_make_record(key="wave7:B", value=b"payload-B"))

        assert store.get("wave7:A").value == b"payload-A"
        assert store.get("wave7:B").value == b"payload-B"


class TestDeleteOwnershipOrdering:
    """Index ownership is not dropped before the payload is confirmed gone."""

    def test_failed_blob_removal_leaves_the_record_owned_and_retryable(
        self,
        store: SecretStore,
        tmp_path: Path,
    ) -> None:
        """A blob that cannot be removed must not be disowned by the index.

        The delete path used to rewrite the index first and then swallow a
        failed blob removal as a warning. That left complete encrypted secret
        material on disk that nothing referenced: ``list_digests()`` was empty
        and ``get`` raised ``SecretNotFoundError`` while the original
        ``BlobReference`` still loaded the secret. Deleting the payload first
        makes the failure leave the record fully owned, so the operator can
        retry rather than losing track of live key material.
        """
        record = _make_record(key="aeat:test:ordering", value=b"payload")
        store.put(record)
        payloads = _payload_paths(tmp_path / "store-root")
        assert len(payloads) == 1
        payload_path = payloads[0]
        with obstructed_path(payload_path):
            with pytest.raises(OSError):
                store.delete("aeat:test:ordering")

            # Ownership survived the failure rather than being dropped ahead of it.
            assert list(store.list_digests()) != []

        # The obstruction restored the payload on exit, so the same delete now
        # succeeds: the failure left a retryable state, not a half-deleted one.
        store.delete("aeat:test:ordering")

        assert list(store.list_digests()) == []
        assert _payload_paths(tmp_path / "store-root") == []

    def test_successful_delete_removes_both_the_payload_and_the_index_entry(
        self,
        store: SecretStore,
        tmp_path: Path,
    ) -> None:
        """Positive control for the ordering above: the normal path still clears both."""
        store.put(_make_record(key="aeat:test:ordering", value=b"payload"))
        assert len(_payload_paths(tmp_path / "store-root")) == 1

        store.delete("aeat:test:ordering")

        assert _payload_paths(tmp_path / "store-root") == []
        assert list(store.list_digests()) == []
        with pytest.raises(SecretNotFoundError):
            store.get("aeat:test:ordering")


class TestPutBlobOwnership:
    """A published blob is owned by exactly one index entry, or by none."""

    def test_successful_put_leaves_no_unreferenced_payload(self, store: SecretStore, tmp_path: Path) -> None:
        """Every payload on disk is reachable through the index after a put."""
        store.put(_make_record(key="aeat:test:owned", value=b"payload"))

        payloads = _payload_paths(tmp_path / "store-root")
        index = json.loads((tmp_path / "fallback-store" / "index.json").read_text(encoding=UTF_8_ENCODING))
        owned = {entry["blob_sha256_plaintext_hex"] for entry in index["entries"].values()}

        assert len(payloads) == 1
        assert {path.stem for path in payloads} == owned

    def test_overwriting_a_record_leaves_exactly_one_owned_payload(
        self,
        store: SecretStore,
        tmp_path: Path,
    ) -> None:
        """An overwrite retires the superseded payload instead of accumulating one.

        Re-putting the same record does NOT reuse its blob: the envelope
        stamps ``written_at``, so the wire bytes differ and the
        content-addressed store mints a new blob every time. The overwrite
        path must therefore retire the previous payload, or every rewrite
        would leave live secret material behind that no index entry owns.
        """
        record = _make_record(key="aeat:test:same", value=b"payload")
        first = store.put(record)
        second = store.put(record, overwrite=True)

        assert first.sha256_plaintext_hex != second.sha256_plaintext_hex
        payloads = _payload_paths(tmp_path / "store-root")
        assert [path.stem for path in payloads] == [second.sha256_plaintext_hex]
        assert store.get("aeat:test:same").value == b"payload"
