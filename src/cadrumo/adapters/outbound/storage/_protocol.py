""":class:`StorageProvider` Protocol - the v1 storage backend contract.

Concrete backends implement this Protocol behind
:func:`adapters.outbound.storage.get_storage_provider`. The coordinator
depends only on this public surface, the provider records
:class:`ProviderObjectMetadata` and :class:`ProviderProbeReport`, and the typed
:class:`adapters.outbound.storage.OutboundStorageError` hierarchy;
concrete backend classes remain private implementation details.

Bytes are the unit of payload. Encryption + classification + envelope
handling happens above the provider layer (in the application sync
coordinator) so providers receive opaque encrypted bytes, not plaintext
domain data.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol, runtime_checkable

from .records import ProviderObjectMetadata, ProviderProbeReport


@runtime_checkable
class StorageProvider(Protocol):
    """Bytes-in / bytes-out per-namespace object store.

    The protocol is selected by
    :func:`adapters.outbound.storage.get_storage_provider` from the
    configured :class:`adapters.outbound.storage.ProviderKind`, but
    callers operate only on the protocol plus :class:`ProviderObjectMetadata`
    and :class:`ProviderProbeReport` boundary records.

    Implementations must be safe to instantiate from settings without
    network IO. Backend setup, credential refresh, remote-folder
    creation, and filesystem root creation happen lazily on :meth:`probe` or
    the first read/write operation.

    Provider methods translate expected backend failures into the
    :class:`adapters.outbound.storage.OutboundStorageError` hierarchy at
    this boundary. Native backend exceptions should not cross the Protocol
    surface except for programming errors.
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
            content_hash: Cryptographic hash of ``payload`` for integrity
                round-tripping
                (:class:`adapters.outbound.storage.OutboundStorageIntegrityError`
                raised on read if the stored hash diverges).
            label: Human-readable suffix appended to the filename for
                operator orientation. Derived from the per-namespace
                label deriver registered at the application layer.

        Returns:
            The newly-written object's :class:`ProviderObjectMetadata`.
        """
        ...

    def get(self, namespace: str, object_key_hmac: str) -> tuple[bytes, ProviderObjectMetadata]:
        """Read an object's payload and metadata.

        Args:
            namespace: Source namespace to read from.
            object_key_hmac: Stable HMAC identifying the object.

        Returns:
            A 2-tuple containing payload bytes and
            :class:`ProviderObjectMetadata`.
        """
        ...

    def delete(self, namespace: str, object_key_hmac: str) -> bool:
        """Remove an object. Return True iff it existed before this call.

        Args:
            namespace: Namespace containing the object.
            object_key_hmac: Stable HMAC identifying the object to remove.

        Returns:
            True if the object existed and was removed; False if it was absent.
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
        """Yield every object in ``namespace``. Order is backend-defined.

        Args:
            namespace: Namespace to enumerate.

        Returns:
            An iterator of :class:`ProviderObjectMetadata` for each object.
        """
        ...

    def probe(self, *, read_only: bool = False) -> ProviderProbeReport:
        """Health-check the backend; return a structured report.

        When ``read_only=False``, performs provider-specific reachability
        checks plus a sentinel payload write/delete round-trip in the
        ``_probe/`` namespace to verify write capability. When
        ``read_only=True``, skips the sentinel payload round-trip but may
        still perform provider-specific root or service checks.

        Args:
            read_only: When True, skips the sentinel payload round-trip.

        Returns:
            A :class:`ProviderProbeReport` describing the backend's state.
            Never raises on expected backend failures; failure modes
            surface via the report's ``reachable`` / ``writable`` fields
            and ``detail`` string.
        """
        ...


__all__ = ["StorageProvider"]
