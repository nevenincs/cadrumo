"""Public outbound storage provider API.

Re-exports the :class:`StorageProvider` Protocol, the :class:`ProviderKind`
selector, provider boundary records such as :class:`ProviderObjectMetadata`
and :class:`ProviderProbeReport`, remote mirror records such as
:class:`RemoteMirrorNamespaceManifest` and :class:`RemoteMirrorInspection`,
the :func:`get_storage_provider` factory, Drive setup helpers
:func:`build_google_credentials` and :func:`resolve_drive_root_folder_id`,
manifest helpers (:func:`build_remote_mirror_namespace_manifest`,
:func:`put_remote_mirror_namespace_manifest`,
:func:`get_remote_mirror_namespace_manifest`,
:func:`compare_remote_mirror_manifests`,
:func:`inspect_remote_mirror_upload`,
:func:`inspect_remote_mirror_download`, and
:func:`remote_mirror_object_key_hmac`), the Drive pagination guard
:func:`next_drive_page_token`, and the typed :class:`OutboundStorageError`
hierarchy.

Concrete backends in :mod:`adapters.outbound.storage._local` and
:mod:`adapters.outbound.storage._google_drive` remain private
implementation details; consumers depend on this Protocol, these records, the
manifest helpers, and the factory.
"""

from __future__ import annotations

from ._drive_pagination import next_drive_page_token
from .errors import (
    OutboundStorageConflictError,
    OutboundStorageError,
    OutboundStorageIntegrityError,
    OutboundStorageNetworkError,
    OutboundStorageNotFoundError,
    OutboundStoragePathTooLongError,
    OutboundStoragePermissionError,
    OutboundStorageQuotaError,
    OutboundStorageUnavailableError,
    OutboundStorageValidationError,
    StorageCorruptionError,
)
from ._factory import build_google_credentials, get_storage_provider, resolve_drive_root_folder_id
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
from ._path_budget import windows_worst_case_object_path_suffix_length
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
    "OutboundStoragePathTooLongError",
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
    "build_google_credentials",
    "build_remote_mirror_namespace_manifest",
    "compare_remote_mirror_manifests",
    "get_remote_mirror_namespace_manifest",
    "get_storage_provider",
    "inspect_remote_mirror_download",
    "inspect_remote_mirror_upload",
    "next_drive_page_token",
    "put_remote_mirror_namespace_manifest",
    "remote_mirror_object_key_hmac",
    "resolve_drive_root_folder_id",
    "windows_worst_case_object_path_suffix_length",
]
