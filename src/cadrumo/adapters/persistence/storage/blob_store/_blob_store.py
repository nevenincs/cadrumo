"""Encrypted, classification-aware blob store.

Blobs are persisted under a content-addressed layout rooted at
:attr:`Settings.cadrumo_blob_store_dir`. Each blob carries a sidecar
:class:`BlobManifest` :class:`Envelope` that pins the sensitivity
classification, the wire-format SHA-256 (plaintext for CORPUS; ciphertext for
every other class), the optional wrapped data-encryption key, the AEAD nonce,
the original size, and the content type.

Two layouts are supported:

- **Plaintext** (``SensitivityClass.CORPUS`` only): blob bytes are
  written verbatim under ``blobs/<hex[:2]>/<hex>`` where ``<hex>`` is
  the plaintext SHA-256. The manifest records ``encryption=None``.
- **Ciphertext** (every other class): the substrate mints a 32-byte
  data-encryption key (DEK), encrypts the blob with AES-256-GCM keyed
  by the DEK, wraps the DEK using the :class:`MasterKeyProvider` (also
  AES-256-GCM), and writes the ciphertext under the plaintext digest path
  ``blobs/<hex[:2]>/<hex>.enc``. The manifest records the ciphertext
  SHA-256, the wrapped DEK, and the AEAD nonces; the master key never
  touches disk.

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

import secrets
from collections.abc import Iterator
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from .....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core.atomic_write import atomic_write_bytes
from .....core.classification import AtRestTreatment, SensitivityClass, default_policy_for
from .....core.directory_scan import scan_directory
from .....core.external_constants import BINARY_MIME_TYPE
from .....core.external_constants import UTF_8_ENCODING as _UTF_8_ENCODING
from .....core.hashing import sha256_hex as _sha256_hex
from .....core.identity import ContentDigest
from .....core.logging import get_logger
from .....core.time import now
from .._namespace_registry import STORAGE_NAMESPACE_REGISTRY
from .._storage_path_definitions import BLOB_MANIFEST_SCHEMA_VERSION
from ..crypto.aead import KEY_SIZE, EncryptedBlob, decrypt_record, encrypt_record
from ..envelope import (
    EncryptionMetadata,
    Envelope,
    load_envelope,
    save_envelope,
)
from ..errors import (
    BlobIntegrityError,
    BlobNotFoundError,
    ClassificationError,
    DecryptionError,
    EncryptionError,
    EnvelopeVersionError,
    StorageValidationError,
)
from ..master_key import MasterKeyProvider, get_active_master_key

_log = get_logger(__name__)

_BLOB_AAD = b"cadrumo.blob.payload.v1"
_DEK_AAD = b"cadrumo.blob.dek-wrap.v1"
_BLOB_ERROR_CONTEXT = {"surface": "encrypted_blob_store"}
_BLOB_MANIFEST_PATH_KEY = "blob_manifest"
_BLOB_MANIFEST_PATH_DEFINITION = STORAGE_NAMESPACE_REGISTRY.path_by_key(_BLOB_MANIFEST_PATH_KEY)
_BLOB_STORE_DIRNAME = _BLOB_MANIFEST_PATH_DEFINITION.grammar.removeprefix("<root>/").split("/", maxsplit=1)[0]
_BLOB_MANIFEST_SUFFIX = _BLOB_MANIFEST_PATH_DEFINITION.grammar.rsplit("<sha256>", maxsplit=1)[1]
_BLOB_CIPHERTEXT_SUFFIX = ".enc"

# Every digest below is the canonical :data:`~core.identity.ContentDigest`.
# The module previously restated the lowercase-hex-64 rule in a local helper
# plus a per-model field validator. The restatement matched the canonical
# alias on every malformed value -- which is what hid the one place it did
# not: ContentDigest strips surrounding whitespace, so a valid digest arriving
# padded normalized everywhere else in the codebase and was refused here.


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

    sha256_plaintext_hex: ContentDigest
    sha256_ciphertext_hex: ContentDigest | None = None
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

    sha256_plaintext_hex: ContentDigest
    classification: SensitivityClass


def _hex_digest(data: bytes) -> str:
    return _sha256_hex(data)


def _path_log_marker(path: Path) -> str:
    try:
        resolved = path.expanduser().resolve(strict=False)
    except OSError:
        resolved = path.absolute()
    return _hex_digest(str(resolved).encode(_UTF_8_ENCODING))[:16]


def _blob_not_found_error(message: str, *, object_kind: str) -> BlobNotFoundError:
    return BlobNotFoundError(
        message,
        context={**_BLOB_ERROR_CONTEXT, "object_kind": object_kind},
        translated_message="errors.fail.fail_storage_blob_not_found",
    )


def _blob_integrity_error(message: str, *, violation: str, object_kind: str = "blob") -> BlobIntegrityError:
    return BlobIntegrityError(
        message,
        context={**_BLOB_ERROR_CONTEXT, "object_kind": object_kind, "violation": violation},
        translated_message="errors.integrity.integrity_storage_blob",
    )


def _assert_declared_plaintext_size(plaintext: bytes, manifest: BlobManifest) -> None:
    """Refuse a manifest whose declared size contradicts the recovered bytes.

    The digest check that precedes this pins the bytes themselves, so a
    disagreement here can only mean the manifest's own ``size_plaintext``
    field is wrong -- a cross-field contradiction inside one manifest rather
    than payload corruption. It was previously undetected on both read paths,
    which left a declared integrity field that could be contradicted while the
    store still reported a successful read: forensic metadata that says one
    thing while the store returns another, and a wrong answer for any consumer
    that budgets or bounds on the declared size without recounting.

    Shared by both layouts deliberately. The two read paths recover their
    plaintext by different routes, and giving each its own copy of the
    comparison is how one of them ends up without it.
    """
    if len(plaintext) != manifest.size_plaintext:
        raise _blob_integrity_error(
            "blob plaintext size disagrees with the manifest",
            violation="plaintext_size",
        )


def _coherent_blob_manifest(envelope: Envelope[BlobManifest]) -> BlobManifest:
    """Return the payload of ``envelope``, refusing a self-contradicting manifest.

    A manifest states its classification twice -- once on the envelope that
    wraps it, once on the payload inside -- and the two steer different
    decisions. Retrieval routes the on-disk layout from the *payload* value,
    the envelope loader gates the *outer* one against the caller's expectation,
    and key rotation reconstructs the outer value from the nested one when it
    rewrites. Nothing compared them, so editing one field alone made those
    surfaces disagree about the same blob: iteration reported a CORPUS blob
    that carried a wrapped DEK, retrieval of a still-valid reference followed
    the plaintext layout and failed, and rotating the manifest propagated the
    tampered value outward, leaving the blob unreadable afterwards.

    Every surface that opens a manifest passes through here, so the
    disagreement is refused once, before any layout routing or rewrite, rather
    than being caught differently -- or not at all -- by each consumer.
    """
    if envelope.classification is not envelope.payload.classification:
        raise _blob_integrity_error(
            "blob manifest envelope and payload classifications disagree",
            violation="manifest_classification_coherence",
            object_kind="manifest",
        )
    return envelope.payload


def _manifest_digest_from_path(path: Path) -> str:
    """Return the plaintext digest named by a manifest file's own filename."""
    return path.name.removesuffix(_BLOB_MANIFEST_SUFFIX)


def _assert_manifest_matches_filename(manifest: BlobManifest, *, expected_digest: str) -> None:
    """Refuse a manifest whose embedded digest is not the one it is filed under.

    The store is content-addressed: a manifest lives at
    ``blobs/<hex[:2]>/<hex>.manifest.json`` and the payload paths are derived
    from the digest the manifest CARRIES, not from the one in its filename.
    Nothing compared the two, so rewriting the embedded digest to another
    blob's re-pointed the read: ``get`` on the original reference located this
    manifest by its untouched filename and then returned the *other* blob's
    bytes, and iteration yielded that second identity for both files. Neither
    surface reported anything wrong, because every digest involved was real
    and every payload it checked reproduced its own hash.

    Both surfaces route through here, each supplying the digest it legitimately
    knows -- the caller's requested digest for a direct read, the filename for
    a scan -- so the binding is one invariant rather than two conventions.
    """
    if manifest.sha256_plaintext_hex != expected_digest:
        raise _blob_integrity_error(
            "blob manifest digest does not match the manifest it was read from",
            violation="manifest_digest_binding",
            object_kind="manifest",
        )


def _load_blob_manifest(path: Path, *, expected_class: SensitivityClass, expected_digest: str) -> BlobManifest:
    """Load one manifest for a direct read, gated on classification and identity.

    Returns the payload rather than the envelope so no caller can reach the
    nested classification without having passed :func:`_coherent_blob_manifest`
    first -- the outer/payload disagreement is unrepresentable downstream of
    this function rather than merely checked by convention.
    """
    try:
        envelope = load_envelope(
            path,
            Envelope[BlobManifest],
            expected_class=expected_class,
            max_supported_version=BLOB_MANIFEST_SCHEMA_VERSION,
        )
    except ClassificationError as exc:
        raise _blob_integrity_error(
            "invalid blob manifest classification",
            violation="manifest_classification",
            object_kind="manifest",
        ) from exc
    except EnvelopeVersionError as exc:
        raise _blob_integrity_error(
            "unsupported blob manifest schema version",
            violation="manifest_schema_version",
            object_kind="manifest",
        ) from exc
    except (OSError, ValueError, ValidationError) as exc:
        raise _blob_integrity_error(
            "invalid blob manifest",
            violation="manifest_payload",
            object_kind="manifest",
        ) from exc
    manifest = _coherent_blob_manifest(envelope)
    _assert_manifest_matches_filename(manifest, expected_digest=expected_digest)
    return manifest


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
                currently active bucket session's data-encryption key is used.
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
        return self._root_dir / _BLOB_STORE_DIRNAME / hex_digest[:2]

    def _plaintext_path_for(self, hex_digest: str) -> Path:
        return self._shard_dir_for(hex_digest) / hex_digest

    def _ciphertext_path_for(self, hex_digest: str) -> Path:
        return self._shard_dir_for(hex_digest) / f"{hex_digest}{_BLOB_CIPHERTEXT_SUFFIX}"

    def _manifest_path_for(self, hex_digest: str) -> Path:
        return self._shard_dir_for(hex_digest) / f"{hex_digest}{_BLOB_MANIFEST_SUFFIX}"

    def put(
        self,
        plaintext: bytes,
        *,
        classification: SensitivityClass,
        content_type: str = BINARY_MIME_TYPE,
    ) -> BlobReference:
        """Persist ``plaintext`` and return a reference for retrieval.

        The on-disk layout is dictated by ``classification``: CORPUS-class
        blobs are written verbatim; every other class is encrypted with
        a fresh per-blob DEK that is then wrapped with the master key.

        Args:
            plaintext: Bytes to persist.
            classification: :class:`SensitivityClass` controlling the at-rest
                treatment (plaintext for CORPUS, ciphertext for all other classes).
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
        # Captured before anything is written, so a failed manifest commit can
        # tell a payload THIS call published from one that was already on disk
        # under a live manifest. The store is content-addressed, so re-putting
        # identical bytes lands on the same paths; unlinking unconditionally
        # would delete a blob other references still resolve.
        #
        # The displaced BYTES are held, not merely the fact that a file was
        # there. A re-put of an encrypted class mints a fresh per-blob DEK, so
        # the payload it writes over a live blob is different ciphertext under
        # the same content-addressed name. Skipping the unlink alone therefore
        # preserved the file while its surviving manifest still described the
        # ciphertext digest of the bytes that had just been overwritten: the
        # live blob stayed listed and resolvable by reference, but reading it
        # failed the digest check. Restoring what was displaced is what makes
        # the untouched-blob guarantee true of its contents and not only of its
        # path. The cost is bounded by one blob, which this method already
        # holds in memory as ``plaintext``.
        displaced_payload = self._capture_displaced_payload(sha_hex)

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
            schema_version=BLOB_MANIFEST_SCHEMA_VERSION,
            written_at=now(),
            classification=classification,
            payload=manifest,
        )
        try:
            save_envelope(envelope, self._manifest_path_for(sha_hex))
        except (OSError, StorageValidationError):
            # The payload is on disk but no manifest describes what this call
            # wrote, so undo the publication before letting the original
            # failure surface. Nothing else would: no read path reports the
            # bytes, so nothing would ever collect them.
            #
            # Which undo depends on what was there first. A payload this call
            # introduced is removed outright -- otherwise it is untracked
            # ciphertext for an encrypted class and untracked PLAINTEXT for
            # CORPUS. A payload that displaced a live blob's bytes is put back,
            # so the manifest that survived still describes the payload it is
            # paired with.
            if displaced_payload is None:
                self._discard_unmanifested_payload(sha_hex)
            else:
                self._restore_displaced_payload(displaced_payload)
            raise
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

    def _capture_displaced_payload(self, sha_hex: str) -> tuple[Path, bytes] | None:
        """Return the payload a put is about to overwrite, or ``None`` if there is none.

        Args:
            sha_hex: Plaintext SHA-256 identifying the content-addressed paths.

        Returns:
            The existing payload path and its bytes, or ``None`` when no
            payload is stored under ``sha_hex`` yet. An unreadable existing
            payload also yields ``None``: it cannot be restored, and treating
            it as absent means the rollback removes the wreckage rather than
            leaving a file it cannot vouch for.
        """
        for payload_path in (self._plaintext_path_for(sha_hex), self._ciphertext_path_for(sha_hex)):
            if not payload_path.is_file():
                continue
            try:
                return payload_path, payload_path.read_bytes()
            except OSError:
                _log.warning(
                    "blob_store put: an existing payload could not be captured before being overwritten path_marker=%s",
                    _path_log_marker(payload_path),
                    exc_info=True,
                )
                return None
        return None

    def _restore_displaced_payload(self, displaced: tuple[Path, bytes]) -> None:
        """Put back the payload bytes a failed put overwrote.

        Best-effort for the same reason as
        :meth:`_discard_unmanifested_payload`: the caller is already unwinding
        a failure, and raising here would replace the reason the put failed
        with the reason the restore did. A failed restore leaves the blob's
        manifest describing bytes that are no longer under it, which is logged
        so an operator can re-put the content.

        Args:
            displaced: The payload path and the bytes captured before the write.
        """
        payload_path, payload_bytes = displaced
        try:
            atomic_write_bytes(payload_path, payload_bytes)
        except OSError:
            _log.warning(
                "blob_store put rollback: could not restore the payload this put overwrote path_marker=%s",
                _path_log_marker(payload_path),
                exc_info=True,
            )

    def _discard_unmanifested_payload(self, sha_hex: str) -> None:
        """Remove payload bytes left behind by a put whose manifest never committed.

        Best-effort by design: the caller is already unwinding a failure, and
        raising from here would replace the reason the put failed with the
        reason the cleanup failed. If this cannot remove the file, the outcome
        is the untracked payload that existed before this compensation, logged
        so an operator can find it.
        """
        for payload_path in (self._plaintext_path_for(sha_hex), self._ciphertext_path_for(sha_hex)):
            if not payload_path.exists():
                continue
            try:
                payload_path.unlink()
            except OSError:
                _log.warning(
                    "blob_store put rollback: could not remove an unmanifested payload path_marker=%s",
                    _path_log_marker(payload_path),
                    exc_info=True,
                )

    def get(self, reference: BlobReference) -> bytes:
        """Return the plaintext bytes for ``reference``.

        Args:
            reference: The blob reference identifying the stored object.

        Returns:
            Decrypted plaintext bytes for the referenced blob.

        Raises:
            BlobNotFoundError: When the manifest or payload file is missing.
            BlobIntegrityError: When the manifest is unusable, including when
                its envelope and payload classifications disagree -- the
                layout is routed from the payload value, so an unchecked
                disagreement would send the read to the wrong layout.
        """
        manifest_path = self._manifest_path_for(reference.sha256_plaintext_hex)
        if not manifest_path.exists():
            raise _blob_not_found_error("blob manifest not found", object_kind="manifest")
        manifest = _load_blob_manifest(
            manifest_path,
            expected_class=reference.classification,
            expected_digest=reference.sha256_plaintext_hex,
        )
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
            raise _blob_not_found_error("blob manifest not found", object_kind="manifest")
        # Payload first: any error here leaves the manifest intact so
        # the inconsistency is observable on the next read.
        for payload_path in (self._plaintext_path_for(sha_hex), self._ciphertext_path_for(sha_hex)):
            if payload_path.exists():
                try:
                    payload_path.unlink()
                except OSError as exc:
                    _log.error(
                        "blob_store delete: failed to remove payload path_marker=%s error_type=%s",
                        _path_log_marker(payload_path),
                        type(exc).__name__,
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
        """Yield the :class:`BlobManifest` of every blob currently persisted.

        The walk is shallow: only the canonical
        ``blobs/<hex[:2]>/<hex>.manifest.json`` files are visited.
        Each manifest is loaded through a single-read + inline
        version-gate path; corrupted or unparseable manifests fail
        closed so corruption does not disappear from audit flows.
        """
        for path, payload in self._iter_manifests_with_paths():
            del path
            yield payload

    def _iter_manifests_with_paths(self) -> Iterator[tuple[Path, BlobManifest]]:
        """Yield ``(manifest_path, manifest_payload)`` pairs for every blob.

        Internal helper used by :meth:`iter_manifests` and by the
        blob-store rotation path (which needs the path to atomically
        rewrite the manifest under the new master key).

        Rotation reaches the coherence gate through this helper, which is
        why the gate lives here rather than in the rotation loop: rotation
        rebuilds the outer classification from the nested value, so a
        manifest whose two classifications disagree would have that
        disagreement written outward and made permanent.
        """
        blobs_dir = self._root_dir / _BLOB_STORE_DIRNAME
        if not blobs_dir.exists():
            return
        for shard_dir in scan_directory(blobs_dir):
            if not shard_dir.is_dir():
                continue
            for manifest_path in scan_directory(shard_dir, pattern="*.manifest.json"):
                # Single read + inline gate: iter_manifests is
                # classification-class-agnostic at the API surface, so the
                # schema-version contract is the only *expectation* gate here.
                # The outer/payload coherence check below is not an
                # expectation -- it is an invariant of the manifest itself --
                # so it applies to this surface exactly as to a direct read.
                try:
                    envelope = Envelope[BlobManifest].model_validate_json(
                        manifest_path.read_text(encoding=_UTF_8_ENCODING),
                    )
                except (OSError, ValueError, ValidationError) as exc:
                    _log.warning(
                        "blob_store: invalid manifest path_marker=%s error_type=%s",
                        _path_log_marker(manifest_path),
                        type(exc).__name__,
                    )
                    raise _blob_integrity_error(
                        "invalid blob manifest",
                        violation="manifest_payload",
                        object_kind="manifest",
                    ) from exc
                if envelope.schema_version != BLOB_MANIFEST_SCHEMA_VERSION:
                    raise EnvelopeVersionError(
                        f"blob manifest is at version {envelope.schema_version}; "
                        f"consumer expects {BLOB_MANIFEST_SCHEMA_VERSION}",
                    )
                manifest = _coherent_blob_manifest(envelope)
                _assert_manifest_matches_filename(
                    manifest,
                    expected_digest=_manifest_digest_from_path(manifest_path),
                )
                yield manifest_path, manifest

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
            old_master_key_provider: :class:`MasterKeyProvider` returning
                the master key that was in use when the blobs were last persisted.
            new_master_key_provider: :class:`MasterKeyProvider` returning
                the new master key.

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
                    _path_log_marker(manifest_path),
                    type(exc).__name__,
                )
            # Fall back to the old key.
            try:
                dek = decrypt_record(wrapped_blob, key=old_master_key, associated_data=_DEK_AAD)
            except (DecryptionError, EncryptionError):
                _log.warning(
                    "blob_store rotate_master_key: cannot decrypt wrapped_dek path_marker=%s",
                    _path_log_marker(manifest_path),
                )
                errors += 1
                continue
            new_wrapped = encrypt_record(dek, key=new_master_key, associated_data=_DEK_AAD)
            new_meta = EncryptionMetadata.from_blob(new_wrapped, associated_data=_DEK_AAD)
            new_manifest = manifest.model_copy(update={"wrapped_dek": new_meta})
            new_envelope = Envelope[BlobManifest](
                schema_version=BLOB_MANIFEST_SCHEMA_VERSION,
                written_at=now(),
                classification=manifest.classification,
                payload=new_manifest,
            )
            try:
                save_envelope(new_envelope, manifest_path)
            except OSError:
                _log.warning(
                    "blob_store rotate_master_key: failed to atomic-write path_marker=%s",
                    _path_log_marker(manifest_path),
                )
                errors += 1
                continue
            rotated += 1
        _log.info(
            "blob_store rotate_master_key: rotated=%d skipped=%d errors=%d root_marker=%s",
            rotated,
            skipped,
            errors,
            _path_log_marker(self._root_dir),
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
            raise _blob_not_found_error("blob payload not found", object_kind="payload")
        data = target.read_bytes()
        if _hex_digest(data) != manifest.sha256_plaintext_hex:
            raise _blob_integrity_error("plaintext blob digest mismatch", violation="plaintext_digest")
        _assert_declared_plaintext_size(data, manifest)
        return data

    def _read_ciphertext_blob(self, manifest: BlobManifest) -> bytes:
        if manifest.wrapped_dek is None or manifest.sha256_ciphertext_hex is None or manifest.payload_metadata is None:
            raise _blob_integrity_error(
                "ciphertext manifest missing encryption metadata",
                violation="ciphertext_manifest_metadata",
                object_kind="manifest",
            )
        target = self._ciphertext_path_for(manifest.sha256_plaintext_hex)
        if not target.exists():
            raise _blob_not_found_error("blob payload not found", object_kind="payload")
        wire = target.read_bytes()
        if _hex_digest(wire) != manifest.sha256_ciphertext_hex:
            raise _blob_integrity_error("ciphertext blob digest mismatch", violation="ciphertext_digest")
        master_key = self._master_key()
        wrapped_blob = manifest.wrapped_dek.to_blob()
        dek = decrypt_record(wrapped_blob, key=master_key, associated_data=_DEK_AAD)
        payload_blob = EncryptedBlob.from_wire(wire)
        plaintext = decrypt_record(payload_blob, key=dek, associated_data=_BLOB_AAD)
        if _hex_digest(plaintext) != manifest.sha256_plaintext_hex:
            raise _blob_integrity_error("decrypted blob digest mismatch", violation="decrypted_digest")
        _assert_declared_plaintext_size(plaintext, manifest)
        return plaintext

    @staticmethod
    def _atomic_write_bytes(target: Path, payload: bytes) -> None:
        try:
            atomic_write_bytes(target, payload)
        except OSError:
            _log.error(
                "blob_store: atomic write failed path_marker=%s",
                _path_log_marker(target),
            )
            raise


__all__ = [
    "BlobIntegrityError",
    "BlobManifest",
    "BlobNotFoundError",
    "BlobReference",
    "EncryptedBlobStore",
]
