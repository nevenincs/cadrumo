"""Per-bucket directory model under ``<aeat-root>/buckets/<bucket-id>/``.

Pydantic v2 strict records, error types, and (in later phases) the
filesystem provisioning, manifest read/write, keystore separation,
pointer-file, and lockfile primitives that compose the multi-bucket
on-disk layout.
"""

from __future__ import annotations

from ._errors import (
    BucketAlreadyPresentError,
    BucketBusyError,
    BucketError,
    BucketLockedError,
    LegacyLayoutDetectedError,
    NoActiveBucketError,
    RecoveryUnavailableError,
    RecoveryVerificationError,
)
from ._export_header import ExportArchiveHeader
from ._layout import BucketPaths, bucket_paths, provision_bucket_directory
from ._manifest import BucketManifest, KdfParams
from ._manifest_io import manifest_path, read_manifest, write_manifest

__all__ = [
    "BucketAlreadyPresentError",
    "BucketBusyError",
    "BucketError",
    "BucketLockedError",
    "BucketManifest",
    "BucketPaths",
    "ExportArchiveHeader",
    "KdfParams",
    "LegacyLayoutDetectedError",
    "NoActiveBucketError",
    "RecoveryUnavailableError",
    "RecoveryVerificationError",
    "bucket_paths",
    "manifest_path",
    "provision_bucket_directory",
    "read_manifest",
    "write_manifest",
]
