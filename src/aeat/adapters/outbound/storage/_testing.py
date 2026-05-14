"""In-memory `StorageProvider` real-implementation test backend.

A real implementation (not a mock) of the `StorageProvider` Protocol
backed by a Python dictionary. Used by application-layer tests that
need a Drive-shaped backend without the Drive API. Mirrors the
semantics of `GoogleDriveProvider` for the parts that diverge from
`LocalFileSystemProvider`:

- `provider_object_id` is a synthetic UUID-shaped string (mimicking
  Drive's `fileId`) rather than a filesystem path.
- `iter_namespaces` returns insertion order (not sorted) because Drive
  has no canonical namespace ordering.
- `probe` returns `provider_kind=IN_MEMORY` and never touches a real
  filesystem.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime

from ._errors import (
    StorageIntegrityError,
    StorageNotFoundError,
    StorageValidationError,
)
from ._records import ProviderKind, ProviderObjectMetadata, ProviderProbeReport


@dataclass(frozen=True)
class _StoredObject:
    """Internal record. Pairs payload with metadata for round-trip."""

    payload: bytes
    metadata: ProviderObjectMetadata


def _validate_namespace(namespace: str) -> str:
    cleaned = namespace.strip()
    if not cleaned:
        raise StorageValidationError("namespace must not be blank")
    return cleaned


def _validate_hmac(object_key_hmac: str) -> str:
    cleaned = object_key_hmac.strip()
    if not cleaned:
        raise StorageValidationError("object_key_hmac must not be blank")
    return cleaned


class InMemoryDriveProvider:
    """Drive-shaped real backend backed by a per-instance Python dict.

    Two-level dict: `{namespace: {object_key_hmac: _StoredObject}}`.
    Inserted namespaces stick around in `iter_namespaces` order even
    when emptied by `delete`, so tests can observe namespace lifecycle
    semantics that mirror Drive's folder behaviour.
    """

    def __init__(self) -> None:
        self._objects: dict[str, dict[str, _StoredObject]] = {}

    def put(
        self,
        namespace: str,
        object_key_hmac: str,
        payload: bytes,
        *,
        content_hash: str,
        label: str,
    ) -> ProviderObjectMetadata:
        namespace_clean = _validate_namespace(namespace)
        hmac_clean = _validate_hmac(object_key_hmac)
        if not content_hash.strip():
            raise StorageValidationError("content_hash must not be blank")
        del label  # The in-memory backend has no operator-visible filename.

        bucket = self._objects.setdefault(namespace_clean, {})
        metadata = ProviderObjectMetadata(
            namespace=namespace_clean,
            object_key_hmac=hmac_clean,
            provider_object_id=str(uuid.uuid4()),
            byte_length=len(payload),
            content_hash=content_hash,
            written_at=datetime.now(UTC),
        )
        bucket[hmac_clean] = _StoredObject(payload=payload, metadata=metadata)
        return metadata

    def get(self, namespace: str, object_key_hmac: str) -> tuple[bytes, ProviderObjectMetadata]:
        namespace_clean = _validate_namespace(namespace)
        hmac_clean = _validate_hmac(object_key_hmac)
        bucket = self._objects.get(namespace_clean)
        if bucket is None or hmac_clean not in bucket:
            raise StorageNotFoundError(
                f"object {hmac_clean!r} not found in namespace {namespace_clean!r}",
                context={"namespace": namespace_clean, "object_key_hmac": hmac_clean},
            )
        stored = bucket[hmac_clean]
        # Integrity check: refuse if the stored content_hash diverges
        # from the actual sha256 digest. Tests can intentionally inject
        # bad hashes to exercise the diverge path.
        stored_hash = stored.metadata.content_hash
        stripped = stored_hash.split("-", 1)[1] if stored_hash.startswith("sha256-") else stored_hash
        if stripped and len(stripped) == 64:
            actual = hashlib.sha256(stored.payload).hexdigest()
            if stripped != actual:
                raise StorageIntegrityError(
                    f"content_hash mismatch for {hmac_clean!r} in {namespace_clean!r}",
                    context={"stored_hash": stored_hash, "actual_sha256": actual},
                )
        return stored.payload, stored.metadata

    def delete(self, namespace: str, object_key_hmac: str) -> bool:
        namespace_clean = _validate_namespace(namespace)
        hmac_clean = _validate_hmac(object_key_hmac)
        bucket = self._objects.get(namespace_clean)
        if bucket is None or hmac_clean not in bucket:
            return False
        del bucket[hmac_clean]
        return True

    def iter_namespaces(self) -> Iterator[str]:
        # Insertion order — mirrors Drive's lack of canonical namespace ordering.
        yield from self._objects.keys()

    def iter_objects(self, namespace: str) -> Iterator[ProviderObjectMetadata]:
        namespace_clean = _validate_namespace(namespace)
        bucket = self._objects.get(namespace_clean)
        if bucket is None:
            raise StorageNotFoundError(
                f"namespace {namespace_clean!r} does not exist",
                context={"namespace": namespace_clean},
            )
        for stored in bucket.values():
            yield stored.metadata

    def probe(self, *, read_only: bool = False) -> ProviderProbeReport:
        return ProviderProbeReport(
            provider_kind=ProviderKind.IN_MEMORY,
            reachable=True,
            writable=not read_only,
            read_only=read_only,
            detail=(
                "in-memory backend; probe is always reachable"
                + ("; read_only=True so writable reported False" if read_only else "")
            ),
        )


__all__ = ["InMemoryDriveProvider"]
