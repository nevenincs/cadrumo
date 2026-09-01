"""Pydantic records and enums for the outbound storage abstraction.

Provider records anchor the storage boundary:

- :class:`adapters.outbound.storage.StorageProvider` - synchronous
  bytes-in / bytes-out provider Protocol.
- :class:`ProviderKind` - closed enum naming the v1 backends.
- :class:`ProviderObjectMetadata` - per-object metadata returned by listing /
  fetching operations. Carries the object key HMAC, namespace, byte
  size, content hash, and backend-native identifier.
- :class:`ProviderProbeReport` - health-probe result. Reports whether the
  backend is reachable, writable, and (when applicable) bound to the
  expected root folder. The ``read_only`` field surfaces whether the
  probe ran in read-only mode (no sentinel-write round-trip).
- :class:`RemoteMirrorObjectManifest`,
  :class:`RemoteMirrorNamespaceManifest`, :class:`RemoteMirrorIssue`, and
  :class:`RemoteMirrorInspection` - immutable manifest and inspection records
  for remote ciphertext mirror reconciliation by
  :mod:`adapters.outbound.storage._mirror_manifest`.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, NonNegativeInt, model_validator

from ....core.identity import ContentDigest
from ....core.models import STRICT_FROZEN_CONFIG

# Every identifier below is a SHA-256 hex digest produced by
# ``core.hashing.sha256_hex``, so each is the canonical
# :data:`~core.identity.ContentDigest` shape under a distinct semantic name.
# A length-only constraint accepted uppercase and non-hex 64-character
# strings that the canonical alias refuses, letting a malformed digest reach
# a persisted manifest and surface only when a later pass recomputes it.

#: HMAC-SHA-256 hex digest naming one object at the remote provider boundary.
_ObjectKeyHmac = ContentDigest
#: SHA-256 hex digest of the mirrored ciphertext bytes.
_CiphertextHash = ContentDigest
#: SHA-256 hex digest identifying one secure-object storage revision.
_StorageRevisionId = ContentDigest


class ProviderKind(StrEnum):
    """Closed storage backend selector for :func:`adapters.outbound.storage.get_storage_provider`."""

    LOCAL_FILESYSTEM = "local_filesystem"
    GOOGLE_DRIVE = "google_drive"


class RemoteMirrorIssueKind(StrEnum):
    """Remote ciphertext mirror degradation classes carried by :class:`RemoteMirrorIssue`."""

    PARTIAL_UPLOAD = "partial_upload"
    PARTIAL_DOWNLOAD = "partial_download"
    STALE_MIRROR = "stale_mirror"
    REVISION_CONFLICT = "revision_conflict"


class ProviderObjectMetadata(BaseModel):
    """Per-object metadata returned by storage-provider operations.

    Returned by :class:`adapters.outbound.storage.StorageProvider`
    methods: :meth:`adapters.outbound.storage.StorageProvider.put`,
    :meth:`adapters.outbound.storage.StorageProvider.get`, and
    :meth:`adapters.outbound.storage.StorageProvider.iter_objects`.
    ``provider_object_id`` is the backend-native identifier (a filesystem path
    for the local provider, a Drive ``fileId`` for the Google Drive provider).
    The coordinator threads it through subsequent get/delete/patch calls without
    re-resolving by name.
    """

    model_config = STRICT_FROZEN_CONFIG

    namespace: str = Field(min_length=1)
    object_key_hmac: str = Field(min_length=1)
    provider_object_id: str = Field(min_length=1)
    byte_length: NonNegativeInt
    content_hash: str = Field(min_length=1)
    written_at: datetime


class ProviderProbeReport(BaseModel):
    """Health-check result returned by storage-provider probes.

    Returned by
    :meth:`adapters.outbound.storage.StorageProvider.probe`.
    ``reachable`` is True iff the backend endpoint responds at all.
    ``writable`` is True iff a sentinel payload write/delete succeeded;
    inherently False when the probe runs in read-only mode.
    ``root_folder_present`` is non-None only when the backend supports
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
    """One ciphertext object entry recorded in a :class:`RemoteMirrorNamespaceManifest`."""

    model_config = STRICT_FROZEN_CONFIG

    namespace: str = Field(min_length=1)
    object_key_hmac: _ObjectKeyHmac
    classification: str = Field(min_length=1)
    schema_version: int = Field(ge=1)
    byte_length: NonNegativeInt
    ciphertext_hash: _CiphertextHash
    storage_revision_id: _StorageRevisionId | None = None
    previous_storage_revision_id: _StorageRevisionId | None = None
    revision_ancestor_ids: tuple[_StorageRevisionId, ...] = ()
    row_written_at: datetime
    revision_written_at: datetime | None = None


class RemoteMirrorNamespaceManifest(BaseModel):
    """Manifest persisted beside remote ciphertext objects for one namespace.

    Built by
    :func:`adapters.outbound.storage.build_remote_mirror_namespace_manifest`
    and persisted by
    :func:`adapters.outbound.storage.put_remote_mirror_namespace_manifest`.
    """

    model_config = STRICT_FROZEN_CONFIG

    manifest_schema_version: int = Field(ge=1)
    namespace: str = Field(min_length=1)
    object_count: NonNegativeInt
    latest_revision_id: _StorageRevisionId | None = None
    latest_revision_written_at: datetime | None = None
    objects: tuple[RemoteMirrorObjectManifest, ...]

    @model_validator(mode="after")
    def _enforce_object_key_uniqueness_and_count(self) -> RemoteMirrorNamespaceManifest:
        """Refuse foreign-namespace children, duplicate object keys, and a disagreeing ``object_count``.

        Comparison in
        :mod:`adapters.outbound.storage._mirror_manifest` keys both manifests
        by ``object_key_hmac``, so a repeated key would silently discard every
        earlier row and hide the revision conflict it carried. The key is one
        object's identity within a namespace, so a repeat is manifest
        corruption rather than a representable state; refusing it here makes a
        tampered or torn remote manifest fail closed through the
        :class:`OutboundStorageIntegrityError` the loader already raises.

        The namespace binding closes the same class of hole one level up. A
        manifest describes exactly one namespace, but each child carried its
        own ``namespace`` field that nothing checked against the parent, and
        the download path fetches by the *child's* value. A manifest named
        ``target`` holding a child named ``foreign`` therefore inspected clean
        and pulled another namespace's ciphertext under the target's identity.
        Binding the two here means the confusion cannot be represented at all,
        rather than being caught separately by each consumer.
        """
        foreign = sorted({entry.namespace for entry in self.objects if entry.namespace != self.namespace})
        if foreign:
            raise ValueError(
                f"remote mirror manifest for namespace {self.namespace!r} "
                f"records objects from foreign namespaces: {foreign}",
            )
        keys = [entry.object_key_hmac for entry in self.objects]
        duplicates = sorted({key for key in keys if keys.count(key) > 1})
        if duplicates:
            raise ValueError(
                f"remote mirror manifest repeats object_key_hmac entries: {duplicates}",
            )
        if self.object_count != len(self.objects):
            raise ValueError(
                f"remote mirror manifest object_count {self.object_count} "
                f"disagrees with {len(self.objects)} recorded objects",
            )
        return self


class RemoteMirrorIssue(BaseModel):
    """One detected remote mirror degradation in a :class:`RemoteMirrorInspection`."""

    model_config = STRICT_FROZEN_CONFIG

    kind: RemoteMirrorIssueKind
    namespace: str = Field(min_length=1)
    object_key_hmac: _ObjectKeyHmac | None = None
    detail: str = Field(min_length=1)


class RemoteMirrorInspection(BaseModel):
    """Typed result returned by remote mirror comparison and inspection helpers."""

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
