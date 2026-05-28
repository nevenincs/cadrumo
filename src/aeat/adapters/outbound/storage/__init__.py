"""Storage provider abstraction — public surface.

Exports the `StorageProvider` Protocol, the four pydantic records that
cross the provider boundary, the `ProviderKind` enum, and the typed
`OutboundStorageError` hierarchy. Concrete backends (`_local.py`,
`_google_drive.py`, `_testing.py`) and the `_factory.py` are not
re-exported; consumers depend on the Protocol surface and the records.
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
    put_remote_mirror_namespace_manifest,
    remote_mirror_object_key_hmac,
)
from ._protocol import StorageProvider
from ._records import (
    ProviderKind,
    ProviderObjectMetadata,
    ProviderProbeReport,
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
    "RemoteMirrorNamespaceManifest",
    "RemoteMirrorObjectManifest",
    "StorageCorruptionError",
    "StorageProvider",
    "build_remote_mirror_namespace_manifest",
    "get_storage_provider",
    "put_remote_mirror_namespace_manifest",
    "remote_mirror_object_key_hmac",
]
