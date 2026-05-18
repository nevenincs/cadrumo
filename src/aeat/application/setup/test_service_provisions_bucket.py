"""Regression tests for the bucket-provisioning side of `initialize_workspace`.

Pins the contract added in P02.S19: after a successful workspace
init, the per-bucket directory tree (`<aeat-root>/buckets/<id>/`
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
    override_master_key_provider,
)
from aeat.adapters.persistence.storage.bucket._layout import bucket_paths
from aeat.adapters.persistence.storage.bucket._manifest_io import manifest_path, read_manifest
from aeat.adapters.persistence.storage.sql import SecureObjectRepository, create_engine_from_settings
from aeat.adapters.persistence.storage.sql._orm import Base
from aeat.application.setup._contracts import InitializeWorkspaceCommand
from aeat.application.setup._service import initialize_workspace
from aeat.core.config import Settings, load_settings

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    provider = EphemeralMasterKeyProvider()
    override_master_key_provider(provider)
    engine = create_engine_from_settings(
        Settings(aeat_database_url=f"sqlite:///{(tmp_path / 'init.db').as_posix()}"),
    )
    Base.metadata.create_all(engine)
    try:
        yield SecureObjectRepository(engine=engine)
    finally:
        engine.dispose()
        override_master_key_provider(None)


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


def test_initialize_workspace_preserves_salt_when_manifest_already_present(
    tmp_path: Path,
    secure_objects: SecureObjectRepository,
) -> None:
    """A re-attempt against an existing manifest does not regenerate the salt.

    The lifecycle service refuses to re-register a profile that
    already exists, but the bucket-directory + manifest provisioning
    runs ahead of the register call. The provision step must NOT
    overwrite an existing manifest because that would clobber the
    bucket's KDF salt and break any recovery enrollment performed
    against the old salt. This test pre-creates the manifest, runs
    init through the full pipeline, and asserts the salt survived
    even though the lifecycle service then refused the duplicate
    registration.
    """

    from aeat.adapters.persistence.storage.bucket._layout import provision_bucket_directory
    from aeat.adapters.persistence.storage.bucket._manifest import BucketManifest, KdfParams
    from aeat.adapters.persistence.storage.bucket._manifest_io import write_manifest
    from datetime import UTC, datetime

    settings = load_settings()
    paths = provision_bucket_directory(settings.aeat_local_storage_root, "catering")
    pinned_salt = b"\x42" * 16
    write_manifest(
        paths,
        BucketManifest(
            bucket_id="catering",
            label="catering",
            created_at=datetime.now(UTC),
            last_unlocked_at=None,
            kdf_params=KdfParams(
                algorithm="argon2id",
                version=0x13,
                memory_cost=19_456,
                time_cost=2,
                parallelism=1,
                salt=pinned_salt,
                output_length=32,
            ),
            recovery_enrolled=False,
            schema_version=1,
        ),
    )

    initialize_workspace(
        InitializeWorkspaceCommand(
            profile_name="catering",
            tax_id="12345678Z",
            activity="catering",
            iva_regime="GENERAL",
            auth_provider="none",
        )
    )

    # Salt survived: the provisioner detected the existing manifest
    # and skipped the write rather than regenerating.
    assert read_manifest(paths).kdf_params.salt == pinned_salt
