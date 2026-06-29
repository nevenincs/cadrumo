from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from ......core.config import SecretStoreBackend, Settings
from ...bucket._layout import provision_bucket_directory
from ...bucket._manifest import (
    BucketKeySchedule,
    BucketLifecycleStatus,
    BucketManifest,
    ManifestKdfParams,
)
from ...bucket._manifest_io import write_manifest


class _InMemoryKeyringClient:
    """Protocol-compatible keyring client backed by an in-process dict."""

    def __init__(
        self,
        *,
        probe: Callable[[], None] | None = None,
        get: Callable[[str, str], str | None] | None = None,
        set_: Callable[[str, str, str], None] | None = None,
        seeded: dict[tuple[str, str], str] | None = None,
    ) -> None:
        self._probe = probe or (lambda: None)
        self._store: dict[tuple[str, str], str] = dict(seeded or {})
        self._get_override = get
        self._set_override = set_

    def probe_backend(self) -> None:
        self._probe()

    def get_password(self, service: str, username: str) -> str | None:
        if self._get_override is not None:
            return self._get_override(service, username)
        return self._store.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        if self._set_override is not None:
            self._set_override(service, username, password)
            return
        self._store[(service, username)] = password


def _settings_with_store(tmp_path: Path, backend: SecretStoreBackend) -> Settings:
    return Settings(
        aeat_local_storage_root=tmp_path / "state",
        aeat_secret_store_dir=tmp_path / "secrets",
        aeat_secret_store_backend=backend,
    )


def _write_registered_bucket(
    root: Path,
    bucket_id: str,
    *,
    idle_lock_minutes: int | None = None,
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
            key_schedule=key_schedule,
            schema_version=1,
            status=BucketLifecycleStatus.ACTIVE,
        ),
    )
