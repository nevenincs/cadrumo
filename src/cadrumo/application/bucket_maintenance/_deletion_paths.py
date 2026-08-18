"""Deletion-path validation for the bucket-maintenance service.

Used by: :class:`~application.bucket_maintenance.BucketMaintenanceService`
to resolve the deletion paths of a real, non-link bucket root before any
manifest read or destructive assessment.

The check runs before manifest reads so a symlink or Windows junction
cannot redirect assessment into storage outside the configured bucket
directory.
"""

from __future__ import annotations

from pathlib import Path

from ...adapters.persistence.storage.bucket import (
    BucketPaths,
    bucket_paths,
)
from ...core import is_link_like


def validated_bucket_deletion_paths(*, root: Path, bucket_id: str) -> BucketPaths:
    """Return deletion paths only for a real, non-link bucket root."""
    paths = bucket_paths(root, bucket_id)
    if is_link_like(paths.bucket_dir):
        raise ValueError(f"bucket deletion refuses linked bucket root: {paths.bucket_dir}")
    if not paths.bucket_dir.is_dir():
        raise FileNotFoundError(paths.bucket_dir)
    return paths


__all__ = [
    "validated_bucket_deletion_paths",
]
