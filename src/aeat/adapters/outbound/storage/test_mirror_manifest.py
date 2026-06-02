"""Real-behavior tests for remote ciphertext mirror manifests."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ....core.classification import SensitivityClass
from ....core.config import Settings
from ...persistence.storage import STORAGE_NAMESPACE_REGISTRY, EphemeralMasterKeyProvider, StorageRemoteMirrorPolicy
from ...persistence.storage.sql._orm import Base
from ...persistence.storage.sql.engine import create_engine_from_settings
from ...persistence.storage.sql.secure_objects import SecureObjectRepository
from . import (
    REMOTE_MIRROR_MANIFEST_NAMESPACE,
    RemoteMirrorIssueKind,
    RemoteMirrorNamespaceManifest,
    build_remote_mirror_namespace_manifest,
    compare_remote_mirror_manifests,
    inspect_remote_mirror_download,
    inspect_remote_mirror_upload,
    put_remote_mirror_namespace_manifest,
    remote_mirror_object_key_hmac,
)
from ._local import LocalFileSystemProvider

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]


def test_remote_mirror_manifest_persists_ciphertext_hashes_and_revision_watermark(tmp_path: Path) -> None:
    provider = EphemeralMasterKeyProvider()
    with provider:
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{(tmp_path / 'secure-objects.db').as_posix()}"),
        )
        Base.metadata.create_all(engine)
        try:
            repo = SecureObjectRepository(engine=engine)
            namespace = "aeat.remote.mirror.fixture"
            first_written_at = datetime(2026, 5, 28, 10, 0, tzinfo=UTC)
            second_written_at = first_written_at + timedelta(minutes=1)
            repo.save(
                namespace=namespace,
                object_key="first-object",
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=first_written_at,
                payload=b"first-plaintext-payload",
            )
            repo.save(
                namespace=namespace,
                object_key="second-object",
                classification=SensitivityClass.FINANCIAL,
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
                assert entry.revision_written_at == raw.revision_written_at

            latest_entry = max(
                reloaded.objects,
                key=lambda entry: entry.revision_written_at or datetime.min.replace(tzinfo=UTC),
            )
            assert reloaded.latest_revision_id == latest_entry.storage_revision_id
            assert reloaded.latest_revision_written_at == latest_entry.revision_written_at
        finally:
            engine.dispose()


def test_remote_mirror_inspections_accept_opaque_encrypted_payload_round_trip(tmp_path: Path) -> None:
    provider = EphemeralMasterKeyProvider()
    with provider:
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{(tmp_path / 'opaque-round-trip.db').as_posix()}"),
        )
        Base.metadata.create_all(engine)
        try:
            repo = SecureObjectRepository(engine=engine, namespace_registry=STORAGE_NAMESPACE_REGISTRY)
            namespace_definition = STORAGE_NAMESPACE_REGISTRY.namespace_by_key("google_oauth_metadata")
            namespace = namespace_definition.namespace
            plaintext = b"operator plaintext that must never reach the remote mirror"
            plaintext_text = plaintext.decode()
            repo.save(
                namespace=namespace,
                object_key="opaque-object",
                classification=namespace_definition.sensitivity,
                schema_version=1,
                written_at=datetime(2026, 6, 2, 8, 0, tzinfo=UTC),
                payload=plaintext,
            )
            raw_row = next(repo.iter_all_records_raw())
            manifest = build_remote_mirror_namespace_manifest(namespace, (raw_row,))
            entry = manifest.objects[0]
            mirror_provider = LocalFileSystemProvider(tmp_path / "mirror")

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
            for artifact in mirror_provider.root.rglob("*"):
                assert plaintext_text not in artifact.relative_to(mirror_provider.root).as_posix()
                if artifact.is_file():
                    assert plaintext not in artifact.read_bytes()
            assert mirrored_metadata.content_hash == f"sha256-{entry.ciphertext_hash}"
            assert inspect_remote_mirror_upload(mirror_provider, manifest).ok is True
            assert inspect_remote_mirror_download(mirror_provider, manifest).ok is True
        finally:
            engine.dispose()


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


def test_remote_mirror_comparison_handles_naive_stale_revision_timestamp(tmp_path: Path) -> None:
    remote_manifest, local_manifest = _three_revision_manifest_pair(tmp_path)
    remote_object = remote_manifest.objects[0]
    naive_remote_object = remote_object.model_copy(
        update={
            "revision_written_at": remote_object.revision_written_at.replace(tzinfo=None),
        }
    )
    naive_remote_manifest = remote_manifest.model_copy(update={"objects": (naive_remote_object,)})

    inspection = compare_remote_mirror_manifests(local=local_manifest, remote=naive_remote_manifest)

    assert inspection.ok is False
    assert {issue.kind for issue in inspection.issues} == {RemoteMirrorIssueKind.STALE_MIRROR}


def test_remote_mirror_comparison_keeps_older_divergent_revision_conflict(tmp_path: Path) -> None:
    _remote_manifest, local_manifest = _overwrite_manifest_pair(tmp_path)
    local_object = local_manifest.objects[0]
    divergent_object = local_object.model_copy(
        update={
            "storage_revision_id": "f" * 64,
            "previous_storage_revision_id": "e" * 64,
            "ciphertext_hash": "d" * 64,
            "revision_written_at": local_object.revision_written_at - timedelta(minutes=5),
        }
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
        }
    )
    conflicted_manifest = local_manifest.model_copy(
        update={
            "latest_revision_id": conflicted_object.storage_revision_id,
            "objects": (conflicted_object,),
        }
    )

    inspection = compare_remote_mirror_manifests(local=local_manifest, remote=conflicted_manifest)

    assert inspection.ok is False
    assert {issue.kind for issue in inspection.issues} == {RemoteMirrorIssueKind.REVISION_CONFLICT}


def _single_object_manifest(tmp_path: Path) -> RemoteMirrorNamespaceManifest:
    provider = EphemeralMasterKeyProvider()
    with provider:
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{(tmp_path / 'single-object.db').as_posix()}"),
        )
        Base.metadata.create_all(engine)
        try:
            repo = SecureObjectRepository(engine=engine)
            namespace = "aeat.remote.mirror.single"
            repo.save(
                namespace=namespace,
                object_key="single-object",
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime(2026, 5, 28, 10, 0, tzinfo=UTC),
                payload=b"single-plaintext-payload",
            )
            return build_remote_mirror_namespace_manifest(namespace, tuple(repo.iter_all_records_raw()))
        finally:
            engine.dispose()


def _overwrite_manifest_pair(tmp_path: Path) -> tuple[RemoteMirrorNamespaceManifest, RemoteMirrorNamespaceManifest]:
    provider = EphemeralMasterKeyProvider()
    with provider:
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{(tmp_path / 'overwrite.db').as_posix()}"),
        )
        Base.metadata.create_all(engine)
        try:
            repo = SecureObjectRepository(engine=engine)
            namespace = "aeat.remote.mirror.overwrite"
            repo.save(
                namespace=namespace,
                object_key="same-object",
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime(2026, 5, 28, 10, 0, tzinfo=UTC),
                payload=b"first-payload",
            )
            remote_manifest = build_remote_mirror_namespace_manifest(namespace, tuple(repo.iter_all_records_raw()))
            repo.save(
                namespace=namespace,
                object_key="same-object",
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime(2026, 5, 28, 10, 1, tzinfo=UTC),
                payload=b"second-payload",
            )
            local_manifest = build_remote_mirror_namespace_manifest(namespace, tuple(repo.iter_all_records_raw()))
            return remote_manifest, local_manifest
        finally:
            engine.dispose()


def _three_revision_manifest_pair(
    tmp_path: Path,
) -> tuple[RemoteMirrorNamespaceManifest, RemoteMirrorNamespaceManifest]:
    provider = EphemeralMasterKeyProvider()
    with provider:
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{(tmp_path / 'three-revisions.db').as_posix()}"),
        )
        Base.metadata.create_all(engine)
        try:
            repo = SecureObjectRepository(engine=engine)
            namespace = "aeat.remote.mirror.three.revisions"
            for offset, payload in enumerate((b"first-payload", b"second-payload", b"third-payload")):
                repo.save(
                    namespace=namespace,
                    object_key="same-object",
                    classification=SensitivityClass.FINANCIAL,
                    schema_version=1,
                    written_at=datetime(2026, 5, 28, 10, offset, tzinfo=UTC),
                    payload=payload,
                )
                if offset == 0:
                    remote_manifest = build_remote_mirror_namespace_manifest(
                        namespace,
                        tuple(repo.iter_all_records_raw()),
                    )
            local_manifest = build_remote_mirror_namespace_manifest(namespace, tuple(repo.iter_all_records_raw()))
            return remote_manifest, local_manifest
        finally:
            engine.dispose()
