"""Encrypted SQL-backed content-addressed attachment store implementation.

Concrete adapter-layer implementation of the
:class:`~aeat.domain.attachments._repository.AttachmentStoreProtocol`. The
domain declares the protocol; this module provides the implementation that
reads/writes encrypted attachment blobs and manifests through the secure-
object persistence substrate.

Sensitivity rationale: attachment blobs and manifests are content-addressed
byte objects (invoice PDFs, bank statements, supporting documents) that are
FINANCIAL regardless of the modelo that triggered the upload. Attachments are
not modelo-scoped — a single blob may be referenced from multiple modelos and
filing revisions. The ``ModeloDefinition.output_sensitivity`` field governs
model *output* artefacts; attachment storage is an independent content-
addressed substrate and its sensitivity class is irreducibly FINANCIAL.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ....core.classification import SensitivityClass
from ....core.logging import get_logger
from ....domain.attachments._errors import (
    AttachmentNotFoundError,
    AttachmentPersistenceError,
    AttachmentValidationError,
)
from ....domain.attachments._models import Attachment
from .envelope import Envelope
from .errors import ClassificationError, EnvelopeVersionError
from .runtime_repository import secure_object_repository_for_active_bucket
from .sql import SecureObjectRepository

_LOGGER = get_logger(__name__)

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")
_STREAM_CHUNK_SIZE = 1024 * 1024
_HEX_DIGITS = frozenset("0123456789abcdef")
_ATTACHMENT_BLOB_VERSION = 1
_ATTACHMENT_MANIFEST_VERSION = 1
_ATTACHMENT_BLOB_NAMESPACE = "aeat.domain.attachments.blobs"
_ATTACHMENT_MANIFEST_NAMESPACE = "aeat.domain.attachments.manifests"


def _require_digest(value: str, *, field_name: str = "attachment_id") -> str:
    """Reject any digest input that is not a 64-char lowercase hex string."""

    if not isinstance(value, str):
        raise AttachmentValidationError(f"{field_name} must be a 64-character lowercase hex digest")
    if len(value) != 64 or any(char not in _HEX_DIGITS for char in value):
        raise AttachmentValidationError(f"{field_name} must be a 64-character lowercase hex digest")
    return value


class AttachmentStore(BaseModel):
    """Encrypted SQL-backed content-addressed attachment store.

    Implements :class:`~aeat.domain.attachments._repository.AttachmentStoreProtocol`.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", arbitrary_types_allowed=True)

    objects: SecureObjectRepository | None = Field(default=None, exclude=True, repr=False)

    def _objects_repo(self) -> SecureObjectRepository:
        return self.objects or secure_object_repository_for_active_bucket()

    @property
    def blobs_dir(self) -> Path:
        """Return the logical byte-object namespace marker."""

        return Path("db://secure_objects") / _ATTACHMENT_BLOB_NAMESPACE

    @property
    def manifests_dir(self) -> Path:
        """Return the logical manifest-object namespace marker."""

        return Path("db://secure_objects") / _ATTACHMENT_MANIFEST_NAMESPACE

    def blob_path(self, sha256: str) -> Path:
        """Return a logical object marker for ``sha256``."""

        return self.blobs_dir / _require_digest(sha256, field_name="sha256")

    def manifest_path(self, attachment_id: str) -> Path:
        """Return a logical object marker for ``attachment_id``."""

        return self.manifests_dir / _require_digest(attachment_id)

    def _manifest_lock_target(self, attachment_id: str) -> Path:
        """Return a logical lock marker; SQL transactions govern writes."""

        return self.manifest_path(attachment_id).with_suffix(".lock")

    def put_bytes(self, data: bytes) -> str:
        """Write ``data`` under its SHA-256 digest if not already present."""

        digest = hashlib.sha256(data).hexdigest()
        objects = self._objects_repo()
        if objects.exists(_ATTACHMENT_BLOB_NAMESPACE, digest):
            _LOGGER.debug("reusing existing attachment object for %s", digest)
            return digest
        objects.save(
            namespace=_ATTACHMENT_BLOB_NAMESPACE,
            object_key=digest,
            # rationale: blob sensitivity is FINANCIAL regardless of modelo; see module docstring.
            classification=SensitivityClass.FINANCIAL,
            schema_version=_ATTACHMENT_BLOB_VERSION,
            written_at=datetime.now(UTC),
            payload=data,
        )
        _LOGGER.debug("stored attachment object %s (%d bytes)", digest, len(data))
        return digest

    def put_file(self, source: Path) -> tuple[str, int]:
        """Read ``source`` into the encrypted object backend."""

        hasher = hashlib.sha256()
        chunks: list[bytes] = []
        bytes_size = 0
        try:
            with source.open("rb") as reader:
                while True:
                    chunk = reader.read(_STREAM_CHUNK_SIZE)
                    if not chunk:
                        break
                    hasher.update(chunk)
                    bytes_size += len(chunk)
                    chunks.append(chunk)
        except OSError as exc:
            raise AttachmentPersistenceError(f"unable to read attachment source: {source}") from exc
        digest = hasher.hexdigest()
        self._objects_repo().save(
            namespace=_ATTACHMENT_BLOB_NAMESPACE,
            object_key=digest,
            # rationale: blob sensitivity is FINANCIAL regardless of modelo; see module docstring.
            classification=SensitivityClass.FINANCIAL,
            schema_version=_ATTACHMENT_BLOB_VERSION,
            written_at=datetime.now(UTC),
            payload=b"".join(chunks),
        )
        _LOGGER.debug("stored attachment object %s (%d bytes)", digest, bytes_size)
        return digest, bytes_size

    def read_bytes(self, sha256: str) -> bytes:
        """Return the raw bytes for ``sha256``."""

        digest = _require_digest(sha256, field_name="sha256")
        record = self._objects_repo().load(
            _ATTACHMENT_BLOB_NAMESPACE,
            digest,
            # rationale: blob sensitivity is FINANCIAL regardless of modelo; see module docstring.
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_ATTACHMENT_BLOB_VERSION,
        )
        if record is None:
            raise AttachmentNotFoundError(f"attachment blob not found: {digest}")
        return record.payload

    def open_bytes(self, sha256: str) -> BinaryIO:
        """Open the blob for ``sha256`` as a streaming binary handle."""

        return BytesIO(self.read_bytes(sha256))

    def verify_blob(self, attachment_id: str) -> None:
        """Re-hash the stored blob and verify it matches ``attachment_id``."""

        digest = _require_digest(attachment_id)
        actual = hashlib.sha256(self.read_bytes(digest)).hexdigest()
        if actual != digest:
            raise AttachmentValidationError(f"blob digest drift for {digest}: stored sha256 is {actual}")

    def write_manifest(self, attachment: Attachment) -> None:
        """Persist ``attachment`` as an encrypted database object."""

        # rationale: manifest sensitivity is FINANCIAL regardless of modelo; see module docstring.
        envelope = Envelope[Attachment](
            schema_version=_ATTACHMENT_MANIFEST_VERSION,
            written_at=datetime.now(UTC),
            classification=SensitivityClass.FINANCIAL,
            payload=attachment,
        )
        self._objects_repo().save(
            namespace=_ATTACHMENT_MANIFEST_NAMESPACE,
            object_key=attachment.attachment_id,
            classification=SensitivityClass.FINANCIAL,
            schema_version=_ATTACHMENT_MANIFEST_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )
        _LOGGER.debug("wrote attachment manifest %s", attachment.attachment_id)

    def load_manifest(self, attachment_id: str) -> Attachment:
        """Load and validate the manifest for ``attachment_id``."""

        digest = _require_digest(attachment_id)
        record = self._objects_repo().load(
            _ATTACHMENT_MANIFEST_NAMESPACE,
            digest,
            # rationale: manifest sensitivity is FINANCIAL regardless of modelo; see module docstring.
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_ATTACHMENT_MANIFEST_VERSION,
        )
        if record is None:
            raise AttachmentNotFoundError(f"attachment manifest not found: {digest}")
        try:
            envelope = Envelope[Attachment].model_validate_json(record.payload.decode("utf-8"))
        except (ClassificationError, EnvelopeVersionError) as exc:
            raise AttachmentValidationError(f"invalid attachment manifest: {digest}") from exc
        except ValidationError as exc:
            raise AttachmentValidationError(f"invalid attachment manifest: {digest}") from exc
        attachment = envelope.payload
        if attachment.attachment_id != digest:
            raise AttachmentValidationError(
                f"manifest key {digest} does not match stored attachment_id {attachment.attachment_id}"
            )
        return attachment

    def iter_manifests(self) -> Iterator[Attachment]:
        """Iterate over every manifest in sorted attachment-id order."""

        manifests: list[Attachment] = []
        for record in self._objects_repo().list_records(
            _ATTACHMENT_MANIFEST_NAMESPACE,
            # rationale: manifest sensitivity is FINANCIAL regardless of modelo; see module docstring.
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_ATTACHMENT_MANIFEST_VERSION,
        ):
            try:
                envelope = Envelope[Attachment].model_validate_json(record.payload.decode("utf-8"))
            except ValidationError as exc:
                raise AttachmentValidationError("invalid attachment manifest") from exc
            manifests.append(envelope.payload)
        yield from sorted(manifests, key=lambda attachment: attachment.attachment_id)


__all__ = ["AttachmentStore"]
