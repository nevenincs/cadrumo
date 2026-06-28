"""Per-bucket directory model under ``<aeat-root>/buckets/<bucket-id>/``.

Pydantic v2 strict records, error types, and the filesystem
provisioning, manifest read/write, keystore separation, pointer-file,
and lockfile primitives that compose the multi-bucket on-disk layout.
"""

from __future__ import annotations

from ._errors import (
    BucketAlreadyPresentError,
    BucketBusyError,
    BucketError,
    BucketLockedError,
    BucketValidationError,
    NoActiveBucketError,
    RecoveryUnavailableError,
    RecoveryVerificationError,
)
from ._export_header import ExportArchiveHeader
from ._keystore_paths import keystore_path, keystore_root, validate_keystore_separation
from ._layout import BucketPaths, bucket_paths, provision_bucket_directory
from ._lockfile import acquire_lock, lock_path, release_lock
from ._manifest import BucketKeySchedule, BucketLifecycleStatus, BucketManifest, ManifestKdfParams
from ._manifest_io import manifest_path, read_manifest, write_manifest
from ._sealed_archive_reader import SealedArchiveContents, read_sealed_archive
from ._sealed_archive_writer import write_sealed_archive

__all__ = [
    "BucketAlreadyPresentError",
    "BucketBusyError",
    "BucketError",
    "BucketKeySchedule",
    "BucketLifecycleStatus",
    "BucketLockedError",
    "BucketManifest",
    "BucketPaths",
    "BucketValidationError",
    "ExportArchiveHeader",
    "ManifestKdfParams",
    "NoActiveBucketError",
    "RecoveryUnavailableError",
    "RecoveryVerificationError",
    "SealedArchiveContents",
    "acquire_lock",
    "bucket_paths",
    "keystore_path",
    "keystore_root",
    "lock_path",
    "manifest_path",
    "provision_bucket_directory",
    "read_manifest",
    "read_sealed_archive",
    "release_lock",
    "validate_keystore_separation",
    "write_manifest",
    "write_sealed_archive",
]
