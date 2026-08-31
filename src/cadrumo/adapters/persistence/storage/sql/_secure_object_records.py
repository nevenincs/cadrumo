"""Pydantic records for SQL secure object persistence.

Secure object read/write records carry
:class:`~adapters.persistence.storage.SensitivityClass` so repository
policy can enforce the expected storage classification.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, NonNegativeInt

from .....core.classification.policies import SensitivityClass
from .....core.identity import ContentDigest
from .....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN

# Every digest-shaped column below is written by ``core.hashing.sha256_hex``
# (directly, or via ``derive_revision_id``), so the canonical
# :data:`~core.identity.ContentDigest` alias is the shape they already carry.
# A length-only constraint additionally admitted uppercase and non-hex
# 64-character strings, which the canonical alias refuses.


class SecureObjectRecord(BaseModel):
    """One decrypted sensitive object loaded from the SQL backend."""

    model_config = _STRICT_FROZEN

    namespace: str = Field(min_length=1)
    object_key: bytes
    classification: SensitivityClass
    schema_version: int = Field(ge=1)
    written_at: datetime
    payload: bytes
    revision_id: ContentDigest


class SecureObjectMetadata(BaseModel):
    """Row-level metadata for one stored secure object, decryption-free."""

    model_config = _STRICT_FROZEN

    namespace: str = Field(min_length=1)
    classification: str = Field(min_length=1)
    schema_version: int = Field(ge=1)
    written_at: datetime
    byte_length: NonNegativeInt


class SecureObjectDeletion(BaseModel):
    """One secure-object row removal addressed by its raw HMAC digest.

    Deletions are addressed by the stored ``object_key`` digest (the
    :class:`~adapters.persistence.storage.HashedLookup` column value)
    rather than the natural key, because a diff-based writer enumerates the
    *stored* rows by digest and cannot recover their natural keys (those are
    recoverable only by decrypting each payload). The 32-byte digest passes
    straight through the ``HashedLookup`` column comparison without re-hashing,
    the same convention
    :meth:`~adapters.persistence.storage.SecureObjectRepository.save_with_raw_key`
    and
    :meth:`~adapters.persistence.storage.SecureObjectRepository.exists_by_raw_key`
    use.
    """

    model_config = _STRICT_FROZEN

    namespace: str = Field(min_length=1)
    hashed_object_key: bytes = Field(min_length=32, max_length=32)


class SecureObjectUnreadable(BaseModel):
    """One stored secure object that cannot be decrypted under the current master key."""

    model_config = _STRICT_FROZEN

    namespace: str = Field(min_length=1)
    row_id: NonNegativeInt
    object_key: bytes
    classification: str = Field(min_length=1)
    schema_version: int = Field(ge=1)
    written_at: datetime
    reason: str = Field(min_length=1)


# Shared readable/unreadable outcome for namespace scans and targeted batch reads.
SecureObjectBatchLoadItem = SecureObjectRecord | SecureObjectUnreadable
SecureObjectListItem = SecureObjectBatchLoadItem


class SecureObjectRawRow(BaseModel):
    """One stored row surfaced without classification / version validation or decryption."""

    model_config = _STRICT_FROZEN

    row_id: NonNegativeInt
    namespace: str = Field(min_length=1)
    object_key: bytes
    classification: str = Field(min_length=1)
    schema_version: int = Field(ge=1)
    written_at: datetime
    payload: bytes
    revision_id: ContentDigest | None = None
    previous_revision_id: ContentDigest | None = None
    revision_ancestor_ids: tuple[ContentDigest, ...] = ()
    previous_payload_hash: ContentDigest | None = None
    payload_hash: ContentDigest | None = None
    ciphertext_hash: ContentDigest | None = None
    revision_written_at: datetime | None = None
    write_provenance: str | None = None
    source_event_id: str | None = None


class SecureObjectNamespaceIntegrity(BaseModel):
    """Per-namespace decryptability counts for the integrity diagnostic."""

    model_config = _STRICT_FROZEN

    namespace: str = Field(min_length=1)
    readable: NonNegativeInt
    unreadable: NonNegativeInt


class SecureObjectDecryptabilityRow(BaseModel):
    """Row-level decryptability metadata without plaintext payload disclosure."""

    model_config = _STRICT_FROZEN

    namespace: str = Field(min_length=1)
    row_id: NonNegativeInt
    object_key: bytes
    classification: str = Field(min_length=1)
    schema_version: int = Field(ge=1)
    written_at: datetime
    readable: bool
    reason: str | None = None
