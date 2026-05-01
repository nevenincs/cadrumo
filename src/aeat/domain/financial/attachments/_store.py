"""Content-addressed byte and manifest store for the attachment service.

The store separates write-once byte blobs from encrypted JSON manifests under a
shared configured root:

* ``<root>/blobs/<sha256>``                   — raw bytes, write-once.
* ``<root>/manifests/<sha256>.envelope.json`` — encrypted manifest envelope at
  FINANCIAL class via :func:`save_encrypted_envelope`.

Every public method that composes a path from an ``attachment_id`` / ``sha256``
input first validates the token is a 64-character lowercase hex digest, so
untrusted CLI inputs cannot traverse out of the store root or exploit NTFS
case-insensitivity to alias blobs.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from ....core.logging import get_logger
from ._errors import AttachmentNotFoundError, AttachmentPersistenceError, AttachmentValidationError
from ._models import Attachment

_LOGGER = get_logger(__name__)

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")
_BLOBS_DIRNAME = "blobs"
_MANIFESTS_DIRNAME = "manifests"
_MANIFEST_SUFFIX = ".envelope.json"
_MANIFEST_LOCK_SUFFIX = ".lock"
_STREAM_CHUNK_SIZE = 1024 * 1024  # 1 MiB
_HEX_DIGITS = frozenset("0123456789abcdef")
_HKDF_CONTEXT_ATTACHMENT_MANIFEST = b"aeat.domain.financial.attachments.manifest.v1"
_ATTACHMENT_MANIFEST_VERSION = 1


def _require_digest(value: str, *, field_name: str = "attachment_id") -> str:
    """Reject any digest input that is not a 64-char lowercase hex string.

    Args:
        value: Untrusted digest candidate.
        field_name: Human-readable field name used in the raised error.

    Returns:
        The validated digest, lowercase.

    Raises:
        AttachmentValidationError: When the input is not a 64-char lowercase
            hex digest. The validation deliberately rejects uppercase digests
            so NTFS case-insensitivity cannot be used to alias blobs across
            `<digest>` and `<DIGEST>` on case-preserving filesystems.
    """
    if not isinstance(value, str):
        raise AttachmentValidationError(f"{field_name} must be a 64-character lowercase hex digest")
    if len(value) != 64 or any(char not in _HEX_DIGITS for char in value):
        raise AttachmentValidationError(f"{field_name} must be a 64-character lowercase hex digest")
    return value


class AttachmentStore(BaseModel):
    """Filesystem-backed content-addressed attachment store."""

    model_config = _STRICT_FROZEN

    root: Path = Field()

    @field_validator("root")
    @classmethod
    def _resolve_root(cls, value: Path) -> Path:
        """Persist an absolute, resolved root so later reads are portable."""
        return Path(value).resolve()

    @classmethod
    def at(cls, root: Path) -> Self:
        """Construct a store rooted at ``root``.

        Args:
            root: Directory that will host ``blobs/`` and ``manifests/``.

        Returns:
            A validated, frozen store instance.
        """
        return cls(root=root)

    @property
    def blobs_dir(self) -> Path:
        """Directory holding write-once byte blobs keyed by SHA-256."""
        return self.root / _BLOBS_DIRNAME

    @property
    def manifests_dir(self) -> Path:
        """Directory holding mutable JSON manifests keyed by SHA-256."""
        return self.root / _MANIFESTS_DIRNAME

    def blob_path(self, sha256: str) -> Path:
        """Return the on-disk blob path for ``sha256``.

        Raises:
            AttachmentValidationError: When ``sha256`` is not a 64-char hex digest.
        """
        return self.blobs_dir / _require_digest(sha256, field_name="sha256")

    def manifest_path(self, attachment_id: str) -> Path:
        """Return the on-disk manifest path for ``attachment_id``.

        Raises:
            AttachmentValidationError: When ``attachment_id`` is not a
                64-char hex digest.
        """
        digest = _require_digest(attachment_id)
        return self.manifests_dir / f"{digest}{_MANIFEST_SUFFIX}"

    def _manifest_lock_target(self, attachment_id: str) -> Path:
        """Return the per-manifest lock sidecar path."""
        digest = _require_digest(attachment_id)
        return self.manifests_dir / f"{digest}{_MANIFEST_LOCK_SUFFIX}"

    def put_bytes(self, data: bytes) -> str:
        """Write ``data`` under its SHA-256 digest if not already present.

        Args:
            data: Raw attachment bytes to persist.

        Returns:
            The lowercase hex SHA-256 digest of ``data``.

        Raises:
            AttachmentPersistenceError: When the blob cannot be written.
        """
        digest = hashlib.sha256(data).hexdigest()
        target = self.blob_path(digest)
        if target.exists():
            _LOGGER.debug("reusing existing blob for %s", digest)
            return digest
        try:
            self.blobs_dir.mkdir(parents=True, exist_ok=True)
            _write_once_bytes(target, data)
        except OSError as exc:
            raise AttachmentPersistenceError(f"unable to write attachment blob: {target}") from exc
        _LOGGER.info("stored attachment blob %s (%d bytes)", digest, len(data))
        return digest

    def put_file(self, source: Path) -> tuple[str, int]:
        """Stream ``source`` into the store, hashing and writing in chunks.

        Reads and writes happen in 1 MiB chunks so large attachments (scans,
        multi-page invoices) never force the full payload into memory. If a
        blob for the resulting digest already exists the streamed tempfile is
        discarded to preserve the write-once invariant. If a concurrent
        writer creates the target blob between the streaming pass and the
        final rename, the rename is retried as a no-op and the tempfile is
        unlinked so the original blob survives untouched.

        Args:
            source: Filesystem path of the bytes to stream into the store.

        Returns:
            A ``(digest, bytes_size)`` tuple with the lowercase hex SHA-256
            digest and the exact byte count of the source payload.

        Raises:
            AttachmentPersistenceError: When the source cannot be read or the
                blob cannot be written.
        """
        hasher = hashlib.sha256()
        bytes_size = 0
        tmp_path: Path | None = None
        try:
            self.blobs_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=self.blobs_dir,
                prefix="stream.",
                suffix=".tmp",
                delete=False,
            ) as tmp_handle:
                tmp_path = Path(tmp_handle.name)
                with source.open("rb") as reader:
                    while True:
                        chunk = reader.read(_STREAM_CHUNK_SIZE)
                        if not chunk:
                            break
                        hasher.update(chunk)
                        bytes_size += len(chunk)
                        tmp_handle.write(chunk)
                tmp_handle.flush()
                # fsync the tempfile bytes before publication so the
                # directory entry never points at an inode whose
                # contents haven't been written through.
                os.fsync(tmp_handle.fileno())
            digest = hasher.hexdigest()
            target = self.blob_path(digest)
            _commit_write_once(tmp_path, target)
            tmp_path = None
            _LOGGER.info("stored attachment blob %s (%d bytes)", digest, bytes_size)
            return digest, bytes_size
        except OSError as exc:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)
            raise AttachmentPersistenceError(f"unable to stream attachment source: {source}") from exc

    def read_bytes(self, sha256: str) -> bytes:
        """Return the raw bytes for ``sha256``.

        Small helper for callers that can reasonably materialise the entire
        blob in memory. Prefer :meth:`open_bytes` for large payloads.

        Args:
            sha256: 64-character lowercase hex digest of the blob to read.

        Returns:
            The raw attachment bytes.

        Raises:
            AttachmentValidationError: When ``sha256`` is not a 64-char hex digest.
            AttachmentNotFoundError: When no blob exists for ``sha256``.
            AttachmentPersistenceError: When the blob cannot be read.
        """
        target = self.blob_path(sha256)
        if not target.exists():
            raise AttachmentNotFoundError(f"attachment blob not found: {sha256}")
        try:
            return target.read_bytes()
        except OSError as exc:
            raise AttachmentPersistenceError(f"unable to read attachment blob: {target}") from exc

    def open_bytes(self, sha256: str) -> BinaryIO:
        """Open the blob for ``sha256`` as a streaming binary handle.

        Callers must close the returned handle (use a ``with`` block). This is
        the memory-safe read path for large attachments and satisfies the
        ``BytesView`` Protocol shape named in issue #76.

        Args:
            sha256: 64-character lowercase hex digest of the blob to read.

        Returns:
            A binary file handle positioned at byte zero.

        Raises:
            AttachmentValidationError: When ``sha256`` is not a 64-char hex digest.
            AttachmentNotFoundError: When no blob exists for ``sha256``.
            AttachmentPersistenceError: When the blob cannot be opened.
        """
        target = self.blob_path(sha256)
        if not target.exists():
            raise AttachmentNotFoundError(f"attachment blob not found: {sha256}")
        try:
            return target.open("rb")
        except OSError as exc:
            raise AttachmentPersistenceError(f"unable to open attachment blob: {target}") from exc

    def verify_blob(self, attachment_id: str) -> None:
        """Re-hash the on-disk blob and verify it matches ``attachment_id``.

        The audit guarantee the feature sells is that every attachment is
        provable end-to-end: if a tax inspector asks "did this blob change?",
        a SHA-256 rescan must answer. This helper provides that guarantee.

        Args:
            attachment_id: Stable attachment identifier (SHA-256 hex digest).

        Raises:
            AttachmentValidationError: When ``attachment_id`` is not a
                64-char hex digest, or when the on-disk blob's SHA-256
                disagrees with ``attachment_id``.
            AttachmentNotFoundError: When no blob exists for ``attachment_id``.
            AttachmentPersistenceError: When the blob cannot be read.
        """
        digest = _require_digest(attachment_id)
        target = self.blob_path(digest)
        if not target.exists():
            raise AttachmentNotFoundError(f"attachment blob not found: {digest}")
        hasher = hashlib.sha256()
        try:
            with target.open("rb") as reader:
                while True:
                    chunk = reader.read(_STREAM_CHUNK_SIZE)
                    if not chunk:
                        break
                    hasher.update(chunk)
        except OSError as exc:
            raise AttachmentPersistenceError(f"unable to re-hash attachment blob: {target}") from exc
        actual = hasher.hexdigest()
        if actual != digest:
            raise AttachmentValidationError(f"blob digest drift for {digest}: on-disk sha256 is {actual}")

    def write_manifest(self, attachment: Attachment) -> None:
        """Persist ``attachment`` to its manifest file atomically.

        The manifest is written as a :class:`CipherEnvelope` at
        FINANCIAL class via the substrate's ``save_encrypted_envelope``
        helper — no plaintext linkage between the attachment digest and
        the linked transaction/invoice IDs lands on disk.

        Args:
            attachment: Validated attachment whose manifest should be written.

        Raises:
            AttachmentPersistenceError: When the manifest cannot be written.
        """
        # Storage imports are deferred so the attachments package does
        # not pull ``aeat.storage`` (with its Alembic plugin discovery)
        # into every CLI command's import chain. Mirrors the json-pipe-
        # safety discipline applied to every other persistence consumer.
        from ....adapters.persistence.storage import (
            Envelope,
            SensitivityClass,
            exclusive_file_lock,
            save_encrypted_envelope,
        )
        from ....adapters.persistence.storage._encrypted_columns import _resolve_master_key_provider

        target = self.manifest_path(attachment.attachment_id)
        try:
            self.manifests_dir.mkdir(parents=True, exist_ok=True)
            with exclusive_file_lock(self._manifest_lock_target(attachment.attachment_id)):
                envelope = Envelope[Attachment](
                    schema_version=_ATTACHMENT_MANIFEST_VERSION,
                    written_at=datetime.now(UTC),
                    classification=SensitivityClass.FINANCIAL,
                    payload=attachment,
                )
                save_encrypted_envelope(
                    envelope,
                    target,
                    master_key_provider=_resolve_master_key_provider(),
                    hkdf_context=_HKDF_CONTEXT_ATTACHMENT_MANIFEST,
                )
        except OSError as exc:
            raise AttachmentPersistenceError(f"unable to write attachment manifest: {target}") from exc
        _LOGGER.info("wrote attachment manifest %s", attachment.attachment_id)

    def load_manifest(self, attachment_id: str) -> Attachment:
        """Load and validate the manifest for ``attachment_id``.

        The filename-derived digest and the manifest's internal
        ``attachment_id`` field must agree. A manifest file whose name
        disagrees with its payload surfaces as
        :class:`AttachmentValidationError` rather than being silently
        returned.

        Args:
            attachment_id: Stable attachment identifier (SHA-256 hex digest).

        Returns:
            The validated attachment manifest.

        Raises:
            AttachmentValidationError: When ``attachment_id`` is not a
                64-char hex digest, the manifest JSON is invalid, or the
                stored ``attachment_id`` disagrees with the filename.
            AttachmentNotFoundError: When no manifest exists.
            AttachmentPersistenceError: When the manifest cannot be read.
        """
        from ....adapters.persistence.storage import (
            Envelope,
            SensitivityClass,
            load_encrypted_envelope,
        )
        from ....adapters.persistence.storage._encrypted_columns import _resolve_master_key_provider
        from ....adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError

        digest = _require_digest(attachment_id)
        target = self.manifest_path(digest)
        if not target.exists():
            raise AttachmentNotFoundError(f"attachment manifest not found: {digest}")
        try:
            envelope = load_encrypted_envelope(
                target,
                Envelope[Attachment],
                expected_class=SensitivityClass.FINANCIAL,
                master_key_provider=_resolve_master_key_provider(),
                hkdf_context=_HKDF_CONTEXT_ATTACHMENT_MANIFEST,
                max_supported_version=_ATTACHMENT_MANIFEST_VERSION,
            )
        except (ClassificationError, EnvelopeVersionError) as exc:
            raise AttachmentValidationError(f"invalid attachment manifest: {target}") from exc
        except ValidationError as exc:
            raise AttachmentValidationError(f"invalid attachment manifest: {target}") from exc
        except OSError as exc:
            raise AttachmentPersistenceError(f"unable to read attachment manifest: {target}") from exc
        attachment = envelope.payload
        if attachment.attachment_id != digest:
            raise AttachmentValidationError(
                f"manifest filename {digest} does not match stored attachment_id {attachment.attachment_id}"
            )
        return attachment

    def iter_manifests(self) -> Iterator[Attachment]:
        """Iterate over every manifest on disk in sorted-filename order.

        Only filenames matching ``<digest>.envelope.json`` whose digest
        is a valid 64-char lowercase hex digest are yielded; any other
        file under ``manifests/`` is ignored. Each yielded manifest
        additionally satisfies the filename-vs-payload cross-check
        enforced by :meth:`load_manifest`.

        Yields:
            Each validated ``Attachment`` manifest stored under the root.

        Raises:
            AttachmentPersistenceError: When the manifests directory cannot be read.
            AttachmentValidationError: When any manifest fails validation.
        """
        if not self.manifests_dir.exists():
            return
        try:
            entries = sorted(self.manifests_dir.iterdir())
        except OSError as exc:
            raise AttachmentPersistenceError(f"unable to list attachment manifests: {self.manifests_dir}") from exc
        for entry in entries:
            if not entry.is_file():
                continue
            name = entry.name
            if not name.endswith(_MANIFEST_SUFFIX):
                continue
            digest = name[: -len(_MANIFEST_SUFFIX)]
            if len(digest) != 64 or any(char not in _HEX_DIGITS for char in digest):
                _LOGGER.debug("skipping non-digest manifest filename: %s", entry.name)
                continue
            yield self.load_manifest(digest)


def _commit_write_once(tmp_path: Path, target: Path) -> None:
    """Commit ``tmp_path`` as ``target`` while preserving write-once.

    Uses ``os.link`` to atomically publish the blob; if the target already
    exists the existing bytes are preserved and the tempfile is removed. On
    filesystems that do not support hardlinks (FAT, some network shares) the
    code falls back to an ``exists`` check + ``os.replace`` — a best-effort
    degradation that matches the original single-writer contract.

    After a successful publish, the parent directory entry is fsynced
    so the rename / link is durable across power loss (file fsync does
    not imply directory fsync on POSIX).
    """
    from ....adapters.persistence.storage._lock import fsync_parent_dir

    try:
        os.link(tmp_path, target)
    except FileExistsError:
        tmp_path.unlink(missing_ok=True)
        return
    except OSError:
        if target.exists():
            tmp_path.unlink(missing_ok=True)
            return
        os.replace(tmp_path, target)
        fsync_parent_dir(target)
        return
    fsync_parent_dir(target)
    tmp_path.unlink(missing_ok=True)


def _write_once_bytes(target: Path, data: bytes) -> None:
    """Atomically write ``data`` to ``target`` if and only if it does not yet exist."""
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
            handle.write(data)
            handle.flush()
            # fsync the tempfile bytes BEFORE the link/replace so the
            # directory entry never points at an inode whose contents
            # haven't been written through. _commit_write_once handles
            # the parent-dir fsync after publication.
            os.fsync(handle.fileno())
        _commit_write_once(tmp_path, target)
        tmp_path = None
    except OSError:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        raise
