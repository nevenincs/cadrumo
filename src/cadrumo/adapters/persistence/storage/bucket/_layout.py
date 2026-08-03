"""Filesystem provisioning and path resolution for per-bucket directories.

The per-bucket on-disk model lives at ``<cadrumo-root>/buckets/<bucket-id>/``
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

import gc
import secrets
import shutil
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from .....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core import StorageCategory, storage_location
from .....core.identity import BucketId
from .....core.logging import get_logger
from .....core.paths import is_windows_long_path_error
from ._errors import BucketAlreadyPresentError, BucketPathTooLongError, BucketValidationError

_log = get_logger(__name__)


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
        root: Cadrumo storage root (the parent of ``buckets/``).
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

    bucket_dir = root / storage_location(StorageCategory.BUCKETS).relative_path() / bucket_id
    return BucketPaths(
        bucket_id=bucket_id,
        root=root,
        bucket_dir=bucket_dir,
        db_dir=bucket_dir / storage_location(StorageCategory.BUCKET_DATABASE).relative_path(),
        blobs_dir=bucket_dir / storage_location(StorageCategory.BUCKET_BLOBS).relative_path(),
        audit_dir=bucket_dir / storage_location(StorageCategory.BUCKET_AUDIT).relative_path(),
    )


def provision_bucket_directory(root: Path, bucket_id: str) -> BucketPaths:
    """Materialise the ``<root>/buckets/<bucket_id>/{db,blobs,audit}/`` tree.

    Provisioning is fail-closed: if the bucket directory already exists,
    the function raises rather than reusing the partial state. The parent
    ``<root>/buckets/`` directory is created lazily.

    Args:
        root: Cadrumo storage root (the parent of ``buckets/``).
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
    except OSError as exc:
        if is_windows_long_path_error(exc):
            raise BucketPathTooLongError(bucket_id=bucket_id, path=str(paths.bucket_dir)) from exc
        raise
    return paths


def trash_rename_and_remove(
    target: Path,
    *,
    on_trash_cleanup_error: Literal["raise", "ignore"] = "raise",
) -> None:
    """Trash-rename ``target`` then recursively remove it — the destroy sibling of :func:`provision_bucket_directory`.

    The directory is first renamed to a same-parent ``.trash-<name>-<hex>``
    sibling so a crashed removal leaves a recoverable on-disk trace, then
    recursively deleted. When the rename itself is refused (Windows denies
    renaming a directory whose SQLite file was only just closed), a garbage
    collection pass releases lingering handles and the directory is removed
    in place instead — the exact same fallback shape either way, just
    against a different path.

    ``on_trash_cleanup_error`` governs only the final ``rmtree`` step (never
    the rename): ``"raise"`` (the default) lets a genuine :class:`OSError`
    from the recursive removal propagate — load-bearing for a create-rollback
    caller that must surface a cleanup failure alongside the original create
    failure. ``"ignore"`` removes best-effort and returns normally regardless
    of outcome — leftover trash litter is an acceptable outcome for an
    ordinary delete. A caller on ``"ignore"`` that must still know whether the
    directory genuinely disappeared checks ``target.exists()`` itself
    afterward and raises its own (possibly domain-typed) error.

    Callers check ``target.exists()`` before calling; this function does not
    special-case an already-absent target.

    Args:
        target: The bucket directory (or any directory) to trash-rename and
            remove.
        on_trash_cleanup_error: The final-removal error policy described
            above.
    """
    trash = target.with_name(f".trash-{target.name}-{secrets.token_hex(4)}")
    try:
        target.rename(trash)
    except OSError:
        # The crash-safe rename was refused (a file handle still held, most
        # often on Windows); release lingering handles and remove the
        # original directory in place instead of the trash sibling.
        gc.collect()
        _remove_tree(target, on_error=on_trash_cleanup_error)
        return
    _remove_tree(trash, on_error=on_trash_cleanup_error)


def _remove_tree(path: Path, *, on_error: Literal["raise", "ignore"]) -> None:
    """``rmtree`` under the given error policy; see :func:`trash_rename_and_remove`."""
    if on_error == "ignore":
        shutil.rmtree(path, ignore_errors=True)
        return
    try:
        shutil.rmtree(path)
    except OSError:
        _log.debug("trash_rename_and_remove: could not remove %s", path, exc_info=True)
        raise


__all__ = [
    "BucketPaths",
    "bucket_paths",
    "provision_bucket_directory",
    "trash_rename_and_remove",
]
