"""Regression tests for the bucket-provisioning side of `initialize_workspace`.

Pins the post-init bucket-provisioning contract: after a successful
workspace init, the per-bucket directory tree (`<aeat-root>/buckets/<id>/`
with `db/`, `blobs/`, `audit/` subdirectories) AND the
`<bucket-dir>/manifest.toml` must exist on disk. The manifest
carries the OWASP-baseline Argon2id KDF parameters under a fresh
salt; `recovery_enrolled=False` until the recovery enrollment
flow runs.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from aeat.adapters.persistence.storage import (
    EphemeralMasterKeyProvider,
)
from aeat.adapters.persistence.storage.bucket._layout import bucket_paths
from aeat.adapters.persistence.storage.bucket._manifest_io import manifest_path, read_manifest
from aeat.adapters.persistence.storage.sql import SecureObjectRepository, create_engine_from_settings
from aeat.adapters.persistence.storage.sql._orm import Base
from aeat.application.setup._contracts import InitializeWorkspaceCommand
from aeat.application.setup._errors import WorkspaceBucketTornError
from aeat.application.setup._service import initialize_workspace
from aeat.core.config import Settings, load_settings

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    provider = EphemeralMasterKeyProvider()
    with provider:
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{(tmp_path / 'init.db').as_posix()}"),
        )
        Base.metadata.create_all(engine)
        try:
            yield SecureObjectRepository(engine=engine)
        finally:
            engine.dispose()


def test_initialize_workspace_provisions_bucket_directory_and_manifest(
    secure_objects: SecureObjectRepository,
) -> None:
    """A successful init lays out the bucket dir and writes the manifest."""

    initialize_workspace(
        InitializeWorkspaceCommand(
            profile_name="catering",
            tax_id="12345678Z",
            activity="catering",
            iva_regime="GENERAL",
            auth_provider="none",
        )
    )

    settings = load_settings()
    paths = bucket_paths(settings.aeat_local_storage_root, "catering")
    assert paths.bucket_dir.is_dir()
    assert paths.db_dir.is_dir()
    assert paths.blobs_dir.is_dir()
    assert paths.audit_dir.is_dir()
    assert manifest_path(paths).is_file()


def test_initialize_workspace_writes_manifest_with_baseline_kdf_params(
    secure_objects: SecureObjectRepository,
) -> None:
    """The manifest records OWASP-baseline Argon2id params + a fresh salt."""

    initialize_workspace(
        InitializeWorkspaceCommand(
            profile_name="catering",
            tax_id="12345678Z",
            activity="catering",
            iva_regime="GENERAL",
            auth_provider="none",
        )
    )

    settings = load_settings()
    paths = bucket_paths(settings.aeat_local_storage_root, "catering")
    manifest = read_manifest(paths)

    assert manifest.bucket_id == "catering"
    assert manifest.label == "catering"
    assert manifest.recovery_enrolled is False
    assert manifest.kdf_params.algorithm == "argon2id"
    assert manifest.kdf_params.memory_cost == 19_456
    assert manifest.kdf_params.time_cost == 2
    assert manifest.kdf_params.parallelism == 1
    assert manifest.kdf_params.output_length == 32
    assert len(manifest.kdf_params.salt) == 16


def _write_manifest_only_bucket(profile_name: str, *, salt: bytes) -> Path:
    """Provision a bucket directory + manifest WITHOUT a profile record.

    Reproduces a torn bucket: a crash between disaster-ADR Ruling-3
    step 2 (manifest write) and step 4 (encrypted profile record
    write) leaves the manifest claiming the profile exists while no
    decryptable record backs it.
    """

    from datetime import UTC, datetime

    from aeat.adapters.persistence.storage.bucket._layout import provision_bucket_directory
    from aeat.adapters.persistence.storage.bucket._manifest import BucketManifest, ManifestKdfParams
    from aeat.adapters.persistence.storage.bucket._manifest_io import write_manifest

    settings = load_settings()
    paths = provision_bucket_directory(settings.aeat_local_storage_root, profile_name)
    write_manifest(
        paths,
        BucketManifest(
            bucket_id=profile_name,
            label=profile_name,
            created_at=datetime.now(UTC),
            last_unlocked_at=None,
            kdf_params=ManifestKdfParams(
                algorithm="argon2id",
                version=0x13,
                memory_cost=19_456,
                time_cost=2,
                parallelism=1,
                salt=salt,
                output_length=32,
            ),
            recovery_enrolled=False,
            schema_version=1,
        ),
    )
    return manifest_path(paths).parent


def test_initialize_workspace_refuses_torn_bucket(
    secure_objects: SecureObjectRepository,
) -> None:
    """A manifest without its profile record is a torn bucket; init refuses.

    The bucket-directory + manifest provisioning runs ahead of the
    profile-record write. A manifest present without the encrypted
    ``UserProfileRecord`` is the disaster-ADR torn case: the manifest
    scan reports the profile as existing, but no decryptable record
    backs it. ``initialize_workspace`` must detect this with a
    no-decryption DB-existence check and raise
    :class:`WorkspaceBucketTornError` rather than silently overlaying
    new profile data into degraded storage.
    """

    _write_manifest_only_bucket("catering", salt=b"\x42" * 16)

    with pytest.raises(WorkspaceBucketTornError):
        initialize_workspace(
            InitializeWorkspaceCommand(
                profile_name="catering",
                tax_id="12345678Z",
                activity="catering",
                iva_regime="GENERAL",
                auth_provider="none",
            )
        )


def test_initialize_workspace_torn_bucket_refusal_preserves_manifest_salt(
    secure_objects: SecureObjectRepository,
) -> None:
    """The torn-bucket refusal does not clobber the existing manifest salt.

    The provisioner detects the existing manifest and skips the
    write; the torn-bucket guard then refuses. The bucket's KDF salt
    must survive the refusal so a later repair + recreate against the
    same salt remains possible.
    """

    pinned_salt = b"\x42" * 16
    bucket_dir = _write_manifest_only_bucket("catering", salt=pinned_salt)
    paths = bucket_paths(load_settings().aeat_local_storage_root, "catering")

    with pytest.raises(WorkspaceBucketTornError):
        initialize_workspace(
            InitializeWorkspaceCommand(
                profile_name="catering",
                tax_id="12345678Z",
                activity="catering",
                iva_regime="GENERAL",
                auth_provider="none",
            )
        )

    assert bucket_dir.is_dir()
    assert read_manifest(paths).kdf_params.salt == pinned_salt


def test_initialize_workspace_idempotent_for_genuinely_initialized_workspace(
    secure_objects: SecureObjectRepository,
) -> None:
    """A re-run against a fully-initialized workspace is a benign no-op.

    The first ``initialize_workspace`` writes both the manifest and
    the encrypted profile record. A second run hits
    ``ProfileAlreadyRegisteredError`` from the lifecycle service, but
    the no-decryption DB-existence check finds the record present, so
    the run returns normally instead of raising the torn-bucket
    error.
    """

    command = InitializeWorkspaceCommand(
        profile_name="catering",
        tax_id="12345678Z",
        activity="catering",
        iva_regime="GENERAL",
        auth_provider="none",
    )

    first = initialize_workspace(command)
    second = initialize_workspace(command)

    assert first.profile_id == "catering"
    assert second.profile_id == "catering"
    assert second.bucket_id == "catering"
