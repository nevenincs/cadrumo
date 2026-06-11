"""Real-behavior coverage for Google sync push mirror semantics."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from .....adapters.outbound.storage import (
    REMOTE_MIRROR_MANIFEST_NAMESPACE,
    OutboundStorageNotFoundError,
    OutboundStorageValidationError,
    RemoteMirrorNamespaceManifest,
    build_remote_mirror_namespace_manifest,
    put_remote_mirror_namespace_manifest,
    remote_mirror_object_key_hmac,
)
from .....adapters.outbound.storage._local import LocalFileSystemProvider
from .....adapters.persistence.storage import STORAGE_NAMESPACE_REGISTRY
from .....core.i18n import tr
from .....tests.secure_sql import isolated_runtime_profile
from .._google import _google_refusal, _push_secure_object_mirror_rows
from .._google_payloads import GoogleSyncProbeResult

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_google_sync_probe_payload_accepts_unknown_root_folder_presence() -> None:
    result = GoogleSyncProbeResult(
        profile="profile-id",
        provider_kind="local_filesystem",
        reachable=True,
        writable=False,
        read_only=True,
        root_folder_present=None,
        root_folder_id="",
        detail="probe reached backend; root folder presence is not applicable",
    )

    assert result.root_folder_present is None
    assert result.model_dump()["root_folder_present"] is None


def test_google_sync_push_persists_manifest_matching_uploaded_ciphertext_objects(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="google-sync-push") as profile:
        repository = profile.repository
        plaintext_by_key = {
            "google_oauth_client": b"push-path-client-secret-plaintext",
            "google_oauth_token": b"push-path-refresh-token-plaintext",
            "google_oauth_metadata": b"push-path-metadata-plaintext",
        }
        for namespace_key, plaintext in plaintext_by_key.items():
            namespace_definition = STORAGE_NAMESPACE_REGISTRY.namespace_by_key(namespace_key)
            repository.save(
                namespace=namespace_definition.namespace,
                object_key=f"natural-key-{namespace_key}",
                classification=namespace_definition.sensitivity,
                schema_version=1,
                written_at=datetime(2026, 5, 28, 12, 0, tzinfo=UTC),
                payload=plaintext,
            )
        raw_rows = tuple(repository.iter_all_records_raw())
        provider = LocalFileSystemProvider(tmp_path / "mirror")

        result = _push_secure_object_mirror_rows(
            provider=provider,
            repository=repository,
            namespace_filter=None,
            limit=None,
            dry_run=False,
        )

        expected_counts = {row.namespace: 1 for row in raw_rows}
        assert result["pushed_by_namespace"] == expected_counts
        assert result["manifest_pushed_by_namespace"] == expected_counts
        assert result["failed_objects"] == []
        assert result["failed_manifests"] == []
        assert result["degraded_manifests"] == []

        manifest_by_namespace: dict[str, RemoteMirrorNamespaceManifest] = {}
        for metadata in provider.iter_objects(REMOTE_MIRROR_MANIFEST_NAMESPACE):
            manifest_payload, _ = provider.get(REMOTE_MIRROR_MANIFEST_NAMESPACE, metadata.object_key_hmac)
            manifest = RemoteMirrorNamespaceManifest.model_validate_json(manifest_payload)
            manifest_by_namespace[manifest.namespace] = manifest
            for plaintext in plaintext_by_key.values():
                assert plaintext not in manifest_payload

        assert set(manifest_by_namespace) == set(expected_counts)
        for raw_row in raw_rows:
            hmac_hex = remote_mirror_object_key_hmac(raw_row.namespace, raw_row.object_key)
            ciphertext_payload, ciphertext_metadata = provider.get(raw_row.namespace, hmac_hex)
            manifest = manifest_by_namespace[raw_row.namespace]

            assert ciphertext_payload == raw_row.payload
            assert ciphertext_metadata.namespace == raw_row.namespace
            assert ciphertext_metadata.object_key_hmac == hmac_hex
            assert manifest.objects[0].object_key_hmac == hmac_hex
            assert manifest.objects[0].ciphertext_hash == raw_row.ciphertext_hash
            assert manifest.latest_revision_id == raw_row.revision_id


def test_google_sync_push_reports_partial_upload_before_repairing_remote_manifest(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="google-sync-partial-upload") as profile:
        repository = profile.repository
        namespace_definition = STORAGE_NAMESPACE_REGISTRY.namespace_by_key("google_oauth_metadata")
        namespace = namespace_definition.namespace
        repository.save(
            namespace=namespace,
            object_key="natural-key",
            classification=namespace_definition.sensitivity,
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
            },
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


def test_google_sync_push_reports_partial_download_before_repairing_remote_object(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="google-sync-partial-download") as profile:
        repository = profile.repository
        namespace_definition = STORAGE_NAMESPACE_REGISTRY.namespace_by_key("google_oauth_metadata")
        namespace = namespace_definition.namespace
        repository.save(
            namespace=namespace,
            object_key="natural-key",
            classification=namespace_definition.sensitivity,
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


def test_google_sync_push_reports_stale_remote_manifest_before_repairing_it(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="google-sync-stale-remote") as profile:
        repository = profile.repository
        namespace_definition = STORAGE_NAMESPACE_REGISTRY.namespace_by_key("google_oauth_metadata")
        namespace = namespace_definition.namespace
        repository.save(
            namespace=namespace,
            object_key="natural-key",
            classification=namespace_definition.sensitivity,
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
            classification=namespace_definition.sensitivity,
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


def test_google_sync_push_refuses_remote_revision_conflict_before_overwriting_object(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="google-sync-revision-conflict") as profile:
        repository = profile.repository
        namespace_definition = STORAGE_NAMESPACE_REGISTRY.namespace_by_key("google_oauth_metadata")
        namespace = namespace_definition.namespace
        repository.save(
            namespace=namespace,
            object_key="natural-key",
            classification=namespace_definition.sensitivity,
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
            },
        )
        remote_manifest = local_manifest.model_copy(
            update={
                "latest_revision_id": remote_entry.storage_revision_id,
                "objects": (remote_entry,),
            },
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


def test_google_sync_push_dry_run_counts_every_row_as_skipped_without_writing(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="google-sync-dry-run") as profile:
        repository = profile.repository
        plaintext_by_key = {
            "google_oauth_client": b"dry-run-client-secret-plaintext",
            "google_oauth_token": b"dry-run-refresh-token-plaintext",
            "google_oauth_metadata": b"dry-run-metadata-plaintext",
        }
        for namespace_key, plaintext in plaintext_by_key.items():
            namespace_definition = STORAGE_NAMESPACE_REGISTRY.namespace_by_key(namespace_key)
            repository.save(
                namespace=namespace_definition.namespace,
                object_key=f"natural-key-{namespace_key}",
                classification=namespace_definition.sensitivity,
                schema_version=1,
                written_at=datetime(2026, 5, 28, 12, 0, tzinfo=UTC),
                payload=plaintext,
            )
        raw_rows = tuple(repository.iter_all_records_raw())
        provider = LocalFileSystemProvider(tmp_path / "mirror")

        result = _push_secure_object_mirror_rows(
            provider=provider,
            repository=repository,
            namespace_filter=None,
            limit=None,
            dry_run=True,
        )

        expected_counts = {row.namespace: 1 for row in raw_rows}
        assert result["skipped_by_namespace"] == expected_counts
        assert result["pushed_by_namespace"] == {}
        assert result["manifest_pushed_by_namespace"] == {}
        assert result["failed_objects"] == []
        assert result["failed_manifests"] == []
        assert result["degraded_manifests"] == []
        # A dry-run must not touch the provider at all: no namespace directory
        # is created, so iter_objects raises not-found for every row's namespace.
        for row in raw_rows:
            with pytest.raises(OutboundStorageNotFoundError):
                next(iter(provider.iter_objects(row.namespace)), None)


def test_google_sync_push_namespace_filter_restricts_pushed_rows(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="google-sync-namespace-filter") as profile:
        repository = profile.repository
        plaintext_by_key = {
            "google_oauth_client": b"filter-client-secret-plaintext",
            "google_oauth_token": b"filter-refresh-token-plaintext",
        }
        for namespace_key, plaintext in plaintext_by_key.items():
            namespace_definition = STORAGE_NAMESPACE_REGISTRY.namespace_by_key(namespace_key)
            repository.save(
                namespace=namespace_definition.namespace,
                object_key=f"natural-key-{namespace_key}",
                classification=namespace_definition.sensitivity,
                schema_version=1,
                written_at=datetime(2026, 5, 28, 12, 0, tzinfo=UTC),
                payload=plaintext,
            )
        target_namespace = STORAGE_NAMESPACE_REGISTRY.namespace_by_key("google_oauth_client").namespace
        other_namespace = STORAGE_NAMESPACE_REGISTRY.namespace_by_key("google_oauth_token").namespace
        provider = LocalFileSystemProvider(tmp_path / "mirror")

        result = _push_secure_object_mirror_rows(
            provider=provider,
            repository=repository,
            namespace_filter=target_namespace,
            limit=None,
            dry_run=False,
        )

        assert result["pushed_by_namespace"] == {target_namespace: 1}
        assert result["manifest_pushed_by_namespace"] == {target_namespace: 1}
        assert result["failed_objects"] == []
        assert result["failed_manifests"] == []
        # The filtered-out namespace must never reach the provider (no directory
        # created), while the target namespace receives exactly its one object.
        with pytest.raises(OutboundStorageNotFoundError):
            next(iter(provider.iter_objects(other_namespace)), None)
        assert len(list(provider.iter_objects(target_namespace))) == 1


def test_google_sync_push_refuses_non_dry_run_limit_because_manifest_would_be_partial(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="google-sync-limit") as profile:
        provider = LocalFileSystemProvider(tmp_path / "mirror")

        with pytest.raises(OutboundStorageValidationError, match="--limit") as raised:
            _push_secure_object_mirror_rows(
                provider=provider,
                repository=profile.repository,
                namespace_filter=None,
                limit=1,
                dry_run=False,
            )
        refusal = _google_refusal(raised.value)

        assert refusal.context is not None
        assert refusal.context["detail"] == tr("cli.config.google.detail.sync_push_limit_requires_dry_run")
