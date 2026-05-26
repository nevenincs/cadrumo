"""Shared secure SQL isolation helpers for tests."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

from aeat.adapters.persistence.storage import EphemeralMasterKeyProvider
from aeat.adapters.persistence.storage.bucket._layout import BucketPaths, provision_bucket_directory
from aeat.adapters.persistence.storage.bucket._manifest import BucketLifecycleStatus, BucketManifest
from aeat.adapters.persistence.storage.bucket._manifest_io import write_manifest
from aeat.adapters.persistence.storage.master_key._active_session import activate_session
from aeat.adapters.persistence.storage.master_key._bucket_session import BucketSession
from aeat.adapters.persistence.storage.master_key._kdf_params import KdfParams
from aeat.adapters.persistence.storage.runtime import StorageRuntime, inspect_storage_runtime
from aeat.adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from aeat.adapters.persistence.storage.sql.engine import dispose_engine
from aeat.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from aeat.core.config import Settings, load_settings, override_settings

_TEST_KEK = b"t" * 32
_TEST_DEK = b"r" * 32


@dataclass(frozen=True)
class TestRuntimeProfile:
    """Real active-profile storage runtime created for tests."""

    __test__: ClassVar[bool] = False

    storage_root: Path
    bucket_id: str
    paths: BucketPaths
    settings: Settings
    runtime: StorageRuntime
    repository: SecureObjectRepository


def dev_test_database_password(settings: Settings | None = None) -> str:
    """Return the shared dev/test password for database-backed storage tests."""

    source = settings or load_settings()
    return source.aeat_dev_test_database_password.get_secret_value()


@contextmanager
def isolated_ephemeral_secure_sql(
    *,
    tmp_path: Path,
    database_name: str = "aeat.db",
) -> Iterator[None]:
    """Run test code with a temp SQL database and real ephemeral master key."""

    database_url = f"sqlite:///{(tmp_path / database_name).as_posix()}"
    with override_settings(
        aeat_database_url=database_url,
        aeat_secret_passphrase=load_settings().aeat_dev_test_database_password,
    ) as settings:
        dispose_engine(settings)
        with EphemeralMasterKeyProvider():
            try:
                yield
            finally:
                dispose_engine(settings)


@contextmanager
def isolated_runtime_profile(
    *,
    tmp_path: Path,
    bucket_id: str = "test-runtime-profile",
    label: str = "Test runtime profile",
) -> Iterator[TestRuntimeProfile]:
    """Create a real active-profile bucket runtime for tests.

    The helper provisions the same durable surfaces used by production:
    a bucket directory, plaintext manifest, active-profile settings route,
    active bucket session, and runtime-owned secure-object repository.
    """

    storage_root = tmp_path / "aeat-storage"
    opened_at = datetime.now(UTC).replace(microsecond=0)
    paths = provision_bucket_directory(storage_root, bucket_id)
    write_manifest(
        paths,
        BucketManifest(
            bucket_id=bucket_id,
            label=label,
            created_at=opened_at,
            last_unlocked_at=opened_at,
            kdf_params=KdfParams.default().to_manifest_params(),
            recovery_enrolled=False,
            schema_version=1,
            status=BucketLifecycleStatus.ACTIVE,
        ),
    )
    session = BucketSession.open(
        bucket_id=bucket_id,
        kek=_TEST_KEK,
        dek=_TEST_DEK,
        idle_minutes=15,
        opened_at=opened_at,
    )

    with override_settings(aeat_local_storage_root=storage_root, aeat_active_profile=bucket_id) as settings:
        dispose_engine(settings)
        with activate_session(session):
            runtime = inspect_storage_runtime(settings)
            repository = secure_object_repository_for_active_bucket()
            try:
                yield TestRuntimeProfile(
                    storage_root=storage_root,
                    bucket_id=bucket_id,
                    paths=paths,
                    settings=settings,
                    runtime=runtime,
                    repository=repository,
                )
            finally:
                dispose_engine(settings)


__all__ = [
    "TestRuntimeProfile",
    "dev_test_database_password",
    "isolated_ephemeral_secure_sql",
    "isolated_runtime_profile",
]
