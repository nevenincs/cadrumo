"""Tests for the encrypted, classification-aware blob store."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from ......core.classification.policies import SensitivityClass
from ......core.config import override_settings
from ......core.errors.error_codes import build_error_envelope, resolve_error_message
from ......core.external_constants import UTF_8_ENCODING
from ......tests.master_key import EphemeralMasterKeyProvider
from ......tests.path_obstruction import obstructed_path
from ..._storage_path_definitions import BLOB_MANIFEST_SCHEMA_VERSION
from ...crypto.aead import KEY_SIZE
from ...envelope._envelope import Envelope
from ...errors import (
    BlobIntegrityError,
    BlobNotFoundError,
    DecryptionError,
    EnvelopeVersionError,
    StorageValidationError,
)
from ...master_key.active_session import NoActiveBucketSessionError, activate_session
from ...master_key.bucket_session import BucketSession
from .._blob_store import BlobManifest, BlobReference, EncryptedBlobStore

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_SESSION_OPENED_AT = datetime(2099, 5, 28, 11, 45, 0, tzinfo=UTC)
_BAD_DIGESTS = (
    "../" + ("a" * 61),
    ("a" * 63) + "/",
    "." + ("a" * 63),
    "A" + ("a" * 63),
    "g" * 64,
)


def _digest_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bucket_session(*, dek: bytes) -> BucketSession:
    return BucketSession.open(
        bucket_id="test-bucket",
        kek=b"k" * KEY_SIZE,
        dek=dek,
        idle_minutes=15,
        opened_at=_SESSION_OPENED_AT,
    )


@pytest.fixture
def store(tmp_path: Path, fixed_master_key: bytes) -> Iterator[EncryptedBlobStore]:
    provider = EphemeralMasterKeyProvider(key=fixed_master_key)
    yield EncryptedBlobStore(
        root_dir=tmp_path / "blob-store",
        master_key_provider=provider,
    )


# ``store.root_dir / "blobs" / ...`` below is the independent oracle for the
# ``blob_content_plaintext`` / ``blob_content_ciphertext`` / ``blob_manifest``
# grammar (``<root>/blobs/<sha256[:2]>/<sha256>[.enc|.manifest.json]``,
# anchored at ``blob_store_root`` -- i.e. whatever ``root_dir`` the store was
# constructed with, which ``store.root_dir`` supplies here). The store derives
# its own "blobs" segment from that same grammar constant
# (``_BLOB_STORE_DIRNAME``), so re-deriving the expected side through it would
# assert the accessor equals itself. Keep the literal.


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

    def test_round_trip_each_sensitive_classification(self, store: EncryptedBlobStore) -> None:
        classifications = (
            SensitivityClass.SECRET,
            SensitivityClass.SESSION,
            SensitivityClass.IDENTITY,
            SensitivityClass.FINANCIAL,
            SensitivityClass.AUDIT,
        )

        for classification in classifications:
            payload = (f"sensitive-payload-{classification.value}-".encode()) * 50
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
        with override_settings(cadrumo_output_language="en"):
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
    def test_reference_and_manifest_reject_path_bearing_or_non_hex_digests(self) -> None:
        for bad_digest in _BAD_DIGESTS:
            with pytest.raises(ValidationError):
                BlobReference(
                    sha256_plaintext_hex=bad_digest,
                    classification=SensitivityClass.CORPUS,
                )

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

        with activate_session(bucket_session(dek=fixed_master_key)):
            ref = store.put(b"active session blob", classification=SensitivityClass.FINANCIAL)
            assert store.get(ref) == b"active session blob"


class TestPutManifestCommitFailure:
    """A payload is never left on disk without the manifest that describes it."""

    @staticmethod
    def _manifest_path(store: EncryptedBlobStore, plaintext: bytes) -> Path:
        """Return the manifest path ``put`` will write for ``plaintext``.

        Obstructing this path is what makes the real ``save_envelope`` inside
        ``put`` meet an ``OSError`` while the payload write has already
        committed -- the window this class exists to pin.
        """
        sha_hex = hashlib.sha256(plaintext).hexdigest()
        shard = store.root_dir / "blobs" / sha_hex[:2]
        shard.mkdir(parents=True, exist_ok=True)
        return shard / f"{sha_hex}.manifest.json"

    @pytest.mark.parametrize(
        "classification",
        [SensitivityClass.SECRET, SensitivityClass.CORPUS],
    )
    def test_failed_manifest_commit_leaves_no_untracked_payload(
        self,
        store: EncryptedBlobStore,
        classification: SensitivityClass,
    ) -> None:
        """The payload is written before the manifest, so a manifest failure orphaned it.

        Nothing referenced the leftover bytes: ``iter_manifests`` returned no
        manifest while the payload file remained, untracked, for an encrypted
        class and as readable PLAINTEXT for CORPUS. A retry would rewrite it
        rather than reclaim it.
        """
        plaintext = b"orphan-probe-payload-" + classification.value.encode(UTF_8_ENCODING)
        sha_hex = hashlib.sha256(plaintext).hexdigest()
        shard = store.root_dir / "blobs" / sha_hex[:2]

        with obstructed_path(self._manifest_path(store, plaintext)):
            with pytest.raises(StorageValidationError):
                store.put(plaintext, classification=classification)

            assert not (shard / sha_hex).exists(), "plaintext payload survived a failed manifest commit"
            assert not (shard / f"{sha_hex}.enc").exists(), "ciphertext payload survived a failed manifest commit"

        # Outside the fault the store's own scan can run: it must find nothing,
        # because the failed put published nothing that outlived it.
        assert list(store.iter_manifests()) == []

    def test_a_successful_put_still_keeps_its_payload(self, store: EncryptedBlobStore) -> None:
        """Positive control: the rollback fires only on failure.

        Without this the test above would pass equally well if ``put`` had
        started deleting every payload it wrote.
        """
        reference = store.put(b"kept-payload", classification=SensitivityClass.SECRET)

        assert store.get(reference) == b"kept-payload"
        assert len(list(store.iter_manifests())) == 1

    def test_a_failed_commit_does_not_remove_a_pre_existing_blob(self, store: EncryptedBlobStore) -> None:
        """A live blob is not collateral damage when a later put of the same bytes fails.

        The store is content-addressed, so re-putting identical bytes targets
        the same payload path. Rolling back unconditionally would delete a
        blob whose manifest is intact and whose references still resolve.
        """
        plaintext = b"shared-content-addressed-payload"
        reference = store.put(plaintext, classification=SensitivityClass.SECRET)

        with obstructed_path(self._manifest_path(store, plaintext)), pytest.raises(StorageValidationError):
            store.put(plaintext, classification=SensitivityClass.SECRET)

        sha_hex = hashlib.sha256(plaintext).hexdigest()
        assert (store.root_dir / "blobs" / sha_hex[:2] / f"{sha_hex}.enc").is_file()
        assert reference.sha256_plaintext_hex == sha_hex

    def test_a_failed_commit_leaves_a_pre_existing_blob_readable(self, store: EncryptedBlobStore) -> None:
        """The surviving blob must still resolve, not merely still have a file.

        Preserving the path was not enough. A re-put of an encrypted class
        mints a fresh per-blob DEK, so the payload it writes over a live blob
        is different ciphertext under the same content-addressed name. When
        the manifest commit then failed, the rollback skipped the unlink and
        the file survived -- but the manifest that survived with it described
        the ciphertext digest of the bytes just overwritten. ``iter_manifests``
        still listed the blob and the original reference still pointed at it,
        while reading it failed the digest check: a silently corrupted blob
        that every inventory surface reported as healthy.
        """
        plaintext = b"live-blob-that-must-survive-a-failed-re-put"
        reference = store.put(plaintext, classification=SensitivityClass.SECRET)

        with obstructed_path(self._manifest_path(store, plaintext)), pytest.raises(StorageValidationError):
            store.put(plaintext, classification=SensitivityClass.SECRET)

        assert store.get(reference) == plaintext
        assert len(list(store.iter_manifests())) == 1

    def test_a_first_put_of_new_bytes_is_still_rolled_back(self, store: EncryptedBlobStore) -> None:
        """Positive control for the restore: it must not resurrect an orphan.

        The two rollback arms are chosen on whether a payload was displaced.
        Without this, a restore that ran unconditionally -- writing back an
        empty capture and leaving the file -- would satisfy the test above
        while re-introducing the untracked payload the compensation exists to
        remove.
        """
        plaintext = b"first-put-of-these-bytes"
        sha_hex = hashlib.sha256(plaintext).hexdigest()

        with obstructed_path(self._manifest_path(store, plaintext)), pytest.raises(StorageValidationError):
            store.put(plaintext, classification=SensitivityClass.SECRET)

        assert not (store.root_dir / "blobs" / sha_hex[:2] / f"{sha_hex}.enc").exists()
        assert list(store.iter_manifests()) == []
