"""Remote ciphertext mirror manifest construction and persistence."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable

from ...persistence.storage.sql.secure_objects import SecureObjectRawRow
from ._protocol import StorageProvider
from ._records import ProviderObjectMetadata, RemoteMirrorNamespaceManifest, RemoteMirrorObjectManifest

REMOTE_MIRROR_MANIFEST_NAMESPACE = "_sync-state"
REMOTE_MIRROR_MANIFEST_SCHEMA_VERSION = 1


def build_remote_mirror_namespace_manifest(
    namespace: str,
    rows: Iterable[SecureObjectRawRow],
) -> RemoteMirrorNamespaceManifest:
    """Build a manifest from raw ciphertext rows for one secure-object namespace."""

    entries = tuple(_remote_mirror_object_manifest(row) for row in rows if row.namespace == namespace)
    latest = max(
        (entry for entry in entries if entry.revision_written_at is not None),
        key=lambda entry: entry.revision_written_at,
        default=None,
    )
    return RemoteMirrorNamespaceManifest(
        manifest_schema_version=REMOTE_MIRROR_MANIFEST_SCHEMA_VERSION,
        namespace=namespace,
        object_count=len(entries),
        latest_revision_id=latest.storage_revision_id if latest is not None else None,
        latest_revision_written_at=latest.revision_written_at if latest is not None else None,
        objects=entries,
    )


def put_remote_mirror_namespace_manifest(
    provider: StorageProvider,
    manifest: RemoteMirrorNamespaceManifest,
) -> ProviderObjectMetadata:
    """Persist a namespace mirror manifest through the remote storage provider."""

    payload = manifest.model_dump_json().encode("utf-8")
    return provider.put(
        REMOTE_MIRROR_MANIFEST_NAMESPACE,
        _manifest_object_key_hmac(manifest.namespace),
        payload,
        content_hash=f"sha256-{hashlib.sha256(payload).hexdigest()}",
        label=f"mirror-manifest-{_manifest_label(manifest.namespace)}",
    )


def _remote_mirror_object_manifest(row: SecureObjectRawRow) -> RemoteMirrorObjectManifest:
    return RemoteMirrorObjectManifest(
        namespace=row.namespace,
        object_key_hmac=remote_mirror_object_key_hmac(row.namespace, row.object_key),
        classification=row.classification,
        schema_version=row.schema_version,
        byte_length=len(row.payload),
        ciphertext_hash=row.ciphertext_hash or hashlib.sha256(row.payload).hexdigest(),
        storage_revision_id=row.revision_id,
        previous_storage_revision_id=row.previous_revision_id,
        row_written_at=row.written_at,
        revision_written_at=row.revision_written_at,
    )


def _manifest_object_key_hmac(namespace: str) -> str:
    return hashlib.sha256(f"remote-mirror-manifest:{namespace}".encode()).hexdigest()


def remote_mirror_object_key_hmac(namespace: str, object_key: bytes) -> str:
    """Compute the provider object key used for mirrored ciphertext rows."""

    hasher = hashlib.sha256()
    hasher.update(namespace.encode())
    hasher.update(b"\x00")
    hasher.update(object_key)
    return hasher.hexdigest()


def _manifest_label(namespace: str) -> str:
    return "".join(character if character.isalnum() else "-" for character in namespace)[:64] or "namespace"


__all__ = [
    "REMOTE_MIRROR_MANIFEST_NAMESPACE",
    "REMOTE_MIRROR_MANIFEST_SCHEMA_VERSION",
    "build_remote_mirror_namespace_manifest",
    "put_remote_mirror_namespace_manifest",
    "remote_mirror_object_key_hmac",
]
