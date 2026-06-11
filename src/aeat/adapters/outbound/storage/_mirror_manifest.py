"""Remote ciphertext mirror manifest construction and persistence."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from datetime import datetime

from pydantic import ValidationError

from ...persistence.storage.sql.secure_objects import SecureObjectRawRow
from ._errors import OutboundStorageIntegrityError, OutboundStorageNotFoundError, OutboundStorageValidationError
from ._protocol import StorageProvider
from ._records import (
    ProviderObjectMetadata,
    RemoteMirrorInspection,
    RemoteMirrorIssue,
    RemoteMirrorIssueKind,
    RemoteMirrorNamespaceManifest,
    RemoteMirrorObjectManifest,
)

REMOTE_MIRROR_MANIFEST_NAMESPACE = "_sync-state"
REMOTE_MIRROR_MANIFEST_SCHEMA_VERSION = 1


def build_remote_mirror_namespace_manifest(
    namespace: str,
    rows: Iterable[SecureObjectRawRow],
) -> RemoteMirrorNamespaceManifest:
    """Build a :class:`RemoteMirrorNamespaceManifest` from raw ciphertext rows for one namespace."""
    entries = tuple(_remote_mirror_object_manifest(row) for row in rows if row.namespace == namespace)
    timed_entries = tuple(entry for entry in entries if entry.revision_written_at is not None)

    def _revision_written_at(entry: RemoteMirrorObjectManifest) -> datetime:
        assert entry.revision_written_at is not None
        return entry.revision_written_at

    latest = max(timed_entries, key=_revision_written_at, default=None)
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
    """Persist a namespace mirror manifest and return its :class:`ProviderObjectMetadata`."""
    payload = manifest.model_dump_json().encode("utf-8")
    return provider.put(
        REMOTE_MIRROR_MANIFEST_NAMESPACE,
        _manifest_object_key_hmac(manifest.namespace),
        payload,
        content_hash=f"sha256-{hashlib.sha256(payload).hexdigest()}",
        label=f"mirror-manifest-{_manifest_label(manifest.namespace)}",
    )


def get_remote_mirror_namespace_manifest(
    provider: StorageProvider,
    namespace: str,
) -> RemoteMirrorNamespaceManifest | None:
    """Return the :class:`RemoteMirrorNamespaceManifest` for ``namespace`` when one exists."""
    try:
        payload, _metadata = provider.get(REMOTE_MIRROR_MANIFEST_NAMESPACE, _manifest_object_key_hmac(namespace))
    except OutboundStorageNotFoundError:
        return None
    try:
        return RemoteMirrorNamespaceManifest.model_validate_json(payload)
    except ValidationError as exc:
        raise OutboundStorageIntegrityError(
            f"remote mirror manifest for namespace {namespace!r} is malformed",
            context={"namespace": namespace},
        ) from exc


def inspect_remote_mirror_upload(
    provider: StorageProvider,
    expected_manifest: RemoteMirrorNamespaceManifest,
) -> RemoteMirrorInspection:
    """Detect remote upload drift for the expected namespace manifest.

    Returns:
        A :class:`RemoteMirrorInspection` describing the drift between the
        expected manifest and the remote mirror.
    """
    remote_manifest = _load_remote_manifest(provider, expected_manifest.namespace)
    issues = list(_compare_manifest_objects(local=expected_manifest, remote=remote_manifest))
    for entry in expected_manifest.objects:
        try:
            payload, metadata = provider.get(entry.namespace, entry.object_key_hmac)
        except OutboundStorageNotFoundError:
            issues.append(
                RemoteMirrorIssue(
                    kind=RemoteMirrorIssueKind.PARTIAL_UPLOAD,
                    namespace=entry.namespace,
                    object_key_hmac=entry.object_key_hmac,
                    detail="ciphertext object is missing from the remote provider",
                ),
            )
            continue
        except OutboundStorageIntegrityError as exc:
            issues.append(
                RemoteMirrorIssue(
                    kind=RemoteMirrorIssueKind.PARTIAL_UPLOAD,
                    namespace=entry.namespace,
                    object_key_hmac=entry.object_key_hmac,
                    detail=str(exc),
                ),
            )
            continue
        if not _provider_payload_matches_manifest_entry(payload, metadata, entry):
            issues.append(
                RemoteMirrorIssue(
                    kind=RemoteMirrorIssueKind.PARTIAL_UPLOAD,
                    namespace=entry.namespace,
                    object_key_hmac=entry.object_key_hmac,
                    detail="remote ciphertext metadata does not match the expected manifest entry",
                ),
            )
    return RemoteMirrorInspection(namespace=expected_manifest.namespace, issues=tuple(issues))


def inspect_remote_mirror_download(
    provider: StorageProvider,
    remote_manifest: RemoteMirrorNamespaceManifest,
) -> RemoteMirrorInspection:
    """Detect whether a remote manifest can be downloaded completely; return a :class:`RemoteMirrorInspection`."""
    issues: list[RemoteMirrorIssue] = []
    for entry in remote_manifest.objects:
        try:
            payload, metadata = provider.get(entry.namespace, entry.object_key_hmac)
        except (OutboundStorageNotFoundError, OutboundStorageIntegrityError) as exc:
            issues.append(
                RemoteMirrorIssue(
                    kind=RemoteMirrorIssueKind.PARTIAL_DOWNLOAD,
                    namespace=entry.namespace,
                    object_key_hmac=entry.object_key_hmac,
                    detail=str(exc),
                ),
            )
            continue
        if not _provider_payload_matches_manifest_entry(payload, metadata, entry):
            issues.append(
                RemoteMirrorIssue(
                    kind=RemoteMirrorIssueKind.PARTIAL_DOWNLOAD,
                    namespace=entry.namespace,
                    object_key_hmac=entry.object_key_hmac,
                    detail="remote ciphertext metadata does not match the manifest entry",
                ),
            )
    return RemoteMirrorInspection(namespace=remote_manifest.namespace, issues=tuple(issues))


def compare_remote_mirror_manifests(
    *,
    local: RemoteMirrorNamespaceManifest,
    remote: RemoteMirrorNamespaceManifest,
) -> RemoteMirrorInspection:
    """Compare local and remote namespace manifests and return a :class:`RemoteMirrorInspection`."""
    return RemoteMirrorInspection(
        namespace=local.namespace,
        issues=tuple(_compare_manifest_objects(local=local, remote=remote)),
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
        revision_ancestor_ids=row.revision_ancestor_ids,
        row_written_at=row.written_at,
        revision_written_at=row.revision_written_at,
    )


def _manifest_object_key_hmac(namespace: str) -> str:
    return hashlib.sha256(f"remote-mirror-manifest:{namespace}".encode()).hexdigest()


def _load_remote_manifest(provider: StorageProvider, namespace: str) -> RemoteMirrorNamespaceManifest:
    remote_manifest = get_remote_mirror_namespace_manifest(provider, namespace)
    if remote_manifest is None:
        return RemoteMirrorNamespaceManifest(
            manifest_schema_version=REMOTE_MIRROR_MANIFEST_SCHEMA_VERSION,
            namespace=namespace,
            object_count=0,
            objects=(),
        )
    return remote_manifest


def _compare_manifest_objects(
    *,
    local: RemoteMirrorNamespaceManifest,
    remote: RemoteMirrorNamespaceManifest,
) -> tuple[RemoteMirrorIssue, ...]:
    if local.namespace != remote.namespace:
        raise OutboundStorageValidationError(
            "cannot compare remote mirror manifests from different namespaces",
            context={"local_namespace": local.namespace, "remote_namespace": remote.namespace},
        )
    issues: list[RemoteMirrorIssue] = []
    local_by_key = {entry.object_key_hmac: entry for entry in local.objects}
    remote_by_key = {entry.object_key_hmac: entry for entry in remote.objects}
    for object_key_hmac in sorted(local_by_key.keys() - remote_by_key.keys()):
        issues.append(
            RemoteMirrorIssue(
                kind=RemoteMirrorIssueKind.PARTIAL_UPLOAD,
                namespace=local.namespace,
                object_key_hmac=object_key_hmac,
                detail="local manifest entry is absent from the remote manifest",
            ),
        )
    for object_key_hmac in sorted(remote_by_key.keys() - local_by_key.keys()):
        issues.append(
            RemoteMirrorIssue(
                kind=RemoteMirrorIssueKind.PARTIAL_DOWNLOAD,
                namespace=local.namespace,
                object_key_hmac=object_key_hmac,
                detail="remote manifest entry is absent from the local manifest",
            ),
        )
    for object_key_hmac in sorted(local_by_key.keys() & remote_by_key.keys()):
        local_entry = local_by_key[object_key_hmac]
        remote_entry = remote_by_key[object_key_hmac]
        if local_entry.storage_revision_id == remote_entry.storage_revision_id:
            if local_entry.ciphertext_hash != remote_entry.ciphertext_hash:
                issues.append(
                    RemoteMirrorIssue(
                        kind=RemoteMirrorIssueKind.REVISION_CONFLICT,
                        namespace=local.namespace,
                        object_key_hmac=object_key_hmac,
                        detail="matching revision ids carry different ciphertext hashes",
                    ),
                )
            continue
        if _is_stale_remote_entry(local_entry=local_entry, remote_entry=remote_entry):
            issues.append(
                RemoteMirrorIssue(
                    kind=RemoteMirrorIssueKind.STALE_MIRROR,
                    namespace=local.namespace,
                    object_key_hmac=object_key_hmac,
                    detail="remote manifest is behind the local storage revision",
                ),
            )
            continue
        issues.append(
            RemoteMirrorIssue(
                kind=RemoteMirrorIssueKind.REVISION_CONFLICT,
                namespace=local.namespace,
                object_key_hmac=object_key_hmac,
                detail="local and remote storage revisions are not in the same lineage",
            ),
        )
    return tuple(issues)


def _provider_payload_matches_manifest_entry(
    payload: bytes,
    metadata: ProviderObjectMetadata,
    entry: RemoteMirrorObjectManifest,
) -> bool:
    content_hash = metadata.content_hash
    digest = content_hash.split("-", 1)[1] if content_hash.startswith("sha256-") else content_hash
    return (
        metadata.namespace == entry.namespace
        and metadata.object_key_hmac == entry.object_key_hmac
        and metadata.byte_length == entry.byte_length
        and len(payload) == entry.byte_length
        and digest == entry.ciphertext_hash
        and hashlib.sha256(payload).hexdigest() == entry.ciphertext_hash
    )


def _is_stale_remote_entry(
    *,
    local_entry: RemoteMirrorObjectManifest,
    remote_entry: RemoteMirrorObjectManifest,
) -> bool:
    return (
        remote_entry.storage_revision_id == local_entry.previous_storage_revision_id
        or remote_entry.storage_revision_id in local_entry.revision_ancestor_ids
    )


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
    "compare_remote_mirror_manifests",
    "get_remote_mirror_namespace_manifest",
    "inspect_remote_mirror_download",
    "inspect_remote_mirror_upload",
    "put_remote_mirror_namespace_manifest",
    "remote_mirror_object_key_hmac",
]
