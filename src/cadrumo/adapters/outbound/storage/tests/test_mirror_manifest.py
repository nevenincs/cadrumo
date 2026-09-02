"""Real-behavior tests for remote ciphertext mirror manifests."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from .....core.directory_scan import iter_directory, scan_directory
from .....core.operator_action_enums import ActionConditionality, ActionEvidenceProvenance, NoRecoveryOutcome
from .....tests.secure_sql import isolated_runtime_profile
from ....persistence.storage.namespace_registry import STORAGE_NAMESPACE_REGISTRY
from ....persistence.storage.namespace_taxonomy import StorageRemoteMirrorPolicy
from ..errors import OutboundStorageIntegrityError
from ..local import LocalFileSystemProvider
from ..mirror_manifest import (
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
from ..records import RemoteMirrorIssueKind, RemoteMirrorNamespaceManifest

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _assert_manifest_verdict(verdict, condition_id: str, facts: dict[str, object], outcome: NoRecoveryOutcome) -> None:
    assert verdict.failed_condition_id == condition_id
    assert verdict.action is None
    assert verdict.argument_bindings == ()
    assert verdict.conditionality is ActionConditionality.NOT_APPLICABLE
    assert verdict.no_recovery_outcome is outcome
    assert len(verdict.evidence) == 1
    evidence = verdict.evidence[0]
    assert evidence.evidence_id == f"{condition_id}.observation"
    assert evidence.provenance in (
        ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        ActionEvidenceProvenance.APPLICATION_STATE,
    )
    assert dict(evidence.values) == facts


def test_remote_mirror_manifest_persists_ciphertext_hashes_and_revision_watermark(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="6587f6e5-3b48-4347-ad19-2f0b297786e8") as profile:
        repo = profile.repository
        namespace_definition = STORAGE_NAMESPACE_REGISTRY.namespace_by_key("google_oauth_metadata")
        namespace = namespace_definition.namespace
        first_written_at = datetime(2026, 5, 28, 10, 0, tzinfo=UTC)
        second_written_at = first_written_at + timedelta(minutes=1)
        repo.save(
            namespace=namespace,
            object_key="first-object",
            classification=namespace_definition.sensitivity,
            schema_version=1,
            written_at=first_written_at,
            payload=b"first-plaintext-payload",
        )
        repo.save(
            namespace=namespace,
            object_key="second-object",
            classification=namespace_definition.sensitivity,
            schema_version=1,
            written_at=second_written_at,
            payload=b"second-plaintext-payload",
        )

        raw_rows = tuple(repo.iter_all_records_raw())
        manifest = build_remote_mirror_namespace_manifest(namespace, raw_rows)
        mirror_provider = LocalFileSystemProvider(tmp_path / "mirror")
        metadata = put_remote_mirror_namespace_manifest(mirror_provider, manifest)
        payload, _ = mirror_provider.get(REMOTE_MIRROR_MANIFEST_NAMESPACE, metadata.object_key_hmac)
        reloaded = RemoteMirrorNamespaceManifest.model_validate_json(payload)

        assert reloaded == manifest
        assert reloaded.object_count == 2
        assert b"first-plaintext-payload" not in payload
        assert b"second-plaintext-payload" not in payload

        raw_by_key_hmac = {remote_mirror_object_key_hmac(row.namespace, row.object_key): row for row in raw_rows}
        for entry in reloaded.objects:
            raw = raw_by_key_hmac[entry.object_key_hmac]
            assert entry.ciphertext_hash == hashlib.sha256(raw.payload).hexdigest()
            assert entry.ciphertext_hash != hashlib.sha256(b"first-plaintext-payload").hexdigest()
            assert entry.ciphertext_hash != hashlib.sha256(b"second-plaintext-payload").hexdigest()
            assert entry.storage_revision_id == raw.revision_id
            assert entry.revision_ancestor_ids == raw.revision_ancestor_ids
            assert entry.revision_written_at == raw.revision_written_at

        latest_entry = max(
            reloaded.objects,
            key=lambda entry: entry.revision_written_at or datetime.min.replace(tzinfo=UTC),
        )
        assert reloaded.latest_revision_id == latest_entry.storage_revision_id
        assert reloaded.latest_revision_written_at == latest_entry.revision_written_at


# Each case needs its OWN bucket identity, and a profile identity is a canonical
# UUIDv4 -- a descriptive slug is refused at provisioning, and a derived uuid5 is
# refused for its version. So they are fixed literals, one per case.
@pytest.mark.parametrize(
    ("namespace_key", "plaintext", "bucket_id"),
    (
        pytest.param(
            "google_oauth_client",
            b"oauth client secret that must never reach the remote mirror",
            "0f5cf7d0-9f8e-4b17-9a3d-6c1f2e8a4b71",
            id="oauth-client",
        ),
        pytest.param(
            "google_oauth_token",
            b"oauth refresh token that must never reach the remote mirror",
            "1b6da8e1-3c2f-4d5a-8e7b-9f0a1c2d3e4f",
            id="oauth-token",
        ),
        pytest.param(
            "google_oauth_metadata",
            b"operator metadata that must never reach the remote mirror",
            "2c7eb9f2-4d3a-4e6b-9f8c-0a1b2c3d4e5f",
            id="oauth-metadata",
        ),
    ),
)
def test_remote_mirror_inspections_accept_opaque_encrypted_payload_round_trip(
    tmp_path: Path,
    namespace_key: str,
    plaintext: bytes,
    bucket_id: str,
) -> None:
    case_root = tmp_path / namespace_key
    with isolated_runtime_profile(tmp_path=case_root, bucket_id=bucket_id) as profile:
        repo = profile.repository
        namespace_definition = STORAGE_NAMESPACE_REGISTRY.namespace_by_key(namespace_key)
        namespace = namespace_definition.namespace
        plaintext_text = plaintext.decode()
        repo.save(
            namespace=namespace,
            object_key="opaque-object",
            classification=namespace_definition.sensitivity,
            schema_version=1,
            written_at=datetime(2026, 6, 2, 8, 0, tzinfo=UTC),
            payload=plaintext,
        )
        # Select by namespace rather than taking the first raw row: the runtime
        # profile fixture writes its own profile-value and bucket-event rows
        # before this one, and the manifest builder discards foreign rows, so
        # a positional pick yields an empty manifest that reaches no subject.
        raw_row = next(row for row in repo.iter_all_records_raw() if row.namespace == namespace)
        manifest = build_remote_mirror_namespace_manifest(namespace, (raw_row,))
        entry = manifest.objects[0]
        mirror_provider = LocalFileSystemProvider(case_root / "mirror")

        mirror_provider.put(
            entry.namespace,
            entry.object_key_hmac,
            raw_row.payload,
            content_hash=f"sha256-{hashlib.sha256(raw_row.payload).hexdigest()}",
            label="opaque-object",
        )
        manifest_metadata = put_remote_mirror_namespace_manifest(mirror_provider, manifest)
        mirrored_payload, mirrored_metadata = mirror_provider.get(entry.namespace, entry.object_key_hmac)
        manifest_payload, _ = mirror_provider.get(
            REMOTE_MIRROR_MANIFEST_NAMESPACE,
            manifest_metadata.object_key_hmac,
        )

        assert raw_row.payload != plaintext
        assert namespace_definition.remote_mirror_policy is StorageRemoteMirrorPolicy.CIPHERTEXT_WITH_METADATA
        assert namespace_definition.remote_mirror_requires_revision is True
        assert namespace_definition.remote_mirror_requires_integrity_manifest is True
        assert plaintext not in raw_row.payload
        assert mirrored_payload == raw_row.payload
        assert plaintext not in mirrored_payload
        assert plaintext not in manifest_payload
        for artifact in scan_directory(mirror_provider.root, recursive=True):
            assert plaintext_text not in artifact.relative_to(mirror_provider.root).as_posix()
            if artifact.is_file():
                assert plaintext not in artifact.read_bytes()
        assert mirrored_metadata.content_hash == f"sha256-{entry.ciphertext_hash}"
        assert inspect_remote_mirror_upload(mirror_provider, manifest).ok is True
        assert inspect_remote_mirror_download(mirror_provider, manifest).ok is True


def test_remote_mirror_upload_inspection_detects_missing_ciphertext_object(tmp_path: Path) -> None:
    manifest = _single_object_manifest(tmp_path)
    provider = LocalFileSystemProvider(tmp_path / "mirror")
    put_remote_mirror_namespace_manifest(provider, manifest)

    inspection = inspect_remote_mirror_upload(provider, manifest)

    assert inspection.ok is False
    assert {issue.kind for issue in inspection.issues} == {RemoteMirrorIssueKind.PARTIAL_UPLOAD}


def test_remote_mirror_download_inspection_detects_missing_manifest_object(tmp_path: Path) -> None:
    manifest = _single_object_manifest(tmp_path)
    provider = LocalFileSystemProvider(tmp_path / "mirror")

    inspection = inspect_remote_mirror_download(provider, manifest)

    assert inspection.ok is False
    assert {issue.kind for issue in inspection.issues} == {RemoteMirrorIssueKind.PARTIAL_DOWNLOAD}


def test_remote_mirror_download_inspection_detects_ciphertext_drift(tmp_path: Path) -> None:
    manifest = _single_object_manifest(tmp_path)
    entry = manifest.objects[0]
    provider = LocalFileSystemProvider(tmp_path / "mirror")
    drifted_payload = b"drifted-ciphertext"
    provider.put(
        entry.namespace,
        entry.object_key_hmac,
        drifted_payload,
        content_hash=f"sha256-{hashlib.sha256(drifted_payload).hexdigest()}",
        label="drifted",
    )

    inspection = inspect_remote_mirror_download(provider, manifest)

    assert inspection.ok is False
    assert {issue.kind for issue in inspection.issues} == {RemoteMirrorIssueKind.PARTIAL_DOWNLOAD}


def test_remote_mirror_download_inspection_detects_provider_metadata_byte_length_drift(tmp_path: Path) -> None:
    manifest, payload = _single_object_manifest_with_payload(tmp_path)
    entry = manifest.objects[0]
    provider = LocalFileSystemProvider(tmp_path / "mirror")
    provider.put(
        entry.namespace,
        entry.object_key_hmac,
        payload,
        content_hash=f"sha256-{hashlib.sha256(payload).hexdigest()}",
        label="metadata-drift",
    )
    drifted_sidecar = _rewrite_local_provider_sidecar(
        provider,
        entry.namespace,
        update={"byte_length": len(payload) + 1},
    )
    assert drifted_sidecar["content_hash"] == f"sha256-{hashlib.sha256(payload).hexdigest()}"

    inspection = inspect_remote_mirror_download(provider, manifest)

    assert inspection.ok is False
    assert {issue.kind for issue in inspection.issues} == {RemoteMirrorIssueKind.PARTIAL_DOWNLOAD}


def test_remote_mirror_upload_inspection_detects_provider_metadata_byte_length_drift(tmp_path: Path) -> None:
    manifest, payload = _single_object_manifest_with_payload(tmp_path)
    entry = manifest.objects[0]
    provider = LocalFileSystemProvider(tmp_path / "mirror")
    provider.put(
        entry.namespace,
        entry.object_key_hmac,
        payload,
        content_hash=f"sha256-{hashlib.sha256(payload).hexdigest()}",
        label="metadata-drift",
    )
    put_remote_mirror_namespace_manifest(provider, manifest)
    _rewrite_local_provider_sidecar(
        provider,
        entry.namespace,
        update={"byte_length": len(payload) + 1},
    )

    inspection = inspect_remote_mirror_upload(provider, manifest)

    assert inspection.ok is False
    assert {issue.kind for issue in inspection.issues} == {RemoteMirrorIssueKind.PARTIAL_UPLOAD}


def test_remote_mirror_manifest_loader_wraps_malformed_payload_in_storage_error(tmp_path: Path) -> None:
    manifest = _single_object_manifest(tmp_path)
    provider = LocalFileSystemProvider(tmp_path / "mirror")
    manifest_metadata = put_remote_mirror_namespace_manifest(provider, manifest)
    malformed_payload = b'{"manifest_schema_version": 1, "namespace": 3}'
    provider.put(
        REMOTE_MIRROR_MANIFEST_NAMESPACE,
        manifest_metadata.object_key_hmac,
        malformed_payload,
        content_hash=f"sha256-{hashlib.sha256(malformed_payload).hexdigest()}",
        label="malformed",
    )

    with pytest.raises(OutboundStorageIntegrityError, match="remote mirror manifest") as raised:
        get_remote_mirror_namespace_manifest(provider, manifest.namespace)
    _assert_manifest_verdict(
        raised.value.terminal_precondition_verdict,
        "storage.mirror.manifest.schema_valid",
        {"namespace": manifest.namespace, "manifest_valid": False},
        NoRecoveryOutcome.SAFETY,
    )


def test_remote_mirror_manifest_loader_refuses_unsupported_schema_version(tmp_path: Path) -> None:
    """A future manifest must not reach mirror comparison before enrollment."""
    manifest = _single_object_manifest(tmp_path)
    provider = LocalFileSystemProvider(tmp_path / "mirror")
    manifest_metadata = put_remote_mirror_namespace_manifest(provider, manifest)
    unsupported_schema_version = REMOTE_MIRROR_MANIFEST_SCHEMA_VERSION + 1
    future_payload = json.dumps(
        json.loads(manifest.model_dump_json()) | {"manifest_schema_version": unsupported_schema_version},
    ).encode("utf-8")
    provider.put(
        REMOTE_MIRROR_MANIFEST_NAMESPACE,
        manifest_metadata.object_key_hmac,
        future_payload,
        content_hash=f"sha256-{hashlib.sha256(future_payload).hexdigest()}",
        label="future-schema-version",
    )

    with pytest.raises(OutboundStorageIntegrityError, match="unsupported schema version") as error:
        get_remote_mirror_namespace_manifest(provider, manifest.namespace)

    assert error.value.context == {
        "namespace": manifest.namespace,
        "manifest_schema_version": unsupported_schema_version,
        "supported_manifest_schema_version": REMOTE_MIRROR_MANIFEST_SCHEMA_VERSION,
    }
    _assert_manifest_verdict(
        error.value.terminal_precondition_verdict,
        "storage.mirror.manifest.schema_supported",
        {
            "namespace": manifest.namespace,
            "manifest_schema_version": unsupported_schema_version,
            "supported_manifest_schema_version": REMOTE_MIRROR_MANIFEST_SCHEMA_VERSION,
        },
        NoRecoveryOutcome.SAFETY,
    )


def test_duplicate_object_keys_in_a_remote_manifest_fail_closed_on_load(tmp_path: Path) -> None:
    """A conflicting duplicate row must refuse rather than be discarded by keyed comparison.

    Comparison keys both manifests by ``object_key_hmac``; before the manifest
    enforced uniqueness a repeated key silently dropped every earlier row, so a
    remote manifest carrying a revision conflict followed by a matching row
    compared clean while still reporting two objects.
    """
    manifest = _single_object_manifest(tmp_path)
    provider = LocalFileSystemProvider(tmp_path / "mirror")
    manifest_metadata = put_remote_mirror_namespace_manifest(provider, manifest)

    original = json.loads(manifest.model_dump_json())
    conflicting_entry = dict(original["objects"][0])
    conflicting_entry["ciphertext_hash"] = "c" * 64
    tampered = dict(original)
    tampered["objects"] = [conflicting_entry, original["objects"][0]]
    tampered["object_count"] = 2
    tampered_payload = json.dumps(tampered).encode("utf-8")

    provider.put(
        REMOTE_MIRROR_MANIFEST_NAMESPACE,
        manifest_metadata.object_key_hmac,
        tampered_payload,
        content_hash=f"sha256-{hashlib.sha256(tampered_payload).hexdigest()}",
        label="duplicate-keys",
    )

    with pytest.raises(OutboundStorageIntegrityError, match="remote mirror manifest"):
        get_remote_mirror_namespace_manifest(provider, manifest.namespace)


def test_remote_mirror_manifest_object_count_must_match_recorded_objects(tmp_path: Path) -> None:
    """``object_count`` is the manifest's own claim about ``objects`` and must agree with it."""
    manifest = _single_object_manifest(tmp_path)

    payload = json.loads(manifest.model_dump_json())
    assert payload["object_count"] == 1

    with pytest.raises(ValidationError, match="object_count"):
        RemoteMirrorNamespaceManifest.model_validate_json(json.dumps(payload | {"object_count": 7}))


def test_remote_mirror_comparison_detects_stale_remote_revision(tmp_path: Path) -> None:
    remote_manifest, local_manifest = _overwrite_manifest_pair(tmp_path)

    inspection = compare_remote_mirror_manifests(local=local_manifest, remote=remote_manifest)

    assert inspection.ok is False
    assert {issue.kind for issue in inspection.issues} == {RemoteMirrorIssueKind.STALE_MIRROR}


def test_remote_mirror_comparison_detects_older_stale_remote_revision(tmp_path: Path) -> None:
    remote_manifest, local_manifest = _three_revision_manifest_pair(tmp_path)

    inspection = compare_remote_mirror_manifests(local=local_manifest, remote=remote_manifest)

    assert inspection.ok is False
    assert {issue.kind for issue in inspection.issues} == {RemoteMirrorIssueKind.STALE_MIRROR}


def test_remote_mirror_comparison_detects_naive_older_stale_remote_revision(tmp_path: Path) -> None:
    remote_manifest, local_manifest = _three_revision_manifest_pair(tmp_path)
    remote_object = remote_manifest.objects[0]
    assert remote_object.revision_written_at is not None
    naive_remote_object = remote_object.model_copy(
        update={
            "revision_written_at": remote_object.revision_written_at.replace(tzinfo=None),
        },
    )
    naive_remote_manifest = remote_manifest.model_copy(update={"objects": (naive_remote_object,)})

    inspection = compare_remote_mirror_manifests(local=local_manifest, remote=naive_remote_manifest)

    assert inspection.ok is False
    assert {issue.kind for issue in inspection.issues} == {RemoteMirrorIssueKind.STALE_MIRROR}


def test_remote_mirror_comparison_keeps_unknown_older_root_revision_conflict(tmp_path: Path) -> None:
    _remote_manifest, local_manifest = _three_revision_manifest_pair(tmp_path)
    local_object = local_manifest.objects[0]
    assert local_object.revision_written_at is not None
    unknown_root_object = local_object.model_copy(
        update={
            "storage_revision_id": "f" * 64,
            "previous_storage_revision_id": None,
            "revision_ancestor_ids": (),
            "ciphertext_hash": "d" * 64,
            "revision_written_at": local_object.revision_written_at - timedelta(minutes=5),
        },
    )
    unknown_root_manifest = local_manifest.model_copy(update={"objects": (unknown_root_object,)})

    inspection = compare_remote_mirror_manifests(local=local_manifest, remote=unknown_root_manifest)

    assert inspection.ok is False
    assert {issue.kind for issue in inspection.issues} == {RemoteMirrorIssueKind.REVISION_CONFLICT}


def test_remote_mirror_comparison_keeps_older_divergent_revision_conflict(tmp_path: Path) -> None:
    _remote_manifest, local_manifest = _overwrite_manifest_pair(tmp_path)
    local_object = local_manifest.objects[0]
    assert local_object.revision_written_at is not None
    divergent_object = local_object.model_copy(
        update={
            "storage_revision_id": "f" * 64,
            "previous_storage_revision_id": "e" * 64,
            "ciphertext_hash": "d" * 64,
            "revision_written_at": local_object.revision_written_at - timedelta(minutes=5),
        },
    )
    divergent_manifest = local_manifest.model_copy(update={"objects": (divergent_object,)})

    inspection = compare_remote_mirror_manifests(local=local_manifest, remote=divergent_manifest)

    assert inspection.ok is False
    assert {issue.kind for issue in inspection.issues} == {RemoteMirrorIssueKind.REVISION_CONFLICT}


def test_remote_mirror_comparison_detects_revision_conflict(tmp_path: Path) -> None:
    _remote_manifest, local_manifest = _overwrite_manifest_pair(tmp_path)
    conflicted_object = local_manifest.objects[0].model_copy(
        update={
            "storage_revision_id": "f" * 64,
            "previous_storage_revision_id": "e" * 64,
            "ciphertext_hash": "d" * 64,
        },
    )
    conflicted_manifest = local_manifest.model_copy(
        update={
            "latest_revision_id": conflicted_object.storage_revision_id,
            "objects": (conflicted_object,),
        },
    )

    inspection = compare_remote_mirror_manifests(local=local_manifest, remote=conflicted_manifest)

    assert inspection.ok is False
    assert {issue.kind for issue in inspection.issues} == {RemoteMirrorIssueKind.REVISION_CONFLICT}


def test_remote_mirror_comparison_refuses_same_revision_with_contradictory_metadata(tmp_path: Path) -> None:
    """One revision ID cannot authoritatively describe two different object records."""
    local_manifest = _single_object_manifest(tmp_path)
    local_entry = local_manifest.objects[0]
    assert local_entry.revision_written_at is not None
    contradictory_entry = type(local_entry).model_validate(
        local_entry.model_dump()
        | {
            "classification": "contradictory-classification",
            "schema_version": local_entry.schema_version + 1,
            "byte_length": local_entry.byte_length + 1,
            "previous_storage_revision_id": "b" * 64,
            "revision_ancestor_ids": ("c" * 64,),
            "row_written_at": local_entry.row_written_at + timedelta(seconds=1),
            "revision_written_at": local_entry.revision_written_at + timedelta(seconds=1),
        }
    )
    contradictory_manifest = local_manifest.model_copy(update={"objects": (contradictory_entry,)})

    inspection = compare_remote_mirror_manifests(local=local_manifest, remote=contradictory_manifest)

    assert inspection.ok is False
    assert {issue.kind for issue in inspection.issues} == {RemoteMirrorIssueKind.REVISION_CONFLICT}
    assert inspection.issues[0].detail == (
        "matching revision ids carry contradictory metadata: "
        "classification, schema_version, byte_length, previous_storage_revision_id, "
        "revision_ancestor_ids, row_written_at, revision_written_at"
    )


def _single_object_manifest(tmp_path: Path) -> RemoteMirrorNamespaceManifest:
    manifest, _payload = _single_object_manifest_with_payload(tmp_path)
    return manifest


def _single_object_manifest_with_payload(tmp_path: Path) -> tuple[RemoteMirrorNamespaceManifest, bytes]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="aef4bd4b-2a08-454e-9e46-ad76d1928ac7") as profile:
        repo = profile.repository
        namespace_definition = STORAGE_NAMESPACE_REGISTRY.namespace_by_key("google_oauth_metadata")
        namespace = namespace_definition.namespace
        repo.save(
            namespace=namespace,
            object_key="single-object",
            classification=namespace_definition.sensitivity,
            schema_version=1,
            written_at=datetime(2026, 5, 28, 10, 0, tzinfo=UTC),
            payload=b"single-plaintext-payload",
        )
        # Select by namespace rather than taking the first raw row: the runtime
        # profile fixture writes its own profile-value and bucket-event rows
        # before this one, and the manifest builder discards foreign rows, so
        # a positional pick yields an empty manifest that reaches no subject.
        raw_row = next(row for row in repo.iter_all_records_raw() if row.namespace == namespace)
        manifest = build_remote_mirror_namespace_manifest(namespace, (raw_row,))
        # An empty manifest is the failure this helper must never hand out. A
        # count comparison over zero objects, a drift check with nothing to
        # drift, a duplicate-key check with no key -- each passes vacuously and
        # reads as coverage. Only the tests that INDEX an object noticed.
        assert manifest.objects, "fixture built a manifest with no objects; no test below reaches its subject"
        return manifest, raw_row.payload


def _rewrite_local_provider_sidecar(
    provider: LocalFileSystemProvider,
    namespace: str,
    *,
    update: dict[str, object],
) -> dict[str, object]:
    sidecar_path = next(iter_directory(provider.root / namespace, pattern="*.meta.json"))
    raw_sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert isinstance(raw_sidecar, dict)
    sidecar: dict[str, object] = {}
    for key, value in raw_sidecar.items():
        assert isinstance(key, str)
        sidecar[key] = value
    sidecar.update(update)
    sidecar_path.write_text(json.dumps(sidecar, sort_keys=True), encoding="utf-8")
    return sidecar


def _overwrite_manifest_pair(tmp_path: Path) -> tuple[RemoteMirrorNamespaceManifest, RemoteMirrorNamespaceManifest]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="84dd214d-8ad6-4e98-81b4-435834004934") as profile:
        repo = profile.repository
        namespace_definition = STORAGE_NAMESPACE_REGISTRY.namespace_by_key("google_oauth_metadata")
        namespace = namespace_definition.namespace
        repo.save(
            namespace=namespace,
            object_key="same-object",
            classification=namespace_definition.sensitivity,
            schema_version=1,
            written_at=datetime(2026, 5, 28, 10, 0, tzinfo=UTC),
            payload=b"first-payload",
        )
        remote_manifest = build_remote_mirror_namespace_manifest(namespace, tuple(repo.iter_all_records_raw()))
        repo.save(
            namespace=namespace,
            object_key="same-object",
            classification=namespace_definition.sensitivity,
            schema_version=1,
            written_at=datetime(2026, 5, 28, 10, 1, tzinfo=UTC),
            payload=b"second-payload",
        )
        local_manifest = build_remote_mirror_namespace_manifest(namespace, tuple(repo.iter_all_records_raw()))
        return remote_manifest, local_manifest


def _three_revision_manifest_pair(
    tmp_path: Path,
) -> tuple[RemoteMirrorNamespaceManifest, RemoteMirrorNamespaceManifest]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="17368978-486e-4c41-9793-75a649bafb8b") as profile:
        repo = profile.repository
        namespace_definition = STORAGE_NAMESPACE_REGISTRY.namespace_by_key("google_oauth_metadata")
        namespace = namespace_definition.namespace
        remote_manifest: RemoteMirrorNamespaceManifest | None = None
        for offset, payload in enumerate((b"first-payload", b"second-payload", b"third-payload")):
            repo.save(
                namespace=namespace,
                object_key="same-object",
                classification=namespace_definition.sensitivity,
                schema_version=1,
                written_at=datetime(2026, 5, 28, 10, offset, tzinfo=UTC),
                payload=payload,
            )
            if offset == 0:
                remote_manifest = build_remote_mirror_namespace_manifest(
                    namespace,
                    tuple(repo.iter_all_records_raw()),
                )
        assert remote_manifest is not None
        local_manifest = build_remote_mirror_namespace_manifest(namespace, tuple(repo.iter_all_records_raw()))
        return remote_manifest, local_manifest


def test_manifest_refuses_child_objects_from_another_namespace() -> None:
    """A manifest describes one namespace, so a foreign child is not representable.

    Each child entry carries its own ``namespace`` and nothing bound it to the
    parent's, while ``inspect_remote_mirror_download`` fetches by the *child's*
    value. A manifest named ``target`` holding a child named ``foreign`` therefore
    inspected clean and would pull another namespace's ciphertext under the
    target's identity.
    """
    from ..records import RemoteMirrorObjectManifest

    def _entry(namespace: str) -> RemoteMirrorObjectManifest:
        return RemoteMirrorObjectManifest(
            namespace=namespace,
            object_key_hmac="a" * 64,
            classification="FINANCIAL",
            schema_version=1,
            byte_length=10,
            ciphertext_hash="b" * 64,
            row_written_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

    with pytest.raises(ValidationError, match="foreign namespaces"):
        RemoteMirrorNamespaceManifest(
            manifest_schema_version=REMOTE_MIRROR_MANIFEST_SCHEMA_VERSION,
            namespace="target",
            object_count=1,
            objects=(_entry("foreign"),),
        )

    # The matching-namespace manifest is unaffected.
    manifest = RemoteMirrorNamespaceManifest(
        manifest_schema_version=REMOTE_MIRROR_MANIFEST_SCHEMA_VERSION,
        namespace="target",
        object_count=1,
        objects=(_entry("target"),),
    )
    assert manifest.objects[0].namespace == manifest.namespace


def test_manifest_refuses_a_mixed_namespace_object_set() -> None:
    """One foreign child among genuine ones is refused, and the refusal names it."""
    from ..records import RemoteMirrorObjectManifest

    def _entry(namespace: str, key_char: str) -> RemoteMirrorObjectManifest:
        return RemoteMirrorObjectManifest(
            namespace=namespace,
            object_key_hmac=key_char * 64,
            classification="FINANCIAL",
            schema_version=1,
            byte_length=10,
            ciphertext_hash="b" * 64,
            row_written_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

    with pytest.raises(ValidationError, match="smuggled"):
        RemoteMirrorNamespaceManifest(
            manifest_schema_version=REMOTE_MIRROR_MANIFEST_SCHEMA_VERSION,
            namespace="target",
            object_count=2,
            objects=(_entry("target", "a"), _entry("smuggled", "c")),
        )


def test_namespace_mismatch_is_an_explicit_operator_decision_verdict(tmp_path: Path) -> None:
    local = _single_object_manifest(tmp_path)
    remote = local.model_copy(update={"namespace": "other-namespace"})
    from ..errors import OutboundStorageValidationError

    with pytest.raises(OutboundStorageValidationError) as raised:
        compare_remote_mirror_manifests(local=local, remote=remote)
    _assert_manifest_verdict(
        raised.value.terminal_precondition_verdict,
        "storage.mirror.manifest.namespaces_match",
        {"local_namespace": local.namespace, "remote_namespace": remote.namespace},
        NoRecoveryOutcome.OPERATOR_DECISION,
    )
