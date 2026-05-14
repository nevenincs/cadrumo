"""Pydantic records and enums for the storage provider abstraction.

Three records anchor the provider boundary:

- `ProviderKind` — closed enum naming the v1 backends.
- `ProviderObjectMetadata` — per-object metadata returned by listing /
  fetching operations. Carries the object key HMAC, namespace, byte
  size, content hash, and backend-native identifier.
- `ProviderProbeReport` — health-probe result. Reports whether the
  backend is reachable, writable, and (when applicable) bound to the
  expected root folder. The `read_only` field surfaces whether the
  probe ran in read-only mode (no sentinel-write round-trip).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ProviderKind(StrEnum):
    """Closed enumeration of supported storage backends."""

    LOCAL_FILESYSTEM = "local_filesystem"
    GOOGLE_DRIVE = "google_drive"


class ProviderObjectMetadata(BaseModel):
    """Per-object metadata returned by the storage provider listing API.

    `provider_object_id` is the backend-native identifier (a filesystem
    path for `LocalFileSystemProvider`, a Drive `fileId` for
    `GoogleDriveProvider`, an in-memory key for the test backend). The
    coordinator threads it through subsequent get/delete/patch calls
    without re-resolving by name.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    namespace: str = Field(min_length=1)
    object_key_hmac: str = Field(min_length=1)
    provider_object_id: str = Field(min_length=1)
    byte_length: int = Field(ge=0)
    content_hash: str = Field(min_length=1)
    written_at: datetime


class ProviderProbeReport(BaseModel):
    """Result of a `probe()` health check against a storage backend.

    `reachable` is True iff the backend endpoint responds at all.
    `writable` is True iff a sentinel-file round-trip succeeded;
    inherently False when the probe runs in read-only mode.
    `root_folder_present` is non-None only when the backend supports
    the notion of an operator-configured root folder (currently
    Google Drive).
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    provider_kind: ProviderKind
    reachable: bool
    writable: bool
    read_only: bool
    root_folder_present: bool | None = None
    detail: str = ""


__all__ = [
    "ProviderKind",
    "ProviderObjectMetadata",
    "ProviderProbeReport",
]
