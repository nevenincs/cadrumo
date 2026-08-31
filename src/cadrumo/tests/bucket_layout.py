"""Test-only provisioning of a bucket directory tree.

This provisioner used to live in the production bucket adapter, where it was a
SECOND creator of a bucket root with no production caller at all. That matters
more than dead weight: measured, ``bucket_paths(root, id).bucket_dir`` and the
parent of the capsule commit marker are the SAME path, so a wired-up second
creator would not merely resemble the capsule-publication collision this
campaign already fixed -- it would reproduce it, in the same directory.

A bucket root comes into existence exactly once in production, by capsule
publication's atomic no-replace rename. Publication is not a substitute for
what this function does, and that is why the capability moved here rather than
being deleted: publication writes the commit marker and creates no ``db/`` or
``blobs/`` children, while the tests that call this are about manifest
input-output, lockfiles, layout and the language hint -- they need the tree and
never publish at all.

Living here rather than in the adapter is the whole point. ``src/cadrumo/tests``
is excluded from the wheel, so the second creator is absent from the shipped
package as well as from the production surface, and nothing an operator runs
can reach it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..adapters.persistence.storage.bucket.directory_layout import bucket_paths
from ..adapters.persistence.storage.bucket.errors import BucketAlreadyPresentError, BucketPathTooLongError
from ..core.paths import is_windows_long_path_error

if TYPE_CHECKING:
    from pathlib import Path

    from ..adapters.persistence.storage.bucket.directory_layout import BucketPaths

__all__ = ["provision_bucket_directory"]


def provision_bucket_directory(root: Path, bucket_id: str) -> BucketPaths:
    """Materialise the ``<root>/buckets/<bucket_id>/{db,blobs}/`` tree.

    Provisioning is fail-closed: if the bucket directory already exists, this
    raises rather than reusing the partial state. The parent ``<root>/buckets/``
    directory is created lazily.

    Args:
        root: Cadrumo storage root (the parent of ``buckets/``).
        bucket_id: The bucket identifier; must be non-empty.

    Returns:
        A :class:`BucketPaths` record carrying every resolved subpath.

    Raises:
        BucketValidationError: When ``bucket_id`` is empty or carries a separator.
        BucketAlreadyPresentError: When the bucket directory already exists.
        BucketPathTooLongError: When Windows refuses the path length.
    """
    paths = bucket_paths(root, bucket_id)
    try:
        paths.bucket_dir.parent.mkdir(parents=True, exist_ok=True)
        paths.bucket_dir.mkdir(parents=False, exist_ok=False)
        paths.db_dir.mkdir(parents=False, exist_ok=False)
        paths.blobs_dir.mkdir(parents=False, exist_ok=False)
    except FileExistsError as exc:
        raise BucketAlreadyPresentError(bucket_id=bucket_id) from exc
    except OSError as exc:
        if is_windows_long_path_error(exc):
            raise BucketPathTooLongError(bucket_id=bucket_id, path=str(paths.bucket_dir)) from exc
        raise
    return paths
