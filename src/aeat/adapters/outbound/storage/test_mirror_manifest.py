"""Real-behavior tests for remote ciphertext mirror manifests."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from aeat.adapters.outbound.storage import (
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
from aeat.adapters.outbound.storage._local import LocalFileSystemProvider
from aeat.adapters.persistence.storage import EphemeralMasterKeyProvider
from aeat.adapters.persistence.storage.sql._orm import Base
from aeat.adapters.persistence.storage.sql.engine import create_engine_from_settings
from aeat.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from aeat.core.classification import SensitivityClass
from aeat.core.config import Settings

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


def test_remote_mirror_comparison_detects_stale_remote_revision(tmp_path: Path) -> None:
    remote_manifest, local_manifest = _overwrite_manifest_pair(tmp_path)

    inspection = compare_remote_mirror_manifests(local=local_manifest, remote=remote_manifest)

    assert inspection.ok is False
    assert {issue.kind for issue in inspection.issues} == {RemoteMirrorIssueKind.STALE_MIRROR}


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
