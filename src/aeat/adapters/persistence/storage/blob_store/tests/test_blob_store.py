"""Tests for the encrypted, classification-aware blob store."""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from ......core.classification import SensitivityClass
from ......core.config import override_settings
from ......core.errors import build_error_envelope, resolve_error_message
from ......core.external_constants import UTF_8_ENCODING
from ..._namespace_registry import BLOB_MANIFEST_SCHEMA_VERSION
from ...crypto import KEY_SIZE
from ...envelope import Envelope
from ...errors import BlobIntegrityError, BlobNotFoundError, DecryptionError, EnvelopeVersionError
from ...master_key import EphemeralMasterKeyProvider
from ...master_key._active_session import NoActiveBucketSessionError, activate_session
from ...master_key._bucket_session import BucketSession
from .. import BlobReference
from .._blob_store import BlobManifest, EncryptedBlobStore

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def _digest_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _bucket_session(*, dek: bytes) -> BucketSession:
    return BucketSession.open(
        bucket_id="test-bucket",
        kek=b"k" * KEY_SIZE,
        dek=dek,
        idle_minutes=15,
        opened_at=datetime.now(UTC),
    )


@pytest.fixture
def fixed_master_key() -> bytes:
    return secrets.token_bytes(KEY_SIZE)


@pytest.fixture
def store(tmp_path: Path, fixed_master_key: bytes) -> Iterator[EncryptedBlobStore]:
    provider = EphemeralMasterKeyProvider(key=fixed_master_key)
    yield EncryptedBlobStore(
        root_dir=tmp_path / "blob-store",
        master_key_provider=provider,
    )


class TestPlaintextCorpusBlobs:
    """CORPUS-class blobs are stored as plaintext under a content-addressed path."""

    def test_round_trip(self, store: EncryptedBlobStore) -> None:
        payload = b"public-corpus-pdf-bytes" * 100
        ref = store.put(
            payload,
            classification=SensitivityClass.CORPUS,
            content_type="application/pdf",
        )
        assert ref.sha256_plaintext_hex == _digest_hex(payload)
        assert ref.classification is SensitivityClass.CORPUS
        assert store.get(ref) == payload

    def test_corpus_blob_is_plaintext_on_disk(self, store: EncryptedBlobStore) -> None:
        payload = b"this-is-public-data"
        ref = store.put(payload, classification=SensitivityClass.CORPUS)
        target_dir = store.root_dir / "blobs" / ref.sha256_plaintext_hex[:2]
        plaintext_path = target_dir / ref.sha256_plaintext_hex
        assert plaintext_path.exists()
        assert plaintext_path.read_bytes() == payload

    def test_idempotent_put_for_same_payload(self, store: EncryptedBlobStore) -> None:
        payload = b"idempotency"
        first = store.put(payload, classification=SensitivityClass.CORPUS)
        second = store.put(payload, classification=SensitivityClass.CORPUS)
        assert first == second


class TestCiphertextSensitiveBlobs:
    """Non-CORPUS blobs are stored as ciphertext with envelope-encrypted DEKs."""

    @pytest.mark.parametrize(
        "classification",
        [
            SensitivityClass.SECRET,
            SensitivityClass.SESSION,
            SensitivityClass.IDENTITY,
            SensitivityClass.FINANCIAL,
            SensitivityClass.AUDIT,
        ],
    )
    def test_round_trip(self, store: EncryptedBlobStore, classification: SensitivityClass) -> None:
        payload = b"sensitive-payload-bytes" * 50
        ref = store.put(payload, classification=classification)
        assert ref.classification is classification
        assert store.get(ref) == payload

    def test_ciphertext_blob_is_not_plaintext_on_disk(self, store: EncryptedBlobStore) -> None:
        payload = b"this-must-not-leak-to-disk-in-plaintext"
        ref = store.put(payload, classification=SensitivityClass.FINANCIAL)
        target_dir = store.root_dir / "blobs" / ref.sha256_plaintext_hex[:2]
        ciphertext_path = target_dir / f"{ref.sha256_plaintext_hex}.enc"
        assert ciphertext_path.exists()
        wire = ciphertext_path.read_bytes()
        assert payload not in wire

    def test_manifest_carries_wrapped_dek(self, store: EncryptedBlobStore) -> None:
        payload = b"x" * 32
        store.put(payload, classification=SensitivityClass.IDENTITY)
        manifests = list(store.iter_manifests())
        assert len(manifests) == 1
        manifest = manifests[0]
        assert manifest.wrapped_dek is not None
        assert manifest.classification is SensitivityClass.IDENTITY
        assert manifest.sha256_ciphertext_hex is not None
        assert manifest.sha256_plaintext_hex == _digest_hex(payload)


class TestNotFoundAndIntegrity:
    """Missing blobs raise BlobNotFoundError; tampering raises BlobIntegrityError."""

    def test_get_missing_raises(self, store: EncryptedBlobStore) -> None:
        digest = _digest_hex(b"never-stored")
        ref = BlobReference(
            sha256_plaintext_hex=digest,
            classification=SensitivityClass.CORPUS,
        )
        with pytest.raises(BlobNotFoundError) as excinfo:
            store.get(ref)
        envelope = build_error_envelope(excinfo.value)
        with override_settings(aeat_output_language="en"):
            message = resolve_error_message(excinfo.value)

        assert excinfo.value.translated_message == "errors.fail.fail_storage_blob_not_found"
        assert str(store.root_dir) not in str(excinfo.value)
        assert digest not in str(excinfo.value)
        assert str(store.root_dir) not in message
        assert digest not in str(envelope.context)
        assert envelope.context == {
            "object_kind": "manifest",
            "surface": "encrypted_blob_store",
        }

    def test_delete_missing_raises(self, store: EncryptedBlobStore) -> None:
        ref = BlobReference(
            sha256_plaintext_hex=_digest_hex(b"never-stored"),
            classification=SensitivityClass.CORPUS,
        )
        with pytest.raises(BlobNotFoundError):
            store.delete(ref)

    def test_tampered_plaintext_raises_integrity(self, store: EncryptedBlobStore) -> None:
        payload = b"corpus-bytes"
        ref = store.put(payload, classification=SensitivityClass.CORPUS)
        plaintext_path = store.root_dir / "blobs" / ref.sha256_plaintext_hex[:2] / ref.sha256_plaintext_hex
        plaintext_path.write_bytes(b"tampered")
        with pytest.raises(BlobIntegrityError) as excinfo:
            store.get(ref)
        assert excinfo.value.translated_message == "errors.integrity.integrity_storage_blob"
        assert excinfo.value.context == {
            "object_kind": "blob",
            "surface": "encrypted_blob_store",
            "violation": "plaintext_digest",
        }

    def test_tampered_ciphertext_raises_integrity(self, store: EncryptedBlobStore) -> None:
        payload = b"sensitive"
        ref = store.put(payload, classification=SensitivityClass.FINANCIAL)
        ciphertext_path = store.root_dir / "blobs" / ref.sha256_plaintext_hex[:2] / f"{ref.sha256_plaintext_hex}.enc"
        wire = bytearray(ciphertext_path.read_bytes())
        # Flip a non-nonce byte so the on-disk SHA-256 disagrees with the manifest.
        wire[len(wire) // 2] ^= 0x01
        ciphertext_path.write_bytes(bytes(wire))
        with pytest.raises(BlobIntegrityError):
            store.get(ref)

    def test_get_corrupt_manifest_raises_localized_integrity_without_digest_leak(
        self,
        store: EncryptedBlobStore,
    ) -> None:
        ref = store.put(b"corrupt-manifest-direct-get-proof", classification=SensitivityClass.CORPUS)
        manifest_path = (
            store.root_dir / "blobs" / ref.sha256_plaintext_hex[:2] / (f"{ref.sha256_plaintext_hex}.manifest.json")
        )
        manifest_path.write_text("{", encoding=UTF_8_ENCODING)

        with pytest.raises(BlobIntegrityError) as excinfo:
            store.get(ref)

        assert excinfo.value.translated_message == "errors.integrity.integrity_storage_blob"
        assert excinfo.value.context == {
            "object_kind": "manifest",
            "surface": "encrypted_blob_store",
            "violation": "manifest_payload",
        }
        assert str(manifest_path) not in str(excinfo.value)
        assert ref.sha256_plaintext_hex not in str(excinfo.value)


class TestDelete:
    def test_delete_removes_payload_and_manifest(self, store: EncryptedBlobStore) -> None:
        payload = b"goodbye"
        ref = store.put(payload, classification=SensitivityClass.CORPUS)
        assert any(store.iter_manifests())
        store.delete(ref)
        assert not any(store.iter_manifests())
        with pytest.raises(BlobNotFoundError):
            store.get(ref)


class TestIterate:
    def test_iter_manifests_yields_each_blob(self, store: EncryptedBlobStore) -> None:
        for i in range(5):
            store.put(
                f"blob-{i}".encode(),
                classification=SensitivityClass.CORPUS if i % 2 == 0 else SensitivityClass.IDENTITY,
            )
        manifests = list(store.iter_manifests())
        assert len(manifests) == 5
        digests = {m.sha256_plaintext_hex for m in manifests}
        assert len(digests) == 5  # all unique

    def test_corrupt_manifest_fails_closed_without_path_leak(
        self,
        store: EncryptedBlobStore,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        ref = store.put(b"corrupt-manifest-proof", classification=SensitivityClass.CORPUS)
        manifest_path = (
            store.root_dir / "blobs" / ref.sha256_plaintext_hex[:2] / (f"{ref.sha256_plaintext_hex}.manifest.json")
        )
        manifest_path.write_text("{", encoding=UTF_8_ENCODING)

        with caplog.at_level("WARNING"), pytest.raises(BlobIntegrityError) as excinfo:
            list(store.iter_manifests())

        assert excinfo.value.translated_message == "errors.integrity.integrity_storage_blob"
        assert excinfo.value.context == {
            "object_kind": "manifest",
            "surface": "encrypted_blob_store",
            "violation": "manifest_payload",
        }
        assert str(manifest_path) not in caplog.text
        assert ref.sha256_plaintext_hex not in str(excinfo.value)

    def test_manifest_schema_drift_is_refused(self, store: EncryptedBlobStore) -> None:
        ref = store.put(b"schema-drift-manifest-proof", classification=SensitivityClass.CORPUS)
        manifest_path = (
            store.root_dir / "blobs" / ref.sha256_plaintext_hex[:2] / (f"{ref.sha256_plaintext_hex}.manifest.json")
        )
        envelope = Envelope[BlobManifest].model_validate_json(manifest_path.read_text(encoding=UTF_8_ENCODING))
        drifted = envelope.model_copy(update={"schema_version": BLOB_MANIFEST_SCHEMA_VERSION + 1})
        manifest_path.write_text(drifted.model_dump_json(), encoding=UTF_8_ENCODING)

        with pytest.raises(EnvelopeVersionError):
            list(store.iter_manifests())


class TestMasterKeyIsolation:
    """A different master key cannot decrypt previously-stored ciphertext."""

    def test_different_master_key_cannot_decrypt(self, tmp_path: Path) -> None:
        # Store under master key A
        provider_a = EphemeralMasterKeyProvider()
        store_a = EncryptedBlobStore(
            root_dir=tmp_path / "store",
            master_key_provider=provider_a,
        )
        ref = store_a.put(b"sensitive", classification=SensitivityClass.FINANCIAL)
        assert store_a.get(ref) == b"sensitive"

        # Open the same store dir under master key B
        provider_b = EphemeralMasterKeyProvider()
        store_b = EncryptedBlobStore(
            root_dir=tmp_path / "store",
            master_key_provider=provider_b,
        )
        with pytest.raises(DecryptionError):
            store_b.get(ref)


class TestBlobDigestValidation:
    @pytest.mark.parametrize(
        "bad_digest",
        (
            "../" + ("a" * 61),
            ("a" * 63) + "/",
            "." + ("a" * 63),
            "A" + ("a" * 63),
            "g" * 64,
        ),
    )
    def test_reference_rejects_non_lowercase_hex_digest(self, bad_digest: str) -> None:
        with pytest.raises(ValidationError):
            BlobReference(
                sha256_plaintext_hex=bad_digest,
                classification=SensitivityClass.CORPUS,
            )

    @pytest.mark.parametrize(
        "bad_digest",
        (
            "../" + ("a" * 61),
            ("a" * 63) + "/",
            "." + ("a" * 63),
            "A" + ("a" * 63),
            "g" * 64,
        ),
    )
    def test_manifest_rejects_path_bearing_or_non_hex_digest(self, bad_digest: str) -> None:
        with pytest.raises(ValidationError):
            BlobManifest(
                sha256_plaintext_hex=bad_digest,
                sha256_ciphertext_hex=None,
                size_plaintext=0,
                content_type="application/octet-stream",
                classification=SensitivityClass.CORPUS,
            )


class TestActiveSessionDefaultProvider:
    def test_ciphertext_write_without_provider_requires_active_bucket_session(self, tmp_path: Path) -> None:
        store = EncryptedBlobStore(root_dir=tmp_path / "store")

        with pytest.raises(NoActiveBucketSessionError) as excinfo:
            store.put(b"needs active session", classification=SensitivityClass.FINANCIAL)

        assert excinfo.value.translated_message == "errors.refused.refused_storage_master_key_no_active_session"

    def test_ciphertext_write_uses_active_bucket_session_when_provider_is_not_injected(
        self,
        tmp_path: Path,
        fixed_master_key: bytes,
    ) -> None:
        store = EncryptedBlobStore(root_dir=tmp_path / "store")

        with activate_session(_bucket_session(dek=fixed_master_key)):
            ref = store.put(b"active session blob", classification=SensitivityClass.FINANCIAL)
            assert store.get(ref) == b"active session blob"
