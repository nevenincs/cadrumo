"""Pydantic records for SQL secure object persistence.

Use of :class:`SensitivityClass` for compliance.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from .....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core.classification import SensitivityClass

DEFAULT_WRITE_PROVENANCE = "secure-object-repository"


class SecureObjectRecord(BaseModel):
    """One decrypted sensitive object loaded from the SQL backend."""

    model_config = _STRICT_FROZEN

    namespace: str = Field(min_length=1)
    object_key: bytes
    classification: SensitivityClass
    schema_version: int = Field(ge=1)
    written_at: datetime
    payload: bytes


class SecureObjectMetadata(BaseModel):
    """Row-level metadata for one stored secure object, decryption-free."""

    model_config = _STRICT_FROZEN

    namespace: str = Field(min_length=1)
    classification: str = Field(min_length=1)
    schema_version: int = Field(ge=1)
    written_at: datetime
    byte_length: int = Field(ge=0)


class SecureObjectWrite(BaseModel):
    """One encrypted secure-object upsert prepared for a unit of work."""

    model_config = _STRICT_FROZEN

    namespace: str = Field(min_length=1)
    object_key: str = Field(min_length=1)
    classification: SensitivityClass
    schema_version: int = Field(ge=1)
    written_at: datetime
    payload: bytes = Field(min_length=1)
    write_provenance: str = Field(default=DEFAULT_WRITE_PROVENANCE, min_length=1, max_length=255)
    source_event_id: str | None = Field(default=None, min_length=1, max_length=128)
    expected_revision_id: str | None = Field(default=None, min_length=64, max_length=64)


class SecureObjectDeletion(BaseModel):
    """One secure-object row removal addressed by its raw HMAC digest.

    Deletions are addressed by the stored ``object_key`` digest (the
    :class:`HashedLookup` column value) rather than the natural key, because a
    diff-based writer enumerates the *stored* rows by digest and cannot recover
    their natural keys (those are recoverable only by decrypting each payload).
    The 32-byte digest passes straight through the ``HashedLookup`` column
    comparison without re-hashing, the same convention
    :meth:`SecureObjectRepository.save_with_raw_key` /
    :meth:`exists_by_raw_key` use.
    """

    model_config = _STRICT_FROZEN

    namespace: str = Field(min_length=1)
    hashed_object_key: bytes = Field(min_length=32, max_length=32)


class SecureObjectUnreadable(BaseModel):
    """One stored secure object that cannot be decrypted under the current master key."""

    model_config = _STRICT_FROZEN

    namespace: str = Field(min_length=1)
    row_id: int = Field(ge=0)
    object_key: bytes
    classification: str = Field(min_length=1)
    schema_version: int = Field(ge=1)
    written_at: datetime
    reason: str = Field(min_length=1)


SecureObjectListItem = SecureObjectRecord | SecureObjectUnreadable


class SecureObjectRawRow(BaseModel):
    """One stored row surfaced without classification / version validation or decryption."""

    model_config = _STRICT_FROZEN

    row_id: int = Field(ge=0)
    namespace: str = Field(min_length=1)
    object_key: bytes
    classification: str = Field(min_length=1)
    schema_version: int = Field(ge=1)
    written_at: datetime
    payload: bytes
    revision_id: str | None = Field(default=None, min_length=64, max_length=64)
    previous_revision_id: str | None = Field(default=None, min_length=64, max_length=64)
    revision_ancestor_ids: tuple[str, ...] = ()
    previous_payload_hash: str | None = Field(default=None, min_length=64, max_length=64)
    payload_hash: str | None = Field(default=None, min_length=64, max_length=64)
    ciphertext_hash: str | None = Field(default=None, min_length=64, max_length=64)
    revision_written_at: datetime | None = None


class SecureObjectNamespaceIntegrity(BaseModel):
    """Per-namespace decryptability counts for the integrity diagnostic."""

    model_config = _STRICT_FROZEN

    namespace: str = Field(min_length=1)
    readable: int = Field(ge=0)
    unreadable: int = Field(ge=0)


class SecureObjectDecryptabilityRow(BaseModel):
    """Row-level decryptability metadata without plaintext payload disclosure."""

    model_config = _STRICT_FROZEN

    namespace: str = Field(min_length=1)
    row_id: int = Field(ge=0)
    object_key: bytes
    classification: str = Field(min_length=1)
    schema_version: int = Field(ge=1)
    written_at: datetime
    readable: bool
    reason: str | None = None
