from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from ......core.config import SecretStoreBackend, Settings
from ......domain.user_profile import UserProfileStatus
from ...bucket import (
    BUCKET_MANIFEST_SCHEMA_VERSION,
    BucketKeySchedule,
    BucketManifest,
    ManifestKdfParams,
    provision_bucket_directory,
    write_manifest,
)


def _settings_with_store(tmp_path: Path, backend: SecretStoreBackend) -> Settings:
    return Settings(
        cadrumo_local_storage_root=tmp_path / "state",
        cadrumo_secret_store_dir=tmp_path / "secrets",
        cadrumo_secret_store_backend=backend,
    )


def _write_registered_bucket(
    root: Path,
    bucket_id: str,
    *,
    idle_lock_minutes: int | None = None,
    session_absolute_minutes: int | None = None,
    key_schedule: BucketKeySchedule = BucketKeySchedule.BUCKET_DEK_V1,
) -> None:
    paths = provision_bucket_directory(root, bucket_id)
    write_manifest(
        paths,
        BucketManifest(
            bucket_id=bucket_id,
            label=bucket_id,
            created_at=datetime(2026, 5, 22, 12, 0, 0, tzinfo=UTC),
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
            recovery_enrolled=False,
            idle_lock_minutes=idle_lock_minutes,
            session_absolute_minutes=session_absolute_minutes,
            key_schedule=key_schedule,
            schema_version=BUCKET_MANIFEST_SCHEMA_VERSION,
            status=UserProfileStatus.ACTIVE,
        ),
    )
