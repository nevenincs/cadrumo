"""Pydantic records and enums for the storage provider abstraction.

Provider records anchor the storage boundary:

- `ProviderKind` — closed enum naming the v1 backends.
- `ProviderObjectMetadata` — per-object metadata returned by listing /
  fetching operations. Carries the object key HMAC, namespace, byte
  size, content hash, and backend-native identifier.
- `ProviderProbeReport` — health-probe result. Reports whether the
  backend is reachable, writable, and (when applicable) bound to the
  expected root folder. The `read_only` field surfaces whether the
  probe ran in read-only mode (no sentinel-write round-trip).
- `RemoteMirror*` records — immutable manifest and inspection records
  for remote ciphertext mirror reconciliation.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field

from ....core import STRICT_FROZEN_CONFIG

_OBJECT_KEY_HMAC_LENGTH = 64
_CIPHERTEXT_HASH_LENGTH = 64
_STORAGE_REVISION_ID_LENGTH = 64

_ObjectKeyHmac = Annotated[
    str,
    Field(min_length=_OBJECT_KEY_HMAC_LENGTH, max_length=_OBJECT_KEY_HMAC_LENGTH),
]
_CiphertextHash = Annotated[
    str,
    Field(min_length=_CIPHERTEXT_HASH_LENGTH, max_length=_CIPHERTEXT_HASH_LENGTH),
]
_StorageRevisionId = Annotated[
    str,
    Field(min_length=_STORAGE_REVISION_ID_LENGTH, max_length=_STORAGE_REVISION_ID_LENGTH),
]


class ProviderKind(StrEnum):
    """Closed enumeration of supported storage backends."""

    LOCAL_FILESYSTEM = "local_filesystem"
    GOOGLE_DRIVE = "google_drive"


class RemoteMirrorIssueKind(StrEnum):
    """Remote ciphertext mirror degradation classes."""

    PARTIAL_UPLOAD = "partial_upload"
    PARTIAL_DOWNLOAD = "partial_download"
    STALE_MIRROR = "stale_mirror"
    REVISION_CONFLICT = "revision_conflict"


class ProviderObjectMetadata(BaseModel):
    """Per-object metadata returned by the storage provider listing API.

    `provider_object_id` is the backend-native identifier (a filesystem
    path for `LocalFileSystemProvider`, a Drive `fileId` for
    `GoogleDriveProvider`). The coordinator threads it through
    subsequent get/delete/patch calls without re-resolving by name.
    """

    model_config = STRICT_FROZEN_CONFIG

    namespace: str = Field(min_length=1)
    object_key_hmac: str = Field(min_length=1)
    provider_object_id: str = Field(min_length=1)
    byte_length: int = Field(ge=0)
    content_hash: str = Field(min_length=1)
    written_at: datetime


class ProviderProbeReport(BaseModel):
    """Result of a `probe()` health check against a storage backend.

    `reachable` is True iff the backend endpoint responds at all.
    `writable` is True iff a sentinel payload write/delete succeeded;
    inherently False when the probe runs in read-only mode.
    `root_folder_present` is non-None only when the backend supports
    the notion of an operator-configured root folder (currently
    Google Drive).
    """

    model_config = STRICT_FROZEN_CONFIG

    provider_kind: ProviderKind
    reachable: bool
    writable: bool
    read_only: bool
    root_folder_present: bool | None = None
    detail: str = ""


class RemoteMirrorObjectManifest(BaseModel):
    """One ciphertext object entry recorded in a remote mirror manifest."""

    model_config = STRICT_FROZEN_CONFIG

    namespace: str = Field(min_length=1)
    object_key_hmac: _ObjectKeyHmac
    classification: str = Field(min_length=1)
    schema_version: int = Field(ge=1)
    byte_length: int = Field(ge=0)
    ciphertext_hash: _CiphertextHash
    storage_revision_id: _StorageRevisionId | None = None
    previous_storage_revision_id: _StorageRevisionId | None = None
    revision_ancestor_ids: tuple[_StorageRevisionId, ...] = ()
    row_written_at: datetime
    revision_written_at: datetime | None = None


class RemoteMirrorNamespaceManifest(BaseModel):
    """Manifest persisted beside remote ciphertext objects for one namespace."""

    model_config = STRICT_FROZEN_CONFIG

    manifest_schema_version: int = Field(default=1, ge=1)
    namespace: str = Field(min_length=1)
    object_count: int = Field(ge=0)
    latest_revision_id: _StorageRevisionId | None = None
    latest_revision_written_at: datetime | None = None
    objects: tuple[RemoteMirrorObjectManifest, ...]


class RemoteMirrorIssue(BaseModel):
    """One detected remote mirror degradation."""

    model_config = STRICT_FROZEN_CONFIG

    kind: RemoteMirrorIssueKind
    namespace: str = Field(min_length=1)
    object_key_hmac: _ObjectKeyHmac | None = None
    detail: str = Field(min_length=1)


class RemoteMirrorInspection(BaseModel):
    """Typed result of comparing or probing a remote mirror namespace."""

    model_config = STRICT_FROZEN_CONFIG

    namespace: str = Field(min_length=1)
    issues: tuple[RemoteMirrorIssue, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.issues


__all__ = [
    "ProviderKind",
    "ProviderObjectMetadata",
    "ProviderProbeReport",
    "RemoteMirrorInspection",
    "RemoteMirrorIssue",
    "RemoteMirrorIssueKind",
    "RemoteMirrorNamespaceManifest",
    "RemoteMirrorObjectManifest",
]
