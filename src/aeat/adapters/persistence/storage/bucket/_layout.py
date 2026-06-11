"""Filesystem provisioning and path resolution for per-bucket directories.

The per-bucket on-disk model lives at ``<aeat-root>/buckets/<bucket-id>/``
and carries exactly three subdirectories:

- ``db/``    relational state (SQLite database files).
- ``blobs/`` opaque artefact storage (sealed ciphertext blobs).
- ``audit/`` append-only audit-trail log files.

Provisioning is fail-closed: a re-attempt against an already-provisioned
bucket id raises rather than silently masking a configuration error. The
typed :class:`BucketPaths` record carries each resolved subpath so callers
never compose the layout themselves.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from .....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core.identity import BucketId
from .._namespace_registry import (
    BUCKET_AUDIT_DIRNAME,
    BUCKET_BLOBS_DIRNAME,
    BUCKET_DB_DIRNAME,
    BUCKETS_DIRNAME,
)
from ._errors import BucketAlreadyPresentError, BucketValidationError


class BucketPaths(BaseModel):
    """Typed record carrying the resolved paths for one bucket directory."""

    model_config = _STRICT_FROZEN

    bucket_id: BucketId
    root: Path
    bucket_dir: Path
    db_dir: Path
    blobs_dir: Path
    audit_dir: Path


def bucket_paths(root: Path, bucket_id: str) -> BucketPaths:
    """Resolve the typed paths for ``<root>/buckets/<bucket_id>/`` without IO.

    Args:
        root: AEAT root directory (the parent of ``buckets/``).
        bucket_id: The bucket identifier; must be non-empty.

    Returns:
        A :class:`BucketPaths` record carrying every resolved subpath.

    Raises:
        BucketValidationError: When ``bucket_id`` is empty or contains a path separator.
    """
    if not bucket_id:
        raise BucketValidationError("bucket_id must be non-empty")
    if "/" in bucket_id or "\\" in bucket_id:
        raise BucketValidationError("bucket_id must not contain a path separator")

    bucket_dir = root / BUCKETS_DIRNAME / bucket_id
    return BucketPaths(
        bucket_id=bucket_id,
        root=root,
        bucket_dir=bucket_dir,
        db_dir=bucket_dir / BUCKET_DB_DIRNAME,
        blobs_dir=bucket_dir / BUCKET_BLOBS_DIRNAME,
        audit_dir=bucket_dir / BUCKET_AUDIT_DIRNAME,
    )


def provision_bucket_directory(root: Path, bucket_id: str) -> BucketPaths:
    """Materialise the ``<root>/buckets/<bucket_id>/{db,blobs,audit}/`` tree.

    Provisioning is fail-closed: if the bucket directory already exists,
    the function raises rather than reusing the partial state. The parent
    ``<root>/buckets/`` directory is created lazily.

    Args:
        root: AEAT root directory (the parent of ``buckets/``).
        bucket_id: The bucket identifier; must be non-empty.

    Returns:
        A :class:`BucketPaths` record carrying every resolved subpath.
    """
    paths = bucket_paths(root, bucket_id)
    try:
        paths.bucket_dir.parent.mkdir(parents=True, exist_ok=True)
        paths.bucket_dir.mkdir(parents=False, exist_ok=False)
        paths.db_dir.mkdir(parents=False, exist_ok=False)
        paths.blobs_dir.mkdir(parents=False, exist_ok=False)
        paths.audit_dir.mkdir(parents=False, exist_ok=False)
    except FileExistsError as exc:
        raise BucketAlreadyPresentError(bucket_id=bucket_id) from exc
    return paths


__all__ = ["BucketPaths", "bucket_paths", "provision_bucket_directory"]
