"""Filesystem provisioning and path resolution for per-bucket directories.

The per-bucket on-disk model lives at ``<cadrumo-root>/buckets/<bucket-id>/``
and carries exactly two subdirectories:

- ``db/``    relational state (SQLite database files).
- ``blobs/`` opaque artefact storage (sealed ciphertext blobs).

This module RESOLVES that layout and destroys it; it does not create it. A
bucket root comes into existence exactly once, by capsule publication's atomic
no-replace rename, and a second creator here would target the very directory
that rename must claim -- measured, ``bucket_paths(...).bucket_dir`` and the
capsule commit marker's parent are the same path. The test-only provisioner
that used to live here now sits in the wheel-excluded test package.

The typed :class:`BucketPaths` record carries each resolved subpath so callers
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
from ._errors import BucketValidationError

_log = get_logger(__name__)


class BucketPaths(BaseModel):
    """Typed record carrying the resolved paths for one bucket directory."""

    model_config = _STRICT_FROZEN

    bucket_id: BucketId
    root: Path
    bucket_dir: Path
    db_dir: Path
    blobs_dir: Path
    database_file: Path
    """The bucket's database file.

    Resolved here rather than composed by callers. Seventeen test modules were
    hand-building it as ``storage_root / "buckets" / id / "db" / "cadrumo.db"``
    precisely because this record carried every sibling directory but not the
    one file inside them.

    The composition is easy to get wrong in a way that fails late:
    ``BUCKET_DATABASE_FILE``'s subpath is ``db/cadrumo.db`` -- bucket-relative,
    already carrying its own ``db/`` segment -- so it joins onto ``bucket_dir``.
    Joining it onto ``db_dir`` yields ``<bucket>/db/db/cadrumo.db``, a path
    nothing creates, surfacing as a missing file rather than a wrong join. That
    is the ``blobs/blobs`` shape: the wrong anchor, not a wrong constant.
    """


def bucket_paths(root: Path, bucket_id: str) -> BucketPaths:
    """Resolve the typed paths for ``<root>/buckets/<bucket_id>/`` without IO.

    A dot segment is refused for the same reason a separator is. ``".."``
    carries no separator, so the check below it passes, and the join then
    resolves to the storage root -- one level ABOVE the ``buckets/`` directory
    this function exists to address. ``"."`` addresses ``buckets/`` itself.
    Neither is a bucket, and both would hand a caller paths over a tree the
    layout never meant to expose.

    Nothing reaches this with a dot segment today: a restored archive's
    ``bucket_id`` must equal the custody envelope's ``profile_id``, which is a
    UUID, and the system-scoped ids in the tree are ``system``, ``unsecured``
    and ``diagnostic-probe``. But that containment lives upstream, in an
    identity cross-check written for a different purpose, while
    :data:`BucketId` itself is a 1-128 character string
    that admits ``".."`` happily. Refusing it HERE puts the guarantee at the
    boundary that owns the join, so a future caller resolving an id from an
    untrusted source inherits the refusal rather than the traversal.

    Args:
        root: Cadrumo storage root (the parent of ``buckets/``).
        bucket_id: The bucket identifier; must be non-empty.

    Returns:
        A :class:`BucketPaths` record carrying every resolved subpath.

    Raises:
        BucketValidationError: When ``bucket_id`` is empty, is a dot segment, or
            contains a path separator.
    """
    if not bucket_id:
        raise BucketValidationError("bucket_id must be non-empty")
    if "/" in bucket_id or "\\" in bucket_id:
        raise BucketValidationError("bucket_id must not contain a path separator")
    if set(bucket_id) == {"."}:
        raise BucketValidationError("bucket_id must not be a dot segment")

    bucket_dir = root / storage_location(StorageCategory.BUCKETS).relative_path() / bucket_id
    return BucketPaths(
        bucket_id=bucket_id,
        root=root,
        bucket_dir=bucket_dir,
        db_dir=bucket_dir / storage_location(StorageCategory.BUCKET_DATABASE).relative_path(),
        blobs_dir=bucket_dir / storage_location(StorageCategory.BUCKET_BLOBS).relative_path(),
        # Anchored on bucket_dir, not db_dir: this member's subpath already
        # carries its own db/ segment. See the field's docstring.
        database_file=bucket_dir / storage_location(StorageCategory.BUCKET_DATABASE_FILE).relative_path(),
    )


def trash_rename_and_remove(
    target: Path,
    *,
    on_trash_cleanup_error: Literal["raise", "ignore"] = "raise",
) -> None:
    """Trash-rename ``target`` then recursively remove it.

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
    "trash_rename_and_remove",
]
