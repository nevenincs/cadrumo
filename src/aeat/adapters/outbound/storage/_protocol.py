"""`StorageProvider` Protocol — the v1 storage backend contract.

Every concrete backend (`LocalFileSystemProvider`, `GoogleDriveProvider`,
`InMemoryDriveProvider`) implements this Protocol. The coordinator
depends only on the Protocol surface, so swapping backends is a one-
line settings change.

Bytes are the unit of payload. Encryption + classification + envelope
handling happens above the provider layer (in the application sync
coordinator) so providers never see plaintext domain data.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol, runtime_checkable

from ._records import ProviderObjectMetadata, ProviderProbeReport


@runtime_checkable
class StorageProvider(Protocol):
    """Bytes-in / bytes-out per-namespace object store.

    Implementations must be safe to instantiate from settings without
    network IO. Network operations (login refresh, root-folder
    creation) happen lazily on first `probe()` or first read/write.
    """

    def put(
        self,
        namespace: str,
        object_key_hmac: str,
        payload: bytes,
        *,
        content_hash: str,
        label: str,
    ) -> ProviderObjectMetadata:
        """Write or overwrite an object; return its post-write metadata.

        Args:
            namespace: Destination namespace (substrate namespace name).
            object_key_hmac: Stable HMAC of the object key. Provider
                surfaces it as part of the filename / Drive name so
                operator-visible listings carry the HMAC prefix.
            payload: Bytes to write. Already encrypted at the
                application layer; providers do not decrypt or inspect.
            content_hash: Cryptographic hash of `payload` for integrity
                round-tripping (`OutboundStorageIntegrityError` raised on read
                if the stored hash diverges).
            label: Human-readable suffix appended to the filename for
                operator orientation. Derived from the per-namespace
                label deriver registered at the application layer.

        Returns:
            The newly-written object's metadata.

        Raises:
            OutboundStorageConflictError: Concurrent write detected.
            OutboundStoragePermissionError: Credentials lack write scope.
            OutboundStorageQuotaError: Backend quota exhausted.
            OutboundStorageNetworkError: Endpoint unreachable.
        """

        ...

    def get(self, namespace: str, object_key_hmac: str) -> tuple[bytes, ProviderObjectMetadata]:
        """Read an object's payload and metadata.

        Raises:
            OutboundStorageNotFoundError: Object does not exist.
            OutboundStorageIntegrityError: Stored content hash mismatches the
                fetched payload.
            OutboundStoragePermissionError: Credentials lack read scope.
            OutboundStorageNetworkError: Endpoint unreachable.
        """

        ...

    def delete(self, namespace: str, object_key_hmac: str) -> bool:
        """Remove an object. Return True iff it existed before this call.

        Raises:
            OutboundStoragePermissionError: Credentials lack delete scope.
            OutboundStorageNetworkError: Endpoint unreachable.
        """

        ...

    def iter_namespaces(self) -> Iterator[str]:
        """Yield every namespace the backend currently holds.

        Includes operator-facing underscore-prefixed buckets such as
        `_inbound`, `_workspace`, `_probe`, `_sync-state` when they
        exist on the backend.
        """

        ...

    def iter_objects(self, namespace: str) -> Iterator[ProviderObjectMetadata]:
        """Yield every object in `namespace`. Order is backend-defined.

        Raises:
            OutboundStorageNotFoundError: Namespace does not exist.
            OutboundStoragePermissionError: Credentials lack listing scope.
            OutboundStorageNetworkError: Endpoint unreachable.
        """

        ...

    def probe(self, *, read_only: bool = False) -> ProviderProbeReport:
        """Health-check the backend; return a structured report.

        When `read_only=False`, performs a sentinel-file round-trip
        (put + get + delete in the `_probe/` namespace) to verify write
        capability. When `read_only=True`, only attempts to list
        namespaces.

        Returns:
            A `ProviderProbeReport` describing the backend's state.
            Never raises on transient failures; failure modes surface
            via the report's `reachable` / `writable` fields and
            `detail` string.
        """

        ...


__all__ = ["StorageProvider"]
