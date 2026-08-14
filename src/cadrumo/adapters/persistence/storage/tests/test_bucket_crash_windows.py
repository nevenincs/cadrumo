"""Storage-boundary tests for torn current-format bucket metadata."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from .....adapters.persistence.storage.bucket import (
    BUCKET_MANIFEST_SCHEMA_VERSION,
    BucketKeySchedule,
    BucketManifest,
    ManifestKdfParams,
    manifest_path,
    provision_bucket_directory,
    read_manifest,
    write_manifest,
)
from .....core.errors import CadrumoError

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def _manifest(bucket_id: str) -> BucketManifest:
    return BucketManifest(
        bucket_id=bucket_id,
        label="Storage test profile",
        created_at=datetime(2026, 6, 1, 9, 0, tzinfo=UTC),
        last_unlocked_at=None,
        kdf_params=ManifestKdfParams(
            algorithm="argon2id",
            version=19,
            memory_cost=19_456,
            time_cost=2,
            parallelism=1,
            salt=b"0123456789abcdef",
            output_length=32,
        ),
        key_schedule=BucketKeySchedule.BUCKET_DEK_V1,
        schema_version=BUCKET_MANIFEST_SCHEMA_VERSION,
    )


def test_manifest_roundtrip_preserves_current_identity(tmp_path: Path) -> None:
    paths = provision_bucket_directory(tmp_path, "11111111-1111-4111-8111-111111111111")
    original = _manifest(paths.bucket_id)
    write_manifest(paths, original)

    assert read_manifest(paths) == original


def test_torn_manifest_is_refused_instead_of_projected(tmp_path: Path) -> None:
    paths = provision_bucket_directory(tmp_path, "22222222-2222-4222-8222-222222222222")
    write_manifest(paths, _manifest(paths.bucket_id))
    manifest_path(paths).write_text("this is not valid toml = = =\n", encoding="utf-8")

    with pytest.raises(CadrumoError):
        read_manifest(paths)
