"""Per-bucket directory model under ``<aeat-root>/buckets/<bucket-id>/``.

Pydantic v2 strict records, error types, and (in later phases) the
filesystem provisioning, manifest read/write, keystore separation,
pointer-file, and lockfile primitives that compose the multi-bucket
on-disk layout.
"""

from __future__ import annotations

from ._export_header import ExportArchiveHeader
from ._manifest import BucketManifest, KdfParams

__all__ = [
    "BucketManifest",
    "ExportArchiveHeader",
    "KdfParams",
]
