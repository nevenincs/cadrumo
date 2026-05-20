"""Regression tests for the bucket-provisioning side of `initialize_workspace`.

Pins the post-init bucket-provisioning contract: after a successful
workspace init, the per-bucket directory tree (`<aeat-root>/buckets/<id>/`
with `db/`, `blobs/`, `audit/` subdirectories) AND the
`<bucket-dir>/manifest.toml` must exist on disk. The bucket directory
is named by the immutable UUID profile identity; the manifest carries
that UUID as `bucket_id` and the operator-chosen name as a decoupled
`label`. The manifest also carries the OWASP-baseline Argon2id KDF
parameters under a fresh salt; `recovery_enrolled=False` until the
recovery enrollment flow runs.
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
from aeat.application.setup._service import initialize_workspace
from aeat.application.user_profile._orchestration import ProfileAlreadyRegisteredError
from aeat.core.config import Settings, load_settings

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_UUID_RE = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"


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
    """A successful init lays out the UUID-named bucket dir and manifest."""

    import re

    result = initialize_workspace(
        InitializeWorkspaceCommand(
            profile_name="catering",
            tax_id="12345678Z",
            activity="catering",
            iva_regime="GENERAL",
            auth_provider="none",
        )
    )

    # The profile identity is a generated UUID, distinct from the name.
    assert re.fullmatch(_UUID_RE, result.profile_id)
    assert result.profile_id == result.bucket_id

    settings = load_settings()
    paths = bucket_paths(settings.aeat_local_storage_root, result.profile_id)
    assert paths.bucket_dir.is_dir()
    assert paths.db_dir.is_dir()
    assert paths.blobs_dir.is_dir()
    assert paths.audit_dir.is_dir()
    assert manifest_path(paths).is_file()


def test_initialize_workspace_writes_manifest_with_uuid_id_and_name_label(
    secure_objects: SecureObjectRepository,
) -> None:
    """The manifest records the UUID identity, the operator label, and KDF params."""

    result = initialize_workspace(
        InitializeWorkspaceCommand(
            profile_name="catering",
            tax_id="12345678Z",
            activity="catering",
            iva_regime="GENERAL",
            auth_provider="none",
        )
    )

    settings = load_settings()
    paths = bucket_paths(settings.aeat_local_storage_root, result.profile_id)
    manifest = read_manifest(paths)

    # bucket_id is the immutable UUID; label is the decoupled operator name.
    assert manifest.bucket_id == result.profile_id
    assert manifest.label == "catering"
    assert manifest.bucket_id != manifest.label
    assert manifest.recovery_enrolled is False
    assert manifest.kdf_params.algorithm == "argon2id"
    assert manifest.kdf_params.memory_cost == 19_456
    assert manifest.kdf_params.time_cost == 2
    assert manifest.kdf_params.parallelism == 1
    assert manifest.kdf_params.output_length == 32
    assert len(manifest.kdf_params.salt) == 16


def test_initialize_workspace_refuses_a_duplicate_operator_name(
    secure_objects: SecureObjectRepository,
) -> None:
    """A second init with the same operator name is refused as a duplicate label.

    Profile identity is a fresh UUID per creation, so there is no
    name-derived idempotent re-run: a name already carried by a live
    profile is a genuine duplicate-label collision.
    """

    command = InitializeWorkspaceCommand(
        profile_name="catering",
        tax_id="12345678Z",
        activity="catering",
        iva_regime="GENERAL",
        auth_provider="none",
    )
    initialize_workspace(command)

    with pytest.raises(ProfileAlreadyRegisteredError):
        initialize_workspace(command)


def test_initialize_workspace_two_distinct_names_get_distinct_uuids(
    secure_objects: SecureObjectRepository,
) -> None:
    """Two profiles with different names land in two UUID-named buckets."""

    first = initialize_workspace(
        InitializeWorkspaceCommand(
            profile_name="catering",
            tax_id="12345678Z",
            activity="catering",
            iva_regime="GENERAL",
            auth_provider="none",
        )
    )
    second = initialize_workspace(
        InitializeWorkspaceCommand(
            profile_name="consulting",
            tax_id="87654321X",
            activity="consulting",
            iva_regime="GENERAL",
            auth_provider="none",
        )
    )

    assert first.profile_id != second.profile_id
    settings = load_settings()
    first_manifest = read_manifest(bucket_paths(settings.aeat_local_storage_root, first.profile_id))
    second_manifest = read_manifest(bucket_paths(settings.aeat_local_storage_root, second.profile_id))
    assert first_manifest.label == "catering"
    assert second_manifest.label == "consulting"
