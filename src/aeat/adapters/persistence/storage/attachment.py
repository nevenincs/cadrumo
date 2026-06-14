"""Encrypted SQL-backed content-addressed attachment store implementation.

Concrete adapter-layer implementation of the
:class:`~aeat.domain.attachments._protocols.AttachmentStoreProtocol`. The
domain declares the protocol; this module provides the implementation that
reads/writes encrypted attachment blobs and manifests wrapped in
:class:`Envelope` records through the :class:`SecureObjectRepository`
persistence substrate.

Sensitivity rationale: attachment blobs and manifests are content-addressed
byte objects (invoice PDFs, bank statements, supporting documents) that are
FINANCIAL regardless of the modelo that triggered the upload. Attachments are
not modelo-scoped - a single blob may be referenced from multiple modelos and
filing revisions. The ``ModeloDefinition.output_sensitivity`` field governs
model *output* artefacts; attachment storage is an independent content-
addressed substrate and its sensitivity class is irreducibly FINANCIAL.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ....core.external_constants import UTF_8_ENCODING
from ....core.logging import get_logger
from ....core.time import now
from ....domain.attachments._errors import (
    AttachmentNotFoundError,
    AttachmentPersistenceError,
    AttachmentValidationError,
)
from ....domain.attachments._models import Attachment, is_link_only_mime_type
from ._namespace_registry import (
    ATTACHMENT_BLOB_NAMESPACE as ATTACHMENT_BLOB_STORAGE_NAMESPACE,
)
from ._namespace_registry import (
    ATTACHMENT_MANIFEST_NAMESPACE as ATTACHMENT_MANIFEST_STORAGE_NAMESPACE,
)
from ._namespace_registry import secure_object_namespace_logical_path
from .envelope import Envelope
from .runtime_repository import secure_object_repository_for_active_bucket
from .sql import SecureObjectRepository

_LOGGER = get_logger(__name__)

_STREAM_CHUNK_SIZE = 1024 * 1024
_HEX_DIGITS = frozenset("0123456789abcdef")
_ATTACHMENT_BLOB_VERSION = ATTACHMENT_BLOB_STORAGE_NAMESPACE.schema_version
_ATTACHMENT_BLOB_SENSITIVITY = ATTACHMENT_BLOB_STORAGE_NAMESPACE.sensitivity
_ATTACHMENT_MANIFEST_VERSION = ATTACHMENT_MANIFEST_STORAGE_NAMESPACE.schema_version
_ATTACHMENT_MANIFEST_SENSITIVITY = ATTACHMENT_MANIFEST_STORAGE_NAMESPACE.sensitivity
_ATTACHMENT_BLOB_NAMESPACE = ATTACHMENT_BLOB_STORAGE_NAMESPACE.namespace
_ATTACHMENT_MANIFEST_NAMESPACE = ATTACHMENT_MANIFEST_STORAGE_NAMESPACE.namespace
_ATTACHMENT_ERROR_CONTEXT = {"surface": "attachment_store"}


def _attachment_validation_error(message: str, *, violation: str) -> AttachmentValidationError:
    return AttachmentValidationError(
        message,
        context={**_ATTACHMENT_ERROR_CONTEXT, "violation": violation},
        translated_message="errors.integrity.integrity_financial_attachments_attachment_validation",
    )


def _attachment_not_found_error(message: str, *, object_kind: str) -> AttachmentNotFoundError:
    return AttachmentNotFoundError(
        message,
        context={**_ATTACHMENT_ERROR_CONTEXT, "object_kind": object_kind},
        translated_message="errors.error.error_financial_attachments_attachment_not_found",
    )


def _attachment_persistence_error(message: str, *, operation: str) -> AttachmentPersistenceError:
    return AttachmentPersistenceError(
        message,
        context={**_ATTACHMENT_ERROR_CONTEXT, "operation": operation},
        translated_message="errors.fail.fail_financial_attachments_attachment_persistence",
    )


def _validate_manifest_envelope(envelope: Envelope[Attachment]) -> None:
    if envelope.classification != _ATTACHMENT_MANIFEST_SENSITIVITY:
        raise _attachment_validation_error(
            "invalid attachment manifest",
            violation="manifest_classification",
        )
    if envelope.schema_version != _ATTACHMENT_MANIFEST_VERSION:
        raise _attachment_validation_error(
            "invalid attachment manifest",
            violation="manifest_schema_version",
        )


def _decode_manifest_envelope(payload: bytes, *, attachment_id: str | None = None) -> Envelope[Attachment]:
    try:
        payload_dict = json.loads(payload.decode(UTF_8_ENCODING))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _attachment_validation_error("invalid attachment manifest", violation="manifest_payload") from exc
    if not isinstance(payload_dict, dict):
        raise _attachment_validation_error("invalid attachment manifest", violation="manifest_payload")
    manifest_payload = payload_dict.get("payload")
    if not isinstance(manifest_payload, dict):
        raise _attachment_validation_error("invalid attachment manifest", violation="manifest_payload")
    if attachment_id is None:
        manifest_sha256 = manifest_payload.get("sha256")
        if not isinstance(manifest_sha256, str):
            raise _attachment_validation_error("invalid attachment manifest", violation="manifest_payload")
        attachment_id = _require_digest(manifest_sha256, field_name="sha256")
    manifest_payload["attachment_id"] = attachment_id
    try:
        envelope_json = json.dumps(payload_dict)
        envelope = Envelope[Attachment].model_validate_json(envelope_json)
    except ValidationError as exc:
        raise _attachment_validation_error("invalid attachment manifest", violation="manifest_payload") from exc
    _validate_manifest_envelope(envelope)
    return envelope


# Content-addressed blob payloads are the operator's raw bytes (a PDF, a bank
# statement). The secure-object integrity column ``payload_hash`` is
# ``sha256(plaintext payload)`` (high-entropy and unguessable for the JSON
# envelopes every other namespace stores), but for a bare-content blob the
# plaintext IS the content, so ``payload_hash`` would equal the content digest
# (== the attachment id) and a DB-read attacker holding a copy of a document
# could confirm its presence by computing its sha256. Framing the stored blob
# behind a fixed envelope prefix makes ``payload_hash`` hash the prefixed bytes
# instead, so the bare content digest never lands in a plaintext column. The
# object key stays HMAC-digested and the payload stays encrypted; this only
# removes the residual content-digest oracle.
_ATTACHMENT_BLOB_ENVELOPE_PREFIX = b"\x00aeat-attachment-blob-envelope-v1\x00"


def _wrap_blob_payload(data: bytes) -> bytes:
    """Frame raw blob bytes so the stored ``payload_hash`` is not the content digest."""
    return _ATTACHMENT_BLOB_ENVELOPE_PREFIX + data


def _unwrap_blob_payload(stored: bytes) -> bytes:
    """Strip the envelope prefix from a stored blob; refuse an un-enveloped payload.

    Every blob is wrapped by :func:`_wrap_blob_payload` at write time, so a
    missing prefix can only mean corruption — never legacy data. Refuse it
    rather than returning unframed bytes.
    """
    if not stored.startswith(_ATTACHMENT_BLOB_ENVELOPE_PREFIX):
        raise _attachment_validation_error(
            "attachment blob payload is missing its envelope prefix",
            violation="blob_envelope_prefix",
        )
    return stored[len(_ATTACHMENT_BLOB_ENVELOPE_PREFIX) :]


def _require_digest(value: str, *, field_name: str = "attachment_id") -> str:
    """Reject any digest input that is not a 64-char lowercase hex string."""
    if not isinstance(value, str):
        raise _attachment_validation_error(
            f"{field_name} must be a 64-character lowercase hex digest",
            violation=f"{field_name}_invalid_digest",
        )
    if len(value) != 64 or any(char not in _HEX_DIGITS for char in value):
        raise _attachment_validation_error(
            f"{field_name} must be a 64-character lowercase hex digest",
            violation=f"{field_name}_invalid_digest",
        )
    return value


class AttachmentStore(BaseModel):
    """Encrypted SQL-backed content-addressed attachment store.

    Implements :class:`~aeat.domain.attachments._protocols.AttachmentStoreProtocol`.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", arbitrary_types_allowed=True)

    objects: SecureObjectRepository | None = Field(default=None, exclude=True, repr=False)

    def _objects_repo(self) -> SecureObjectRepository:
        return self.objects or secure_object_repository_for_active_bucket()

    @property
    def blobs_dir(self) -> Path:
        """Return the logical byte-object namespace marker."""
        return secure_object_namespace_logical_path(_ATTACHMENT_BLOB_NAMESPACE)

    @property
    def manifests_dir(self) -> Path:
        """Return the logical manifest-object namespace marker."""
        return secure_object_namespace_logical_path(_ATTACHMENT_MANIFEST_NAMESPACE)

    def manifest_path(self, attachment_id: str) -> Path:
        """Return a logical object marker for ``attachment_id``."""
        return self.manifests_dir / _require_digest(attachment_id)

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
            classification=_ATTACHMENT_BLOB_SENSITIVITY,
            schema_version=_ATTACHMENT_BLOB_VERSION,
            written_at=now(),
            payload=_wrap_blob_payload(data),
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
            _LOGGER.debug("attachment source read failed error_type=%s", type(exc).__name__)
            raise _attachment_persistence_error("unable to read attachment source", operation="read_source") from exc
        digest = hasher.hexdigest()
        self._objects_repo().save(
            namespace=_ATTACHMENT_BLOB_NAMESPACE,
            object_key=digest,
            # rationale: blob sensitivity is FINANCIAL regardless of modelo; see module docstring.
            classification=_ATTACHMENT_BLOB_SENSITIVITY,
            schema_version=_ATTACHMENT_BLOB_VERSION,
            written_at=now(),
            payload=_wrap_blob_payload(b"".join(chunks)),
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
            expected_class=_ATTACHMENT_BLOB_SENSITIVITY,
            max_supported_version=_ATTACHMENT_BLOB_VERSION,
        )
        if record is None:
            raise _attachment_not_found_error("attachment blob not found", object_kind="blob")
        return _unwrap_blob_payload(record.payload)

    def open_bytes(self, sha256: str) -> BinaryIO:
        """Open the blob for ``sha256`` as a streaming binary handle."""
        return BytesIO(self.read_bytes(sha256))

    def verify_blob(self, attachment_id: str) -> None:
        """Re-hash the stored blob and verify it matches ``attachment_id``."""
        digest = _require_digest(attachment_id)
        actual = hashlib.sha256(self.read_bytes(digest)).hexdigest()
        if actual != digest:
            raise _attachment_validation_error("blob digest drift", violation="blob_digest_drift")

    def write_manifest(self, attachment: Attachment) -> None:
        """Persist ``attachment`` as an encrypted database object."""
        if is_link_only_mime_type(attachment.mime_type):
            raise _attachment_validation_error(
                "attachment manifest must carry document bytes, not a link-only URI list",
                violation="manifest_link_only_mime_type",
            )
        # rationale: manifest sensitivity is FINANCIAL regardless of modelo; see module docstring.
        envelope = Envelope[Attachment](
            schema_version=_ATTACHMENT_MANIFEST_VERSION,
            written_at=now(),
            classification=_ATTACHMENT_MANIFEST_SENSITIVITY,
            payload=attachment,
        )
        envelope_dict = json.loads(envelope.model_dump_json())
        del envelope_dict["payload"]["attachment_id"]
        payload_json = json.dumps(envelope_dict)
        self._objects_repo().save(
            namespace=_ATTACHMENT_MANIFEST_NAMESPACE,
            object_key=attachment.attachment_id,
            # rationale: manifest sensitivity is FINANCIAL regardless of modelo; see module docstring.
            classification=_ATTACHMENT_MANIFEST_SENSITIVITY,
            schema_version=_ATTACHMENT_MANIFEST_VERSION,
            written_at=envelope.written_at,
            payload=payload_json.encode(UTF_8_ENCODING),
        )
        _LOGGER.debug("wrote attachment manifest %s", attachment.attachment_id)

    def load_manifest(self, attachment_id: str) -> Attachment:
        """Load and validate the :class:`Attachment` manifest for ``attachment_id``."""
        digest = _require_digest(attachment_id)
        record = self._objects_repo().load(
            _ATTACHMENT_MANIFEST_NAMESPACE,
            digest,
            # rationale: manifest sensitivity is FINANCIAL regardless of modelo; see module docstring.
            expected_class=_ATTACHMENT_MANIFEST_SENSITIVITY,
            max_supported_version=_ATTACHMENT_MANIFEST_VERSION,
        )
        if record is None:
            raise _attachment_not_found_error("attachment manifest not found", object_kind="manifest")
        envelope = _decode_manifest_envelope(record.payload, attachment_id=digest)
        attachment = envelope.payload
        if attachment.attachment_id != digest:
            raise _attachment_validation_error(
                "manifest key does not match stored attachment_id",
                violation="manifest_key",
            )
        return attachment

    def iter_manifests(self) -> Iterator[Attachment]:
        """Iterate over every :class:`Attachment` manifest in sorted attachment-id order."""
        manifests: list[Attachment] = []
        for record in self._objects_repo().list_records(
            _ATTACHMENT_MANIFEST_NAMESPACE,
            # rationale: manifest sensitivity is FINANCIAL regardless of modelo; see module docstring.
            expected_class=_ATTACHMENT_MANIFEST_SENSITIVITY,
            max_supported_version=_ATTACHMENT_MANIFEST_VERSION,
        ):
            envelope = _decode_manifest_envelope(record.payload)
            manifests.append(envelope.payload)
        yield from sorted(manifests, key=lambda attachment: attachment.attachment_id)


__all__ = ["AttachmentStore"]
