"""Storage provider abstraction public surface.

Exports the `StorageProvider` Protocol, provider boundary records, the
`ProviderKind` enum, remote mirror manifest helpers, the
`get_storage_provider` factory, and the typed `OutboundStorageError`
hierarchy. Concrete backend classes remain private implementation details;
consumers depend on the Protocol, records, manifest helpers, and factory.
"""

from __future__ import annotations

from ._errors import (
    OutboundStorageConflictError,
    OutboundStorageError,
    OutboundStorageIntegrityError,
    OutboundStorageNetworkError,
    OutboundStorageNotFoundError,
    OutboundStoragePermissionError,
    OutboundStorageQuotaError,
    OutboundStorageUnavailableError,
    OutboundStorageValidationError,
    StorageCorruptionError,
)
from ._factory import get_storage_provider
from ._mirror_manifest import (
    REMOTE_MIRROR_MANIFEST_NAMESPACE,
    REMOTE_MIRROR_MANIFEST_SCHEMA_VERSION,
    build_remote_mirror_namespace_manifest,
    compare_remote_mirror_manifests,
    get_remote_mirror_namespace_manifest,
    inspect_remote_mirror_download,
    inspect_remote_mirror_upload,
    put_remote_mirror_namespace_manifest,
    remote_mirror_object_key_hmac,
)
from ._protocol import StorageProvider
from ._records import (
    ProviderKind,
    ProviderObjectMetadata,
    ProviderProbeReport,
    RemoteMirrorInspection,
    RemoteMirrorIssue,
    RemoteMirrorIssueKind,
    RemoteMirrorNamespaceManifest,
    RemoteMirrorObjectManifest,
)

__all__ = [
    "REMOTE_MIRROR_MANIFEST_NAMESPACE",
    "REMOTE_MIRROR_MANIFEST_SCHEMA_VERSION",
    "OutboundStorageConflictError",
    "OutboundStorageError",
    "OutboundStorageIntegrityError",
    "OutboundStorageNetworkError",
    "OutboundStorageNotFoundError",
    "OutboundStoragePermissionError",
    "OutboundStorageQuotaError",
    "OutboundStorageUnavailableError",
    "OutboundStorageValidationError",
    "ProviderKind",
    "ProviderObjectMetadata",
    "ProviderProbeReport",
    "RemoteMirrorInspection",
    "RemoteMirrorIssue",
    "RemoteMirrorIssueKind",
    "RemoteMirrorNamespaceManifest",
    "RemoteMirrorObjectManifest",
    "StorageCorruptionError",
    "StorageProvider",
    "build_remote_mirror_namespace_manifest",
    "compare_remote_mirror_manifests",
    "get_remote_mirror_namespace_manifest",
    "get_storage_provider",
    "inspect_remote_mirror_download",
    "inspect_remote_mirror_upload",
    "put_remote_mirror_namespace_manifest",
    "remote_mirror_object_key_hmac",
]
