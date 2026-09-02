"""Remote ciphertext mirror manifest construction, persistence, and inspection.

This module converts
:class:`adapters.persistence.storage.sql.secure_objects.SecureObjectRawRow`
records into :class:`RemoteMirrorNamespaceManifest` payloads, stores those
payloads through :class:`StorageProvider` under
:data:`REMOTE_MIRROR_MANIFEST_NAMESPACE`, and reports mirror drift as
:class:`RemoteMirrorInspection` records. Google sync uses the inspection
helpers to distinguish partial uploads, partial downloads, stale mirrors, and
revision conflicts without exposing plaintext secure-object payloads.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from pydantic import ValidationError

from ....application.operator_actions.preconditions import no_action_precondition_verdict
from ....core.hashing import sha256_hex
from ....core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ...persistence.storage.sql.secure_objects import SecureObjectRawRow
from .errors import OutboundStorageIntegrityError, OutboundStorageNotFoundError, OutboundStorageValidationError
from .protocol import StorageProvider
from .records import (
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
    """Build a :class:`RemoteMirrorNamespaceManifest` for one ciphertext namespace.

    Only rows whose
    :class:`adapters.persistence.storage.sql.secure_objects.SecureObjectRawRow`
    namespace matches ``namespace`` are included. Each row becomes a
    :class:`RemoteMirrorObjectManifest`, and the latest revision watermark is
    derived from the newest ``revision_written_at`` among those entries.
    """
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
    """Persist ``manifest`` through ``provider`` and return its metadata.

    The manifest JSON is written as an object in
    :data:`REMOTE_MIRROR_MANIFEST_NAMESPACE` with a
    :func:`core.hashing.sha256_hex` content hash.

    Returns:
        The provider's :class:`ProviderObjectMetadata` for the manifest object.
    """
    payload = manifest.model_dump_json().encode("utf-8")
    return provider.put(
        REMOTE_MIRROR_MANIFEST_NAMESPACE,
        _manifest_object_key_hmac(manifest.namespace),
        payload,
        content_hash=f"sha256-{sha256_hex(payload)}",
        label=f"mirror-manifest-{_manifest_label(manifest.namespace)}",
    )


def get_remote_mirror_namespace_manifest(
    provider: StorageProvider,
    namespace: str,
) -> RemoteMirrorNamespaceManifest | None:
    """Return the stored :class:`RemoteMirrorNamespaceManifest` for ``namespace``.

    Missing manifest objects return ``None``. Malformed manifest payloads are
    translated to :class:`OutboundStorageIntegrityError` so callers can handle
    them through the :class:`adapters.outbound.storage.OutboundStorageError`
    hierarchy.
    """
    try:
        payload, _metadata = provider.get(REMOTE_MIRROR_MANIFEST_NAMESPACE, _manifest_object_key_hmac(namespace))
    except OutboundStorageNotFoundError:
        return None
    try:
        manifest = RemoteMirrorNamespaceManifest.model_validate_json(payload)
    except ValidationError as exc:
        raise OutboundStorageIntegrityError(
            f"remote mirror manifest for namespace {namespace!r} is malformed",
            context={"namespace": namespace},
            precondition_verdict=no_action_precondition_verdict(
                condition_id="storage.mirror.manifest.schema_valid",
                facts={"namespace": namespace, "manifest_valid": False},
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        ) from exc
    if manifest.manifest_schema_version != REMOTE_MIRROR_MANIFEST_SCHEMA_VERSION:
        raise OutboundStorageIntegrityError(
            f"remote mirror manifest for namespace {namespace!r} uses unsupported schema version "
            f"{manifest.manifest_schema_version}",
            context={
                "namespace": namespace,
                "manifest_schema_version": manifest.manifest_schema_version,
                "supported_manifest_schema_version": REMOTE_MIRROR_MANIFEST_SCHEMA_VERSION,
            },
            precondition_verdict=no_action_precondition_verdict(
                condition_id="storage.mirror.manifest.schema_supported",
                facts={
                    "namespace": namespace,
                    "manifest_schema_version": manifest.manifest_schema_version,
                    "supported_manifest_schema_version": REMOTE_MIRROR_MANIFEST_SCHEMA_VERSION,
                },
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        )
    return manifest


def inspect_remote_mirror_upload(
    provider: StorageProvider,
    expected_manifest: RemoteMirrorNamespaceManifest,
) -> RemoteMirrorInspection:
    """Detect remote upload drift for the expected namespace manifest.

    Returns:
        A :class:`RemoteMirrorInspection` describing the drift between the
        expected manifest and the remote mirror. Issues use
        :class:`RemoteMirrorIssueKind` values such as ``PARTIAL_UPLOAD``,
        ``STALE_MIRROR``, and ``REVISION_CONFLICT``.
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
    """Inspect whether every object in ``remote_manifest`` is downloadable.

    Missing objects, unreadable objects, integrity failures, and provider
    metadata drift are reported as ``PARTIAL_DOWNLOAD`` issues on the returned
    :class:`RemoteMirrorInspection`.
    """
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
    """Compare two namespace manifests and return a :class:`RemoteMirrorInspection`.

    The comparison classifies absent entries, stale remote revisions, and
    divergent revision lineages as :class:`RemoteMirrorIssue` records.
    """
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
        ciphertext_hash=row.ciphertext_hash or sha256_hex(row.payload),
        storage_revision_id=row.revision_id,
        previous_storage_revision_id=row.previous_revision_id,
        revision_ancestor_ids=row.revision_ancestor_ids,
        row_written_at=row.written_at,
        revision_written_at=row.revision_written_at,
    )


def _manifest_object_key_hmac(namespace: str) -> str:
    return sha256_hex(f"remote-mirror-manifest:{namespace}".encode())


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
            precondition_verdict=no_action_precondition_verdict(
                condition_id="storage.mirror.manifest.namespaces_match",
                facts={"local_namespace": local.namespace, "remote_namespace": remote.namespace},
                provenance=ActionEvidenceProvenance.APPLICATION_STATE,
                outcome=NoRecoveryOutcome.OPERATOR_DECISION,
            ),
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
            contradictory_fields = _same_revision_metadata_differences(
                local_entry=local_entry,
                remote_entry=remote_entry,
            )
            if contradictory_fields:
                issues.append(
                    RemoteMirrorIssue(
                        kind=RemoteMirrorIssueKind.REVISION_CONFLICT,
                        namespace=local.namespace,
                        object_key_hmac=object_key_hmac,
                        detail=(
                            "matching revision ids carry contradictory metadata: " + ", ".join(contradictory_fields)
                        ),
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


def _same_revision_metadata_differences(
    *,
    local_entry: RemoteMirrorObjectManifest,
    remote_entry: RemoteMirrorObjectManifest,
) -> tuple[str, ...]:
    """Return authoritative fields that cannot diverge under one revision ID."""
    compared_fields = (
        "classification",
        "schema_version",
        "byte_length",
        "ciphertext_hash",
        "previous_storage_revision_id",
        "revision_ancestor_ids",
        "row_written_at",
        "revision_written_at",
    )
    return tuple(
        field_name
        for field_name in compared_fields
        if getattr(local_entry, field_name) != getattr(remote_entry, field_name)
    )


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
        and sha256_hex(payload) == entry.ciphertext_hash
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
    """Compute the provider object key used for mirrored ciphertext rows.

    The digest combines the logical ``namespace`` and the raw secure-object
    ``object_key`` bytes so the remote provider sees only deterministic
    ciphertext object identifiers.
    """
    return sha256_hex(namespace.encode() + b"\x00" + object_key)


def remote_mirror_object_label(namespace: str) -> str:
    """Derive the human-readable half of a mirrored row's provider filename.

    A mirrored object is named ``<object-key-hmac>--<label>.bin``. The hmac half
    comes from :func:`remote_mirror_object_key_hmac`; this is the other half,
    and both are facts about the wire, not about whichever surface happens to
    push. The label is the namespace's trailing dotted segment, sanitised to
    alphanumerics, dash, underscore and dot, and capped at thirty-two
    characters, so the operator can recognise a row in a Drive listing without
    the name carrying anything the hmac exists to hide.

    Deliberately not :func:`_manifest_label`, which names the manifest FILE for
    a namespace: that one keeps the whole namespace, admits no dots or
    underscores, and allows sixty-four characters. Two names for two different
    objects, and neither policy is a superset of the other.
    """
    leaf = namespace.rsplit(".", 1)[-1] or "obj"
    safe = "".join(character if character.isalnum() or character in "-_." else "-" for character in leaf)
    return safe[:32] or "obj"


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
    "remote_mirror_object_label",
]
