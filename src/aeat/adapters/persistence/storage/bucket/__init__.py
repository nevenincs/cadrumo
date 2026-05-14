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
from ._manifest import BucketManifest, KdfParams

__all__ = [
    "BucketAlreadyPresentError",
    "BucketBusyError",
    "BucketError",
    "BucketLockedError",
    "BucketManifest",
    "ExportArchiveHeader",
    "KdfParams",
    "LegacyLayoutDetectedError",
    "NoActiveBucketError",
    "RecoveryUnavailableError",
    "RecoveryVerificationError",
]
