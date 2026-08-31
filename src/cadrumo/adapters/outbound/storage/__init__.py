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

__all__: tuple[str, ...] = ()
