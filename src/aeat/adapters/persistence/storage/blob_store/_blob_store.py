"""Encrypted, classification-aware blob store.

Blobs are persisted under a content-addressed layout rooted at
:attr:`Settings.aeat_blob_store_dir`. Each blob carries a sidecar
:class:`BlobManifest` envelope that pins the sensitivity classification,
the wire-format SHA-256 (plaintext for CORPUS; ciphertext for every
other class), the optional wrapped data-encryption key, the AEAD
nonce, the original size, and the content type.

Two layouts are supported:

- **Plaintext** (``SensitivityClass.CORPUS`` only): blob bytes are
  written verbatim under ``blobs/<hex[:2]>/<hex>`` where ``<hex>`` is
  the plaintext SHA-256. The manifest records ``encryption=None``.
- **Ciphertext** (every other class): the substrate mints a 32-byte
  data-encryption key (DEK), encrypts the blob with AES-256-GCM keyed
  by the DEK, wraps the DEK with the master key (also AES-256-GCM),
  and writes the ciphertext under ``blobs/<hex[:2]>/<hex>.enc`` where
  ``<hex>`` is the ciphertext SHA-256. The manifest records the
  wrapped DEK plus the AEAD nonces; the master key never touches disk.

The repository's public read API returns plaintext bytes; the
sensitivity class drives whether decryption is performed under the
hood. Manifests are :class:`Envelope[BlobManifest]` instances stored
under ``<hex>.manifest.json``.

Attempting to write a blob whose declared classification is incompatible
with its layout (e.g. tagging an arbitrary blob as CORPUS to skip
encryption) raises :class:`ClassificationError`. Missing blobs raise
:class:`BlobNotFoundError`. SHA-256 disagreement between the
on-disk file and the manifest raises :class:`BlobIntegrityError`.
"""

from __future__ import annotations

import hashlib
import os
import secrets
import tempfile
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .....core.classification import AtRestTreatment, SensitivityClass, default_policy_for
from .....core.locks import fsync_parent_dir
from .....core.logging import get_logger
from ..crypto._crypto import KEY_SIZE, EncryptedBlob, decrypt_record, encrypt_record
from ..envelope._envelope import EncryptionMetadata, Envelope, load_envelope, save_envelope
from ..errors import (
    BlobIntegrityError,
    BlobNotFoundError,
    ClassificationError,
    DecryptionError,
    EncryptionError,
    EnvelopeVersionError,
)
from ..master_key._active_session import get_active_master_key
from ..master_key._master_key import MasterKeyProvider

_log = get_logger(__name__)

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")

_BLOB_AAD = b"aeat.blob.payload.v1"
_DEK_AAD = b"aeat.blob.dek-wrap.v1"
_BLOB_MANIFEST_VERSION = 1


class BlobManifest(BaseModel):
    """Frozen manifest record for one blob in the encrypted blob store.

    Attributes:
        sha256_plaintext_hex: Lowercase hex digest of the original
            plaintext bytes. Always present.
        sha256_ciphertext_hex: Lowercase hex digest of the ciphertext
            on disk. ``None`` for plaintext (CORPUS) blobs.
        size_plaintext: Size of the original plaintext in bytes.
        content_type: Free-form MIME type or descriptive label
            (e.g. ``application/pdf``, ``application/json``,
            ``application/octet-stream``). The substrate does not parse
            or validate the value; it is recorded for forensic clarity
            only. Consumers that need a stricter classification should
            choose the appropriate :class:`SensitivityClass` rather
            than relying on the content-type label.
        classification: The :class:`SensitivityClass` of the payload.
        wrapped_dek: Per-blob data-encryption key, AES-256-GCM-wrapped
            with the master key, expressed as JSON-friendly
            :class:`EncryptionMetadata`. ``None`` for plaintext blobs.
        payload_metadata: AEAD metadata for the payload itself
            (nonce + algorithm). The ciphertext lives on disk; this
            field carries only the surrounding metadata. ``None`` for
            plaintext blobs.
    """

    model_config = _STRICT_FROZEN

    sha256_plaintext_hex: str = Field(min_length=64, max_length=64)
    sha256_ciphertext_hex: str | None = None
    size_plaintext: int = Field(ge=0)
    content_type: str = Field(min_length=1)
    classification: SensitivityClass
    wrapped_dek: EncryptionMetadata | None = None
    payload_metadata: EncryptionMetadata | None = None


class BlobReference(BaseModel):
    """Frozen public handle for one blob.

    Attributes:
        sha256_plaintext_hex: Lowercase hex digest of the plaintext.
            This is the natural key for retrieval; the consumer
            computes it from the plaintext at write time.
        classification: The classification used at write time. Required
            because the on-disk layout differs by class (plaintext vs
            ciphertext); the get path uses this to find the file.
    """

    model_config = _STRICT_FROZEN

    sha256_plaintext_hex: str = Field(min_length=64, max_length=64)
    classification: SensitivityClass


def _hex_digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class EncryptedBlobStore:
    """Repository for the at-rest, classification-aware blob store."""

    def __init__(
        self,
        *,
        root_dir: Path,
        master_key_provider: MasterKeyProvider | None = None,
    ) -> None:
        """Bind the store to a root directory and a master-key provider.

        Args:
            root_dir: Directory containing the ``blobs/`` subtree. The
                directory is created on first write.
            master_key_provider: Optional override. When ``None``, the
                process-wide :func:`get_master_key_provider` is used.
        """
        self._root_dir = Path(root_dir)
        self._master_key_provider = master_key_provider

    @property
    def root_dir(self) -> Path:
        """Return the configured root directory."""
        return self._root_dir

    def _master_key(self) -> bytes:
        if self._master_key_provider is not None:
            return self._master_key_provider.get_master_key()
        return get_active_master_key()

    def _shard_dir_for(self, hex_digest: str) -> Path:
        return self._root_dir / "blobs" / hex_digest[:2]

    def _plaintext_path_for(self, hex_digest: str) -> Path:
        return self._shard_dir_for(hex_digest) / hex_digest

    def _ciphertext_path_for(self, hex_digest: str) -> Path:
        return self._shard_dir_for(hex_digest) / f"{hex_digest}.enc"

    def _manifest_path_for(self, hex_digest: str) -> Path:
        return self._shard_dir_for(hex_digest) / f"{hex_digest}.manifest.json"

    def put(
        self,
        plaintext: bytes,
        *,
        classification: SensitivityClass,
        content_type: str = "application/octet-stream",
    ) -> BlobReference:
        """Persist ``plaintext`` and return a reference for retrieval.

        The on-disk layout is dictated by ``classification``: CORPUS-class
        blobs are written verbatim; every other class is encrypted with
        a fresh per-blob DEK that is then wrapped with the master key.

        Args:
            plaintext: Bytes to persist.
            classification: Sensitivity class.
            content_type: Stable MIME-type-style label stored in the
                manifest.

        Returns:
            A :class:`BlobReference` keyed by the plaintext SHA-256
            and the classification.

        Raises:
            ClassificationError: If a non-CORPUS class is requested but
                the policy table forbids ciphertext for it (defensive
                check; the default table never trips this).
        """
        sha_hex = _hex_digest(plaintext)
        policy = default_policy_for(classification)

        if classification is SensitivityClass.CORPUS:
            if policy.at_rest is not AtRestTreatment.PLAINTEXT:
                raise ClassificationError(
                    "CORPUS class must use PLAINTEXT at-rest treatment per policy.",
                )
            self._write_plaintext_blob(plaintext, sha_hex)
            manifest = BlobManifest(
                sha256_plaintext_hex=sha_hex,
                sha256_ciphertext_hex=None,
                size_plaintext=len(plaintext),
                content_type=content_type,
                classification=classification,
                wrapped_dek=None,
                payload_metadata=None,
            )
        else:
            if policy.at_rest is not AtRestTreatment.CIPHERTEXT_REQUIRED:
                raise ClassificationError(
                    f"class {classification} requires ciphertext at rest per policy.",
                )
            wrapped_dek_meta, payload_meta, ciphertext_hex = self._write_ciphertext_blob(plaintext, sha_hex)
            manifest = BlobManifest(
                sha256_plaintext_hex=sha_hex,
                sha256_ciphertext_hex=ciphertext_hex,
                size_plaintext=len(plaintext),
                content_type=content_type,
                classification=classification,
                wrapped_dek=wrapped_dek_meta,
                payload_metadata=payload_meta,
            )

        envelope = Envelope[BlobManifest](
            schema_version=_BLOB_MANIFEST_VERSION,
            written_at=datetime.now(UTC),
            classification=classification,
            payload=manifest,
        )
        save_envelope(envelope, self._manifest_path_for(sha_hex))
        _log.debug(
            "blob_store put: sha256=%s classification=%s size=%d content_type=%s",
            sha_hex[:16],
            classification.value,
            len(plaintext),
            content_type,
        )
        return BlobReference(
            sha256_plaintext_hex=sha_hex,
            classification=classification,
        )

    def get(self, reference: BlobReference) -> bytes:
        """Return the plaintext bytes for ``reference``.

        Raises:
            BlobNotFoundError: If the manifest or payload file is
                missing.
            BlobIntegrityError: If the on-disk SHA-256 disagrees with
                the manifest (tampering or storage corruption).
            ClassificationError: If the manifest declares a different
                classification than the reference (defensive).
        """
        manifest_path = self._manifest_path_for(reference.sha256_plaintext_hex)
        if not manifest_path.exists():
            raise BlobNotFoundError(
                f"no manifest at {manifest_path} for blob {reference.sha256_plaintext_hex}",
            )
        envelope = load_envelope(
            manifest_path,
            Envelope[BlobManifest],
            expected_class=reference.classification,
            max_supported_version=_BLOB_MANIFEST_VERSION,
        )
        manifest = envelope.payload
        if manifest.classification is SensitivityClass.CORPUS:
            return self._read_plaintext_blob(manifest)
        return self._read_ciphertext_blob(manifest)

    def delete(self, reference: BlobReference) -> None:
        """Remove the blob and its manifest.

        Order: payload bytes (plaintext or ciphertext) are unlinked
        first, then the manifest. If the payload unlink fails, the
        manifest is left in place so a subsequent ``get`` surfaces a
        :class:`BlobIntegrityError` rather than a silent
        ``BlobNotFoundError`` (sec-M-2).
        """
        sha_hex = reference.sha256_plaintext_hex
        manifest_path = self._manifest_path_for(sha_hex)
        if not manifest_path.exists():
            raise BlobNotFoundError(
                f"no manifest at {manifest_path} for blob {sha_hex}",
            )
        # Payload first: any error here leaves the manifest intact so
        # the inconsistency is observable on the next read.
        for payload_path in (self._plaintext_path_for(sha_hex), self._ciphertext_path_for(sha_hex)):
            if payload_path.exists():
                try:
                    payload_path.unlink()
                except OSError:
                    _log.error(
                        "blob_store delete: failed to remove payload %s sha256=%s",
                        payload_path,
                        sha_hex[:16],
                        exc_info=True,
                    )
                    raise
        # Manifest last; only its removal surface is allowed to be
        # treated as best-effort (the get path raises BlobNotFoundError
        # on a missing manifest, which is the expected post-delete
        # state).
        manifest_path.unlink()
        _log.debug(
            "blob_store delete: removed sha256=%s classification=%s",
            sha_hex[:16],
            reference.classification.value,
        )

    def iter_manifests(self) -> Iterator[BlobManifest]:
        """Yield the manifest of every blob currently persisted.

        The walk is shallow: only the canonical
        ``blobs/<hex[:2]>/<hex>.manifest.json`` files are visited.
        Each manifest is loaded through a single-read + inline
        version-gate path; corrupted or unparseable manifests are
        logged and skipped so a single broken file cannot break the
        iteration for every other blob.
        """
        for path, payload in self._iter_manifests_with_paths():
            del path
            yield payload

    def _iter_manifests_with_paths(self) -> Iterator[tuple[Path, BlobManifest]]:
        """Yield ``(manifest_path, manifest_payload)`` pairs for every blob.

        Internal helper used by :meth:`iter_manifests` and by the
        blob-store rotation path (which needs the path to atomically
        rewrite the manifest under the new master key).
        """
        blobs_dir = self._root_dir / "blobs"
        if not blobs_dir.exists():
            return
        for shard_dir in sorted(blobs_dir.iterdir()):
            if not shard_dir.is_dir():
                continue
            for manifest_path in sorted(shard_dir.glob("*.manifest.json")):
                # Single read + inline gate: iter_manifests is
                # classification-class-agnostic at the API surface, so
                # the only gate that applies is the version ceiling.
                try:
                    envelope = Envelope[BlobManifest].model_validate_json(
                        manifest_path.read_text(encoding="utf-8"),
                    )
                except (OSError, ValueError, ValidationError):
                    # A single corrupted manifest must not break the
                    # whole iteration. Log and skip; the operator can
                    # surface the broken file via filesystem inspection.
                    _log.warning(
                        "blob_store: skipping unparseable manifest %s",
                        manifest_path,
                        exc_info=True,
                    )
                    continue
                if envelope.schema_version > _BLOB_MANIFEST_VERSION:
                    raise EnvelopeVersionError(
                        f"envelope at {manifest_path} is at version {envelope.schema_version}; "
                        f"consumer supports up to {_BLOB_MANIFEST_VERSION}",
                    )
                yield manifest_path, envelope.payload

    def rotate_master_key(
        self,
        *,
        old_master_key_provider: MasterKeyProvider,
        new_master_key_provider: MasterKeyProvider,
    ) -> tuple[int, int, int]:
        """Re-wrap every blob's per-record DEK under the new master key.

        The blob store wraps each blob's DEK directly under the master
        key (``encrypt_record(dek, key=master_key, associated_data=_DEK_AAD)``).
        When the master key rotates, every wrapped DEK must be re-wrapped
        under the new master key or the blob becomes unrecoverable.

        Resume-idempotent: re-running on an already-rotated store
        decrypts the wrapped DEK under the new master key first; on
        success the manifest is skipped.

        Args:
            old_master_key_provider: Provider returning the master key
                that was in use when the blobs were last persisted.
            new_master_key_provider: Provider returning the new master
                key.

        Returns:
            A ``(rotated, skipped, errors)`` triple.
        """
        rotated = 0
        skipped = 0
        errors = 0
        old_master_key = old_master_key_provider.get_master_key()
        new_master_key = new_master_key_provider.get_master_key()
        for manifest_path, manifest in self._iter_manifests_with_paths():
            if manifest.wrapped_dek is None:
                # Plaintext-class blob (e.g. CORPUS); no wrapped DEK
                # to rotate.
                skipped += 1
                continue
            wrapped_blob = manifest.wrapped_dek.to_blob()
            # Try the new key first — already-rotated manifests succeed
            # here.
            try:
                decrypt_record(wrapped_blob, key=new_master_key, associated_data=_DEK_AAD)
                skipped += 1
                continue
            except (DecryptionError, EncryptionError) as exc:
                _log.debug(
                    "blob_store rotate_master_key: new key cannot decrypt wrapped_dek for %s; "
                    "falling back to old key (%s)",
                    manifest_path,
                    exc,
                )
            # Fall back to the old key.
            try:
                dek = decrypt_record(wrapped_blob, key=old_master_key, associated_data=_DEK_AAD)
            except (DecryptionError, EncryptionError):
                _log.warning(
                    "blob_store rotate_master_key: cannot decrypt wrapped_dek for %s",
                    manifest_path,
                    exc_info=True,
                )
                errors += 1
                continue
            new_wrapped = encrypt_record(dek, key=new_master_key, associated_data=_DEK_AAD)
            new_meta = EncryptionMetadata.from_blob(new_wrapped, associated_data=_DEK_AAD)
            new_manifest = manifest.model_copy(update={"wrapped_dek": new_meta})
            new_envelope = Envelope[BlobManifest](
                schema_version=_BLOB_MANIFEST_VERSION,
                written_at=datetime.now(UTC),
                classification=manifest.classification,
                payload=new_manifest,
            )
            try:
                save_envelope(new_envelope, manifest_path)
            except OSError:
                _log.warning(
                    "blob_store rotate_master_key: failed to atomic-write %s",
                    manifest_path,
                    exc_info=True,
                )
                errors += 1
                continue
            rotated += 1
        _log.info(
            "blob_store rotate_master_key: rotated=%d skipped=%d errors=%d (root=%s)",
            rotated,
            skipped,
            errors,
            self._root_dir,
        )
        return rotated, skipped, errors

    def _write_plaintext_blob(self, plaintext: bytes, sha_hex: str) -> None:
        target = self._plaintext_path_for(sha_hex)
        target.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write_bytes(target, plaintext)

    def _write_ciphertext_blob(
        self,
        plaintext: bytes,
        sha_hex: str,
    ) -> tuple[EncryptionMetadata, EncryptionMetadata, str]:
        master_key = self._master_key()
        dek = secrets.token_bytes(KEY_SIZE)
        payload_blob = encrypt_record(plaintext, key=dek, associated_data=_BLOB_AAD)
        wrapped_dek_blob = encrypt_record(dek, key=master_key, associated_data=_DEK_AAD)
        wire_payload = payload_blob.to_wire()
        ciphertext_hex = _hex_digest(wire_payload)
        target = self._ciphertext_path_for(sha_hex)
        target.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write_bytes(target, wire_payload)
        wrapped_dek_meta = EncryptionMetadata.from_blob(wrapped_dek_blob, associated_data=_DEK_AAD)
        payload_meta = EncryptionMetadata.from_blob(payload_blob, associated_data=_BLOB_AAD)
        return wrapped_dek_meta, payload_meta, ciphertext_hex

    def _read_plaintext_blob(self, manifest: BlobManifest) -> bytes:
        target = self._plaintext_path_for(manifest.sha256_plaintext_hex)
        if not target.exists():
            raise BlobNotFoundError(f"no plaintext payload at {target}")
        data = target.read_bytes()
        if _hex_digest(data) != manifest.sha256_plaintext_hex:
            raise BlobIntegrityError(
                f"plaintext blob digest mismatch at {target}: expected "
                f"{manifest.sha256_plaintext_hex}, got {_hex_digest(data)}",
            )
        return data

    def _read_ciphertext_blob(self, manifest: BlobManifest) -> bytes:
        if manifest.wrapped_dek is None or manifest.sha256_ciphertext_hex is None or manifest.payload_metadata is None:
            raise BlobIntegrityError(
                f"ciphertext manifest for {manifest.sha256_plaintext_hex} "
                "missing wrapped_dek, sha256_ciphertext_hex, or payload_metadata",
            )
        target = self._ciphertext_path_for(manifest.sha256_plaintext_hex)
        if not target.exists():
            raise BlobNotFoundError(f"no ciphertext payload at {target}")
        wire = target.read_bytes()
        if _hex_digest(wire) != manifest.sha256_ciphertext_hex:
            raise BlobIntegrityError(
                f"ciphertext blob digest mismatch at {target}: expected "
                f"{manifest.sha256_ciphertext_hex}, got {_hex_digest(wire)}",
            )
        master_key = self._master_key()
        wrapped_blob = manifest.wrapped_dek.to_blob()
        dek = decrypt_record(wrapped_blob, key=master_key, associated_data=_DEK_AAD)
        payload_blob = EncryptedBlob.from_wire(wire)
        plaintext = decrypt_record(payload_blob, key=dek, associated_data=_BLOB_AAD)
        if _hex_digest(plaintext) != manifest.sha256_plaintext_hex:
            raise BlobIntegrityError(
                f"decrypted blob digest mismatch: expected "
                f"{manifest.sha256_plaintext_hex}, got {_hex_digest(plaintext)}",
            )
        return plaintext

    @staticmethod
    def _atomic_write_bytes(target: Path, payload: bytes) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        # NamedTemporaryFile raising means no file was created; the
        # ``except OSError`` below re-raises cleanly.
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=target.parent,
                prefix=f"{target.stem}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                tmp_path = Path(handle.name)
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, target)
            fsync_parent_dir(target)
        except OSError:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)
            _log.error(
                "blob_store: atomic write failed target=%s",
                target,
                exc_info=True,
            )
            raise


__all__ = [
    "BlobIntegrityError",
    "BlobManifest",
    "BlobNotFoundError",
    "BlobReference",
    "EncryptedBlobStore",
]
