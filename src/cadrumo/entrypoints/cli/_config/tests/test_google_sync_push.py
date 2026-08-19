"""Real-behavior coverage for Google sync push mirror semantics."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import text

from .....adapters.outbound.storage import (
    REMOTE_MIRROR_MANIFEST_NAMESPACE,
    OutboundStorageNotFoundError,
    OutboundStorageValidationError,
    ProviderKind,
    RemoteMirrorNamespaceManifest,
    build_remote_mirror_namespace_manifest,
    put_remote_mirror_namespace_manifest,
    remote_mirror_object_key_hmac,
)
from .....adapters.outbound.storage._local import LocalFileSystemProvider
from .....adapters.persistence.storage import STORAGE_NAMESPACE_REGISTRY
from .....adapters.persistence.storage.sql import SecureObjectRepository
from .....core.i18n import tr
from .....tests.path_obstruction import obstructed_path
from .....tests.secure_sql import isolated_runtime_profile
from .._google import _google_refusal, _label_for, _push_secure_object_mirror_rows
from .._google_payloads import GoogleSyncProbeResult

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _row_in(repository: SecureObjectRepository, namespace: str):
    """Return the seeded row for ``namespace``, not merely the first row stored.

    The bucket carries more than a case seeds: the runtime profile fixture
    writes a profile-fact row and a bucket-event row, and both are mirrorable,
    so they are pushed as ciphertext alongside whatever the case saved. Taking
    the first row therefore builds a manifest for somebody else's namespace.
    """
    return next(row for row in repository.iter_all_records_raw() if row.namespace == namespace)


def test_google_sync_probe_payload_accepts_unknown_root_folder_presence() -> None:
    result = GoogleSyncProbeResult(
        profile="profile-id",
        provider_kind=ProviderKind.LOCAL_FILESYSTEM,
        reachable=True,
        writable=False,
        read_only=True,
        root_folder_present=None,
        root_folder_id="",
        detail="probe reached backend; root folder presence is not applicable",
    )

    assert result.root_folder_present is None
    assert result.model_dump()["root_folder_present"] is None


@pytest.mark.parametrize("provider_kind", ["", "bogus"])
def test_google_sync_probe_payload_refuses_unknown_provider_kind(provider_kind: str) -> None:
    """The CLI probe contract admits only storage backends the provider can report."""

    with pytest.raises(ValidationError, match="ProviderKind"):
        GoogleSyncProbeResult(
            profile="profile-id",
            provider_kind=provider_kind,
            reachable=True,
            writable=False,
            read_only=True,
            root_folder_present=None,
            root_folder_id="",
        )


def test_google_sync_push_persists_manifest_matching_uploaded_ciphertext_objects(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="003a1085-09ba-4bb7-b507-792b9aa74379") as profile:
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
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="91284810-5de7-4586-8555-673b5384139b") as profile:
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
        raw_row = _row_in(repository, namespace)
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
        assert result["manifest_pushed_by_namespace"][namespace] == 1
        assert len(result["degraded_manifests"]) == 1
        assert result["degraded_manifests"][0][0] == namespace
        assert "partial_upload" in result["degraded_manifests"][0][1]


def test_google_sync_push_reports_partial_download_before_repairing_remote_object(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="17252893-3010-4568-acfe-927ca590bc5b") as profile:
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
        raw_row = _row_in(repository, namespace)
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
        assert result["manifest_pushed_by_namespace"][namespace] == 1
        assert len(result["degraded_manifests"]) == 1
        assert result["degraded_manifests"][0][0] == namespace
        assert "partial_download" in result["degraded_manifests"][0][1]


def test_google_sync_push_reports_stale_remote_manifest_before_repairing_it(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="448f713f-d59d-4478-a993-738d4e6e1521") as profile:
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
        first_raw_row = _row_in(repository, namespace)
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
        latest_raw_row = _row_in(repository, namespace)

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
        assert result["manifest_pushed_by_namespace"][namespace] == 1
        assert len(result["degraded_manifests"]) == 1
        assert result["degraded_manifests"][0][0] == namespace
        assert "stale_mirror" in result["degraded_manifests"][0][1]
        assert repaired_manifest.latest_revision_id == latest_raw_row.revision_id


def test_google_sync_push_refuses_remote_revision_conflict_before_overwriting_object(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="884c2da3-26bb-4317-89fb-8e6ab3d539b8") as profile:
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
        raw_row = _row_in(repository, namespace)
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

        # THIS namespace is the one the conflict must block. The bucket's other
        # mirrorable rows -- the profile fact and bucket event the runtime
        # fixture writes -- push normally, and a whole-bucket emptiness check
        # would be asserting that a revision conflict in one namespace halts
        # every other, which is the blast radius the per-namespace preflight
        # exists to avoid.
        assert namespace not in result["pushed_by_namespace"]
        assert namespace not in result["manifest_pushed_by_namespace"]
        assert result["failed_objects"] == []
        assert len(result["failed_manifests"]) == 1
        assert result["failed_manifests"][0][0] == namespace
        assert "revision_conflict" in result["failed_manifests"][0][1]
        assert persisted_payload == remote_payload


def _tamper_stored_column(repository: SecureObjectRepository, *, namespace: str, column: str, value: str) -> None:
    """Overwrite one stored ``secure_objects`` column, asserting the write actually changed it.

    Mirrors the pattern in
    ``storage/sql/tests/test_secure_object_revision_lineage_coverage.py``: a
    tamper that silently no-ops would leave the row genuine, and every
    "blocked" verdict below would then be satisfied by an untouched row
    rather than by a forged one.
    """
    engine = repository._engine
    select = text(f"SELECT {column} FROM secure_objects WHERE namespace = :ns")  # noqa: S608 - column is a module constant
    update = text(f"UPDATE secure_objects SET {column} = :value WHERE namespace = :ns")  # noqa: S608
    with engine.begin() as connection:
        before = connection.execute(select, {"ns": namespace}).scalar_one()
        connection.execute(update, {"value": value, "ns": namespace})
        after = connection.execute(select, {"ns": namespace}).scalar_one()
    assert before != after, f"{column}: tamper was a no-op, stored value stayed {before!r}"


def test_google_sync_push_blocks_a_namespace_whose_raw_row_lineage_recomputes_wrong(tmp_path: Path) -> None:
    """A tampered covered column on the RAW row must block that namespace's push.

    :meth:`SecureObjectRepository.iter_all_records_raw` bypasses the
    encrypted-column type decorators by design (rows sealed under a rotated
    master key must still surface for mirroring), so the decrypting read
    path's revision-lineage self-consistency gate never otherwise runs on
    these rows. Tampering ``payload_hash`` -- one of the eight
    ``derive_revision_id`` inputs -- directly at the SQL layer after a
    genuine write is the only way to reach that gap: the raw iterator has no
    decrypt step of its own to catch it.

    POSITIVE CONTROL, both directions: the tampered namespace's ciphertext
    must never reach the remote provider at all (not merely have its
    manifest withheld), while an untouched sibling namespace must still push
    cleanly -- proving the block is scoped to the compromised namespace, not
    the whole preflight.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="24b3f89e-6752-49e1-b93b-b25e81e9294a") as profile:
        repository = profile.repository
        tampered_definition = STORAGE_NAMESPACE_REGISTRY.namespace_by_key("google_oauth_metadata")
        tampered_namespace = tampered_definition.namespace
        repository.save(
            namespace=tampered_namespace,
            object_key="natural-key",
            classification=tampered_definition.sensitivity,
            schema_version=1,
            written_at=datetime(2026, 5, 28, 12, 0, tzinfo=UTC),
            payload=b"tampered-lineage-plaintext",
        )
        clean_definition = STORAGE_NAMESPACE_REGISTRY.namespace_by_key("google_oauth_client")
        clean_namespace = clean_definition.namespace
        repository.save(
            namespace=clean_namespace,
            object_key="natural-key",
            classification=clean_definition.sensitivity,
            schema_version=1,
            written_at=datetime(2026, 5, 28, 12, 0, tzinfo=UTC),
            payload=b"untouched-sibling-plaintext",
        )
        _tamper_stored_column(repository, namespace=tampered_namespace, column="payload_hash", value="f" * 64)

        provider = LocalFileSystemProvider(tmp_path / "mirror")
        result = _push_secure_object_mirror_rows(
            provider=provider,
            repository=repository,
            namespace_filter=None,
            limit=None,
            dry_run=False,
        )

        # The tampered namespace is blocked before anything is pushed: no
        # ciphertext object, no manifest, one failed-manifest diagnostic
        # naming the lineage failure.
        assert tampered_namespace not in result["pushed_by_namespace"]
        assert tampered_namespace not in result["manifest_pushed_by_namespace"]
        assert result["failed_objects"] == []
        failed_by_namespace = dict(result["failed_manifests"])
        assert tampered_namespace in failed_by_namespace
        diagnostic = failed_by_namespace[tampered_namespace]
        assert "revision_lineage_inconsistent" in diagnostic
        # The diagnostic names the surface that caught it (there are now two
        # call sites on the shared lineage check: the decrypt path and this
        # mirror preflight) and states WHY a lineage failure is a block, not
        # a degradation -- the causal reason, not a bare severity label, so a
        # later reader cannot "helpfully" weaken it back to a degradation on
        # the true-but-irrelevant grounds that the ciphertext stays safe.
        assert "mirror_preflight" in diagnostic
        assert "remote manifest" in diagnostic

        tampered_raw_row = next(row for row in repository.iter_all_records_raw() if row.namespace == tampered_namespace)
        tampered_hmac = remote_mirror_object_key_hmac(tampered_namespace, tampered_raw_row.object_key)
        with pytest.raises(OutboundStorageNotFoundError):
            provider.get(tampered_namespace, tampered_hmac)

        # The untouched sibling namespace still pushes cleanly: the block is
        # scoped to the compromised namespace, not the whole preflight.
        assert result["pushed_by_namespace"].get(clean_namespace) == 1
        assert result["manifest_pushed_by_namespace"].get(clean_namespace) == 1


def test_google_sync_push_dry_run_counts_every_row_as_skipped_without_writing(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="9ce8825c-9620-4ebb-8097-63cf14fc514d") as profile:
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
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="5a71781d-e8a9-4e01-8c5a-19442d44b402") as profile:
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


def test_google_sync_push_rolls_back_prior_objects_when_a_later_upload_fails(tmp_path: Path) -> None:
    """A partial namespace failure leaves no unmanifested ciphertext on the remote.

    Two rows are seeded in one real namespace; the second row's target file
    is pre-occupied by a real directory, so the real
    :func:`~cadrumo.core.atomic_write.atomic_write_hardened_bytes` replace
    genuinely fails for it (no mock/monkeypatch). The first row's object
    uploads successfully before the second fails -- proving the finding's
    scenario -- and the rollback must delete it: the namespace's manifest is
    withheld, and the provider must not retain any orphaned object for it.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="db940db3-b347-4518-861b-e67c8dee653b") as profile:
        repository = profile.repository
        namespace_definition = STORAGE_NAMESPACE_REGISTRY.namespace_by_key("google_oauth_metadata")
        namespace = namespace_definition.namespace
        for object_key, payload in (
            ("natural-key-first", b"first-row-plaintext"),
            ("natural-key-second", b"second-row-plaintext"),
        ):
            repository.save(
                namespace=namespace,
                object_key=object_key,
                classification=namespace_definition.sensitivity,
                schema_version=1,
                written_at=datetime(2026, 5, 28, 12, 0, tzinfo=UTC),
                payload=payload,
            )
        raw_rows = sorted(
            (row for row in repository.iter_all_records_raw() if row.namespace == namespace),
            key=lambda row: row.row_id,
        )
        assert len(raw_rows) == 2
        second_row = raw_rows[-1]  # the row inserted second, by ascending row_id

        provider = LocalFileSystemProvider(tmp_path / "mirror")
        second_hmac = remote_mirror_object_key_hmac(second_row.namespace, second_row.object_key)
        second_label = _label_for(second_row.namespace)
        # Real O_EXCL-then-replace collision: os.replace refuses to swap a
        # plain file onto an existing directory, so the real atomic-write
        # commit for the second row's object genuinely fails -- no mock.
        second_target = provider.root / namespace / f"{second_hmac[:8]}--{second_label}.bin"

        with obstructed_path(second_target):
            result = _push_secure_object_mirror_rows(
                provider=provider,
                repository=repository,
                namespace_filter=None,
                limit=None,
                dry_run=False,
            )

        assert len(result["failed_objects"]) == 1
        assert result["failed_objects"][0][0] == namespace
        assert result["cleanup_failed_objects"] == []
        # Scoped to the namespace whose upload failed: the rollback must undo
        # THIS namespace's partial publication, not stop the bucket's other
        # mirrorable rows -- the fixture's profile fact and bucket event --
        # from completing their own.
        assert namespace not in result["manifest_pushed_by_namespace"]
        assert namespace not in result["pushed_by_namespace"]

        # The first row's object was genuinely uploaded, then rolled back. The
        # obstruction is cleared by now, so nothing stands at the second row's
        # path either: an empty listing here means the rollback removed what it
        # published, rather than meaning the collision directory was filtered
        # out of the listing.
        assert list(provider.iter_objects(namespace)) == [], "no unmanifested object may remain after the rollback"


def test_google_sync_push_refuses_non_dry_run_limit_because_manifest_would_be_partial(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="bf1dc908-d5a4-4384-8ff0-0e54b3be3e8b") as profile:
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
        # The limit the operator actually passed is the context; the
        # explanation is the typed translated_message. It used to be smuggled
        # into the context as a rendered "detail" string, which the shared
        # envelope contract does not carry -- reading it from there now finds
        # nothing, while the refusal itself is as instructive as it ever was.
        assert refusal.context["limit"] == "1"
        assert refusal.translated_message == "cli.config.google.detail.sync_push_limit_requires_dry_run"
        assert tr(refusal.translated_message) != refusal.translated_message
