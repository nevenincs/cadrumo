"""Filesystem provisioning and path resolution for per-bucket directories.

The per-bucket on-disk model lives at ``<cadrumo-root>/buckets/<bucket-id>/``
and carries exactly two subdirectories:

- ``db/``    relational state (SQLite database files).
- ``blobs/`` opaque artefact storage (sealed ciphertext blobs).

This module RESOLVES that layout; it does not create or destroy it. A
bucket root comes into existence exactly once, by capsule publication's atomic
no-replace rename, and a second creator here would target the very directory
that rename must claim -- measured, ``bucket_paths(...).bucket_dir`` and the
capsule commit marker's parent are the same path. The test-only provisioner
that used to live here now sits in the wheel-excluded test package.

The typed :class:`BucketPaths` record carries each resolved subpath so callers
never compose the layout themselves.
"""

from __future__ import annotations

from pathlib import Path, PureWindowsPath

from pydantic import BaseModel

from .....core.identity import BucketId
from .....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core.storage_taxonomy import StorageCategory
from .....core.storage_taxonomy_locations import storage_location
from .errors import BucketValidationError


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


__all__ = [
    "BucketPaths",
    "bucket_paths",
    "validate_path_component",
]
