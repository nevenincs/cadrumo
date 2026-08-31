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
from pathlib import Path, PureWindowsPath
from typing import Literal

from pydantic import BaseModel

from .....core.identity import BucketId
from .....core.logging import get_logger
from .....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core.storage_taxonomy import StorageCategory
from .....core.storage_taxonomy_locations import storage_location
from .errors import BucketValidationError

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


def validate_path_component(value: str, *, subject: str) -> None:
    """Refuse ``value`` unless it is one path component that stays where it is joined.

    Every storage path built from a caller-supplied string needs this same
    answer, and the rule was previously written out at each join instead. Three
    copies drifted apart: ``bucket_paths`` and :func:`keystore_path` each
    enumerated the empty and separator cases, and the keystore sidecar join
    validated its ``bucket_id`` while never looking at its ``filename`` at all.

    Four ways a value fails to be a component, each measured against a real
    join rather than reasoned about:

    - **Empty**, which joins to the parent itself.
    - **Carrying a separator**, the only case all three copies caught.
    - **A dot segment.** ``".."`` carries no separator, so a separator check
      passes it, and the join then resolves ABOVE the directory being addressed.
    - **Drive-qualified.** ``"D:x"`` resolves onto another drive entirely, and
      ``"C:x"`` -- when the root is already on ``C:`` -- silently becomes the
      component ``"x"``, so the directory name no longer equals the identifier
      that named it and two distinct ids can land on one directory.

    Raises:
        BucketValidationError: When ``value`` is not a single containable
            component; ``subject`` names the offending parameter.
    """
    if not value:
        raise BucketValidationError(f"{subject} must be non-empty")
    if "/" in value or "\\" in value:
        raise BucketValidationError(f"{subject} must not contain a path separator")
    if set(value) == {"."}:
        raise BucketValidationError(f"{subject} must not be a dot segment")
    windows_reading = PureWindowsPath(value)
    if windows_reading.drive or windows_reading.root:
        raise BucketValidationError(f"{subject} must not be drive-qualified")


def bucket_paths(root: Path, bucket_id: str) -> BucketPaths:
    """Resolve the typed paths for ``<root>/buckets/<bucket_id>/`` without IO.

    The id is checked by :func:`validate_path_component` before it is joined,
    so it must be one containable component. Nothing reaches this with a
    hostile id today -- a restored archive's ``bucket_id`` must equal the
    custody envelope's ``profile_id``, which is a UUID, and the system-scoped
    ids are ``system``, ``unsecured`` and ``diagnostic-probe``. But that
    containment lives upstream in an identity cross-check written for another
    purpose, while :data:`BucketId` itself is a 1-128 character string that
    admits ``".."`` happily. Refusing it HERE puts the guarantee at the
    boundary that owns the join.

    Args:
        root: Cadrumo storage root (the parent of ``buckets/``).
        bucket_id: The bucket identifier; must be one path component.

    Returns:
        A :class:`BucketPaths` record carrying every resolved subpath.

    Raises:
        BucketValidationError: When ``bucket_id`` is not a single containable
            path component; see :func:`validate_path_component`.
    """
    validate_path_component(bucket_id, subject="bucket_id")

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
    "validate_path_component",
]
