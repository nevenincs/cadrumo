"""Real-behavior coverage for Google sync push mirror semantics."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.outbound.storage import (
    REMOTE_MIRROR_MANIFEST_NAMESPACE,
    OutboundStorageValidationError,
    RemoteMirrorNamespaceManifest,
    build_remote_mirror_namespace_manifest,
    put_remote_mirror_namespace_manifest,
    remote_mirror_object_key_hmac,
)
from ....adapters.outbound.storage._local import LocalFileSystemProvider
from ....adapters.persistence.storage import EphemeralMasterKeyProvider
from ....adapters.persistence.storage.sql._orm import Base
from ....adapters.persistence.storage.sql.engine import create_engine_from_settings
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....core.classification import SensitivityClass
from ....core.config import Settings
from ._google import _push_secure_object_mirror_rows

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]


def test_google_sync_push_persists_manifest_matching_uploaded_ciphertext_objects(tmp_path: Path) -> None:
    key_provider = EphemeralMasterKeyProvider()
    with key_provider:
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{(tmp_path / 'push.db').as_posix()}"),
        )
        Base.metadata.create_all(engine)
        try:
            repository = SecureObjectRepository(engine=engine)
            namespace = "aeat.google.sync.push.fixture"
            repository.save(
                namespace=namespace,
                object_key="natural-key",
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime(2026, 5, 28, 12, 0, tzinfo=UTC),
                payload=b"push-path-plaintext",
            )
            raw_row = next(repository.iter_all_records_raw())
            provider = LocalFileSystemProvider(tmp_path / "mirror")

            result = _push_secure_object_mirror_rows(
                provider=provider,
                repository=repository,
                namespace_filter=None,
                limit=None,
                dry_run=False,
            )

            hmac_hex = remote_mirror_object_key_hmac(namespace, raw_row.object_key)
            ciphertext_payload, ciphertext_metadata = provider.get(namespace, hmac_hex)
            manifest_payload, _ = provider.get(
                REMOTE_MIRROR_MANIFEST_NAMESPACE,
                next(iter(provider.iter_objects(REMOTE_MIRROR_MANIFEST_NAMESPACE))).object_key_hmac,
            )
            manifest = RemoteMirrorNamespaceManifest.model_validate_json(manifest_payload)

            assert result["pushed_by_namespace"] == {namespace: 1}
            assert result["manifest_pushed_by_namespace"] == {namespace: 1}
            assert result["failed_objects"] == []
            assert result["failed_manifests"] == []
            assert result["degraded_manifests"] == []
            assert ciphertext_payload == raw_row.payload
            assert ciphertext_metadata.object_key_hmac == hmac_hex
            assert b"push-path-plaintext" not in manifest_payload
            assert manifest.objects[0].object_key_hmac == hmac_hex
            assert manifest.objects[0].ciphertext_hash == raw_row.ciphertext_hash
            assert manifest.latest_revision_id == raw_row.revision_id
        finally:
            engine.dispose()


def test_google_sync_push_reports_partial_upload_before_repairing_remote_manifest(tmp_path: Path) -> None:
    key_provider = EphemeralMasterKeyProvider()
    with key_provider:
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{(tmp_path / 'partial-upload.db').as_posix()}"),
        )
        Base.metadata.create_all(engine)
        try:
            repository = SecureObjectRepository(engine=engine)
            namespace = "aeat.google.sync.push.partial.upload"
            repository.save(
                namespace=namespace,
                object_key="natural-key",
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime(2026, 5, 28, 12, 0, tzinfo=UTC),
                payload=b"partial-upload-plaintext",
            )
            raw_row = next(repository.iter_all_records_raw())
            local_manifest = build_remote_mirror_namespace_manifest(namespace, (raw_row,))
            remote_manifest = local_manifest.model_copy(
                update={
                    "object_count": 0,
                    "latest_revision_id": None,
                    "latest_revision_written_at": None,
                    "objects": (),
                }
            )
            provider = LocalFileSystemProvider(tmp_path / "mirror")
            put_remote_mirror_namespace_manifest(provider, remote_manifest)

            result = _push_secure_object_mirror_rows(
                provider=provider,
                repository=repository,
                namespace_filter=None,
                limit=None,
                dry_run=False,
            )

            assert result["failed_objects"] == []
            assert result["failed_manifests"] == []
            assert result["manifest_pushed_by_namespace"] == {namespace: 1}
            assert len(result["degraded_manifests"]) == 1
            assert result["degraded_manifests"][0][0] == namespace
            assert "partial_upload" in result["degraded_manifests"][0][1]
        finally:
            engine.dispose()


def test_google_sync_push_reports_partial_download_before_repairing_remote_object(tmp_path: Path) -> None:
    key_provider = EphemeralMasterKeyProvider()
    with key_provider:
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{(tmp_path / 'partial-download.db').as_posix()}"),
        )
        Base.metadata.create_all(engine)
        try:
            repository = SecureObjectRepository(engine=engine)
            namespace = "aeat.google.sync.push.partial.download"
            repository.save(
                namespace=namespace,
                object_key="natural-key",
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime(2026, 5, 28, 12, 0, tzinfo=UTC),
                payload=b"partial-download-plaintext",
            )
            raw_row = next(repository.iter_all_records_raw())
            manifest = build_remote_mirror_namespace_manifest(namespace, (raw_row,))
            provider = LocalFileSystemProvider(tmp_path / "mirror")
            put_remote_mirror_namespace_manifest(provider, manifest)

            result = _push_secure_object_mirror_rows(
                provider=provider,
                repository=repository,
                namespace_filter=None,
                limit=None,
                dry_run=False,
            )

            assert result["failed_objects"] == []
            assert result["failed_manifests"] == []
            assert result["manifest_pushed_by_namespace"] == {namespace: 1}
            assert len(result["degraded_manifests"]) == 1
            assert result["degraded_manifests"][0][0] == namespace
            assert "partial_download" in result["degraded_manifests"][0][1]
        finally:
            engine.dispose()


def test_google_sync_push_reports_stale_remote_manifest_before_repairing_it(tmp_path: Path) -> None:
    key_provider = EphemeralMasterKeyProvider()
    with key_provider:
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{(tmp_path / 'stale-remote.db').as_posix()}"),
        )
        Base.metadata.create_all(engine)
        try:
            repository = SecureObjectRepository(engine=engine)
            namespace = "aeat.google.sync.push.stale.remote"
            repository.save(
                namespace=namespace,
                object_key="natural-key",
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime(2026, 5, 28, 12, 0, tzinfo=UTC),
                payload=b"first-stale-plaintext",
            )
            first_raw_row = next(repository.iter_all_records_raw())
            provider = LocalFileSystemProvider(tmp_path / "mirror")
            first_hmac = remote_mirror_object_key_hmac(namespace, first_raw_row.object_key)
            provider.put(
                namespace,
                first_hmac,
                first_raw_row.payload,
                content_hash=f"sha256-{hashlib.sha256(first_raw_row.payload).hexdigest()}",
                label="stale",
            )
            first_manifest = build_remote_mirror_namespace_manifest(namespace, (first_raw_row,))
            manifest_metadata = put_remote_mirror_namespace_manifest(provider, first_manifest)

            repository.save(
                namespace=namespace,
                object_key="natural-key",
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime(2026, 5, 28, 12, 1, tzinfo=UTC),
                payload=b"second-stale-plaintext",
            )
            latest_raw_row = next(repository.iter_all_records_raw())

            result = _push_secure_object_mirror_rows(
                provider=provider,
                repository=repository,
                namespace_filter=None,
                limit=None,
                dry_run=False,
            )
            manifest_payload, _ = provider.get(REMOTE_MIRROR_MANIFEST_NAMESPACE, manifest_metadata.object_key_hmac)
            repaired_manifest = RemoteMirrorNamespaceManifest.model_validate_json(manifest_payload)

            assert result["failed_objects"] == []
            assert result["failed_manifests"] == []
            assert result["manifest_pushed_by_namespace"] == {namespace: 1}
            assert len(result["degraded_manifests"]) == 1
            assert result["degraded_manifests"][0][0] == namespace
            assert "stale_mirror" in result["degraded_manifests"][0][1]
            assert repaired_manifest.latest_revision_id == latest_raw_row.revision_id
        finally:
            engine.dispose()


def test_google_sync_push_refuses_remote_revision_conflict_before_overwriting_object(tmp_path: Path) -> None:
    key_provider = EphemeralMasterKeyProvider()
    with key_provider:
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{(tmp_path / 'revision-conflict.db').as_posix()}"),
        )
        Base.metadata.create_all(engine)
        try:
            repository = SecureObjectRepository(engine=engine)
            namespace = "aeat.google.sync.push.revision.conflict"
            repository.save(
                namespace=namespace,
                object_key="natural-key",
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime(2026, 5, 28, 12, 0, tzinfo=UTC),
                payload=b"local-conflict-plaintext",
            )
            raw_row = next(repository.iter_all_records_raw())
            local_manifest = build_remote_mirror_namespace_manifest(namespace, (raw_row,))
            local_entry = local_manifest.objects[0]
            remote_payload = b"remote-conflicting-ciphertext"
            remote_entry = local_entry.model_copy(
                update={
                    "storage_revision_id": "f" * 64,
                    "previous_storage_revision_id": "e" * 64,
                    "ciphertext_hash": hashlib.sha256(remote_payload).hexdigest(),
                    "byte_length": len(remote_payload),
                }
            )
            remote_manifest = local_manifest.model_copy(
                update={
                    "latest_revision_id": remote_entry.storage_revision_id,
                    "objects": (remote_entry,),
                }
            )
            provider = LocalFileSystemProvider(tmp_path / "mirror")
            provider.put(
                namespace,
                remote_entry.object_key_hmac,
                remote_payload,
                content_hash=f"sha256-{hashlib.sha256(remote_payload).hexdigest()}",
                label="conflict",
            )
            put_remote_mirror_namespace_manifest(provider, remote_manifest)

            result = _push_secure_object_mirror_rows(
                provider=provider,
                repository=repository,
                namespace_filter=None,
                limit=None,
                dry_run=False,
            )
            persisted_payload, _ = provider.get(namespace, remote_entry.object_key_hmac)

            assert result["pushed_by_namespace"] == {}
            assert result["manifest_pushed_by_namespace"] == {}
            assert result["failed_objects"] == []
            assert len(result["failed_manifests"]) == 1
            assert result["failed_manifests"][0][0] == namespace
            assert "revision_conflict" in result["failed_manifests"][0][1]
            assert persisted_payload == remote_payload
        finally:
            engine.dispose()


def test_google_sync_push_refuses_non_dry_run_limit_because_manifest_would_be_partial(tmp_path: Path) -> None:
    key_provider = EphemeralMasterKeyProvider()
    with key_provider:
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{(tmp_path / 'limit.db').as_posix()}"),
        )
        Base.metadata.create_all(engine)
        try:
            repository = SecureObjectRepository(engine=engine)
            provider = LocalFileSystemProvider(tmp_path / "mirror")

            with pytest.raises(OutboundStorageValidationError, match="--limit"):
                _push_secure_object_mirror_rows(
                    provider=provider,
                    repository=repository,
                    namespace_filter=None,
                    limit=1,
                    dry_run=False,
                )
        finally:
            engine.dispose()
