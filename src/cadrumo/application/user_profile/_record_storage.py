"""Application ports for the physical profile-record projections.

The aggregate repository sequences several durable projections, but it does
not own their filesystem, manifest, or SQL implementations.  This module is
the application-side port for that work.  The default provider binds the port
to the real persistence adapter at the composition boundary; callers that
already own a storage lifetime can inject the same port explicitly.

The storage models deliberately remain opaque to the application port.  They
are persisted-format records owned by the storage adapter, while the
application owns the ordering and cross-store invariants around them.
"""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Any, Protocol, cast

from ...domain.buckets import BucketEventHistoryRepositoryProtocol


class ProfileAggregateStoragePort(Protocol):
    """Physical capabilities required by the profile aggregate repository."""

    buckets_dirname: str
    bucket_dek_filename: str
    manifest_schema_version: int
    storage_validation_error_type: type[Exception]

    def storage_validation_error(self, *, translated_message: str, context: dict[str, object]) -> Exception:
        """Build the adapter's storage-validation error at the boundary."""
        ...

    def default_kdf_params(self) -> Any:
        """Return the canonical fresh-bucket manifest KDF parameters."""
        ...

    def bucket_dek_v1_schedule(self) -> Any:
        """Return the current encrypted-bucket key schedule discriminator."""
        ...

    def bucket_paths(self, root: Path, profile_id: str) -> Any:
        """Resolve the canonical physical paths for one profile bucket."""
        ...

    def keystore_path(self, root: Path, profile_id: str) -> Path:
        """Resolve the profile's separated keystore directory."""
        ...

    def manifest_path(self, paths: Any) -> Path:
        """Resolve the manifest file for one bucket path record."""
        ...

    def provision_bucket_directory(self, root: Path, profile_id: str) -> Any:
        """Provision a fresh bucket directory through the storage adapter."""
        ...

    def read_manifest(self, paths: Any) -> Any:
        """Read and validate one current-format bucket manifest."""
        ...

    def write_manifest(self, paths: Any, manifest: Any) -> None:
        """Atomically persist one validated bucket manifest."""
        ...

    def build_manifest(self, **fields: Any) -> Any:
        """Build the adapter-owned manifest model from application fields."""
        ...

    def trash_rename_and_remove(self, target: Path) -> None:
        """Remove one staged bucket through the storage rollback primitive."""
        ...

    def dispose_engines_for_bucket(self, profile_id: str) -> None:
        """Release any live SQL handles for one bucket during rollback."""
        ...


class _PersistenceProfileAggregateStorage:
    """Adapt the public persistence facades to the application port."""

    def __init__(self) -> None:
        storage = import_module("cadrumo.adapters.persistence.storage")
        bucket = import_module("cadrumo.adapters.persistence.storage.bucket")
        master_key = import_module("cadrumo.adapters.persistence.storage.master_key")
        self._storage = storage
        self._bucket = bucket
        self._master_key = master_key
        self.buckets_dirname = storage.BUCKETS_DIRNAME
        self.bucket_dek_filename = storage.BUCKET_DEK_FILENAME
        self.manifest_schema_version = bucket.BUCKET_MANIFEST_SCHEMA_VERSION
        self.storage_validation_error_type = cast(type[Exception], storage.StorageValidationError)

    def storage_validation_error(self, *, translated_message: str, context: dict[str, object]) -> Exception:
        """Build the adapter's storage-validation error at the boundary."""
        error_type = cast(Any, self.storage_validation_error_type)
        error = error_type(translated_message=translated_message, context=context)
        if not isinstance(error, Exception):
            raise TypeError("storage validation provider returned a non-exception")
        return error

    def default_kdf_params(self) -> Any:
        """Return the canonical fresh-bucket manifest KDF parameters."""
        kdf_type = self._master_key.KdfParams
        return kdf_type.default().to_manifest_params()

    def bucket_dek_v1_schedule(self) -> Any:
        """Return the current encrypted-bucket key schedule discriminator."""
        schedule_type = self._bucket.BucketKeySchedule
        return schedule_type.BUCKET_DEK_V1

    def bucket_paths(self, root: Path, profile_id: str) -> Any:
        """Resolve the canonical physical paths for one profile bucket."""
        return self._bucket.bucket_paths(root, profile_id)

    def keystore_path(self, root: Path, profile_id: str) -> Path:
        """Resolve the profile's separated keystore directory."""
        return self._bucket.keystore_path(root, profile_id)

    def manifest_path(self, paths: Any) -> Path:
        """Resolve the manifest file for one bucket path record."""
        return self._bucket.manifest_path(paths)

    def provision_bucket_directory(self, root: Path, profile_id: str) -> Any:
        """Provision a fresh bucket directory through the storage adapter."""
        return self._bucket.provision_bucket_directory(root, profile_id)

    def read_manifest(self, paths: Any) -> Any:
        """Read and validate one current-format bucket manifest."""
        return self._bucket.read_manifest(paths)

    def write_manifest(self, paths: Any, manifest: Any) -> None:
        """Atomically persist one validated bucket manifest."""
        self._bucket.write_manifest(paths, manifest)

    def build_manifest(self, **fields: Any) -> Any:
        """Build the adapter-owned manifest model from application fields."""
        manifest_type = self._bucket.BucketManifest
        return manifest_type(**fields)

    def trash_rename_and_remove(self, target: Path) -> None:
        """Remove one staged bucket through the storage rollback primitive."""
        self._bucket.trash_rename_and_remove(target)

    def dispose_engines_for_bucket(self, profile_id: str) -> None:
        """Release any live SQL handles for one bucket during rollback."""
        self._storage.dispose_engines_for_bucket(profile_id)


def default_profile_aggregate_storage() -> ProfileAggregateStoragePort:
    """Return the real profile storage adapter through the application port."""
    return _PersistenceProfileAggregateStorage()


class _PersistenceBucketEventHistoryModule(Protocol):
    """Public adapter facade needed to construct the event-history port."""

    BucketEventHistoryRepository: type[BucketEventHistoryRepositoryProtocol]


def default_bucket_event_history_repository() -> BucketEventHistoryRepositoryProtocol:
    """Return the concrete event-history adapter through its domain port."""
    module = cast(
        _PersistenceBucketEventHistoryModule,
        import_module("cadrumo.adapters.persistence.profile.buckets"),
    )
    return module.BucketEventHistoryRepository()


__all__ = [
    "ProfileAggregateStoragePort",
    "default_bucket_event_history_repository",
    "default_profile_aggregate_storage",
]
