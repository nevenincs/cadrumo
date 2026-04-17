"""Content-addressed byte and manifest store for the attachment service.

The store separates write-once byte blobs from mutable JSON manifests under a
shared configured root:

* ``<root>/blobs/<sha256>``      — raw bytes, write-once.
* ``<root>/manifests/<sha256>.json`` — JSON manifest, rewritten as links evolve.

Reads of blobs return ``bytes`` directly; the ``bytes`` type is itself a
structural read-only sequence, which satisfies the ``BytesView`` Protocol
shape required by issue #76 without introducing a dedicated wrapper.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from aeat.logging import get_logger

from ._errors import AttachmentNotFoundError, AttachmentPersistenceError, AttachmentValidationError
from ._models import Attachment

_LOGGER = get_logger(__name__)

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")
_BLOBS_DIRNAME = "blobs"
_MANIFESTS_DIRNAME = "manifests"
_MANIFEST_SUFFIX = ".json"
_STREAM_CHUNK_SIZE = 1024 * 1024  # 1 MiB


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
        """Return the on-disk blob path for ``sha256``."""
        return self.blobs_dir / sha256

    def manifest_path(self, attachment_id: str) -> Path:
        """Return the on-disk manifest path for ``attachment_id``."""
        return self.manifests_dir / f"{attachment_id}{_MANIFEST_SUFFIX}"

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
            _atomic_write_bytes(target, data)
        except OSError as exc:
            raise AttachmentPersistenceError(f"unable to write attachment blob: {target}") from exc
        _LOGGER.info("stored attachment blob %s (%d bytes)", digest, len(data))
        return digest

    def put_file(self, source: Path) -> tuple[str, int]:
        """Stream ``source`` into the store, hashing and writing in chunks.

        Reads and writes happen in 1 MiB chunks so large attachments (scans,
        multi-page invoices) never force the full payload into memory. If a
        blob for the resulting digest already exists the streamed tempfile is
        discarded to preserve the write-once invariant.

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
            digest = hasher.hexdigest()
            target = self.blob_path(digest)
            if target.exists():
                tmp_path.unlink(missing_ok=True)
                _LOGGER.debug("reusing existing blob for %s", digest)
            else:
                os.replace(tmp_path, target)
                _LOGGER.info("stored attachment blob %s (%d bytes)", digest, bytes_size)
            return digest, bytes_size
        except OSError as exc:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)
            raise AttachmentPersistenceError(f"unable to stream attachment source: {source}") from exc

    def read_bytes(self, sha256: str) -> bytes:
        """Return the raw bytes for ``sha256``.

        Args:
            sha256: 64-character lowercase hex digest of the blob to read.

        Returns:
            The raw attachment bytes.

        Raises:
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

    def write_manifest(self, attachment: Attachment) -> None:
        """Persist ``attachment`` to its manifest file atomically.

        Args:
            attachment: Validated attachment whose manifest should be written.

        Raises:
            AttachmentPersistenceError: When the manifest cannot be written.
        """
        target = self.manifest_path(attachment.attachment_id)
        try:
            self.manifests_dir.mkdir(parents=True, exist_ok=True)
            _atomic_write_text(target, attachment.model_dump_json(indent=2))
        except OSError as exc:
            raise AttachmentPersistenceError(f"unable to write attachment manifest: {target}") from exc
        _LOGGER.info("wrote attachment manifest %s", attachment.attachment_id)

    def load_manifest(self, attachment_id: str) -> Attachment:
        """Load and validate the manifest for ``attachment_id``.

        Args:
            attachment_id: Stable attachment identifier (SHA-256 hex digest).

        Returns:
            The validated attachment manifest.

        Raises:
            AttachmentNotFoundError: When no manifest exists.
            AttachmentPersistenceError: When the manifest cannot be read.
            AttachmentValidationError: When the manifest fails validation.
        """
        target = self.manifest_path(attachment_id)
        if not target.exists():
            raise AttachmentNotFoundError(f"attachment manifest not found: {attachment_id}")
        try:
            raw = target.read_text(encoding="utf-8")
        except OSError as exc:
            raise AttachmentPersistenceError(f"unable to read attachment manifest: {target}") from exc
        try:
            return Attachment.model_validate_json(raw)
        except ValidationError as exc:
            raise AttachmentValidationError(f"invalid attachment manifest: {target}") from exc

    def iter_manifests(self) -> Iterator[Attachment]:
        """Iterate over every manifest on disk in sorted-filename order.

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
            if entry.suffix != _MANIFEST_SUFFIX or not entry.is_file():
                continue
            attachment_id = entry.stem
            yield self.load_manifest(attachment_id)


def _atomic_write_bytes(target: Path, data: bytes) -> None:
    """Atomically write ``data`` to ``target`` via a sibling tempfile."""
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
        os.replace(tmp_path, target)
    except OSError:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        raise


def _atomic_write_text(target: Path, payload: str) -> None:
    """Atomically write ``payload`` (UTF-8) to ``target`` via a sibling tempfile."""
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f"{target.stem}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            tmp_path = Path(handle.name)
            handle.write(payload)
        os.replace(tmp_path, target)
    except OSError:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        raise
