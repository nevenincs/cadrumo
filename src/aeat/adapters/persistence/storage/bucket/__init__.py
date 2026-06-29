"""Per-bucket directory model under ``<aeat-root>/buckets/<bucket-id>/``.

Pydantic v2 strict records, error types, and the filesystem
provisioning, manifest read/write, keystore separation, pointer-file,
and lockfile primitives that compose the multi-bucket on-disk layout.

The sealed-archive surface re-exports :class:`ExportArchiveHeader`,
:class:`SealedArchiveContents`, :func:`write_sealed_archive`, and
:func:`read_sealed_archive` for application-level bucket export/import. These
helpers own archive shape and metadata normalisation only; profile payload
composition remains in :mod:`aeat.application.user_profile`, while
:mod:`aeat.application.bucket_maintenance` orchestrates operator-facing export
and import.

See Also:
    :class:`BucketManifest`
        Strict per-bucket manifest record stored beside the bucket directory.
    :class:`ExportArchiveHeader`
        Plaintext frontmatter for sealed bucket-export archives.
    :func:`write_sealed_archive`
        Host-metadata-normalising writer for sealed export archives.
    :func:`read_sealed_archive`
        Reader that validates archive member order and header shape before
        returning encrypted payload bytes.
    :mod:`aeat.application.bucket_maintenance`
        Application service facade that composes these archive primitives with
        profile lifecycle and domain event history.
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
