"""CLI projections keep setup state on authenticated records, not pointers."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import pytest
from click.testing import Result

from ....adapters.persistence.storage.bucket import (
    BUCKET_MANIFEST_SCHEMA_VERSION,
    BucketKeySchedule,
    BucketManifest,
    ManifestKdfParams,
    provision_bucket_directory,
    write_manifest,
)
from ....core.config import load_settings
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage

__all__ = ["isolated_profile_storage"]
from ._profile_lifecycle_support import create_profile_via_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_LEGACY_BUCKET_ID = "33333333-3333-4333-8333-333333333333"
_STAGED_CREATED_AT = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


def _stage_legacy_manifest(*, bucket_id: str, label: str) -> None:
    """Materialise a manifest that has no committed profile capsule."""
    root = load_settings().cadrumo_local_storage_root
    paths = provision_bucket_directory(root, bucket_id)
    write_manifest(
        paths,
        BucketManifest(
            bucket_id=bucket_id,
            label=label,
            created_at=_STAGED_CREATED_AT,
            last_unlocked_at=None,
            kdf_params=ManifestKdfParams(
                algorithm="argon2id",
                version=0x13,
                memory_cost=19_456,
                time_cost=2,
                parallelism=1,
                salt=b"0123456789abcdef",
                output_length=32,
            ),
            key_schedule=BucketKeySchedule.BUCKET_DEK_V1,
            schema_version=BUCKET_MANIFEST_SCHEMA_VERSION,
        ),
    )


def test_config_list_excludes_a_manifest_without_a_committed_capsule() -> None:
    create_profile_via_cli("workable")
    _stage_legacy_manifest(bucket_id=_LEGACY_BUCKET_ID, label="onboarding")

    result = _invoke(("config", "profile", "list"))

    assert result.exit_code == 0, result.output
    assert "workable" in result.output
    assert "onboarding" not in result.output


def test_overview_calendar_does_not_project_a_manifest_without_a_record() -> None:
    create_profile_via_cli("filer")
    _stage_legacy_manifest(bucket_id=_LEGACY_BUCKET_ID, label="onboarding")

    result = _invoke(
        (
            "app",
            "overview",
            "calendar",
            "--from",
            "2026-01-01",
            "--to",
            "2026-03-31",
            "--all-profiles",
            "--allow-incomplete",
        ),
    )

    assert result.exit_code == 0, result.output
    assert "profile_setup_incomplete" not in result.output
    assert "onboarding" not in result.output
