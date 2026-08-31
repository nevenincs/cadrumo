"""Keystore separation contract enforcing the isolation invariant.

The KEK / DEK / passphrase / OS-keystore custody artefacts live under a
keystore root that is structurally outside the buckets parent. The two
invariants enforced here are:

- The keystore root is sibling to ``buckets/`` under the Cadrumo root
  (``<cadrumo-root>/keystore/<bucket-id>/``), never nested inside any bucket
  directory and never co-located under the relational database directory.
- A configuration that resolves the keystore path under either parent is
  rejected by :func:`validate_keystore_separation` so a subsequent unlock
  cannot silently violate the invariant.

The pure helpers do not materialise the directory; the cryptographic core
(P03) owns provisioning when an enrolment first lands.
"""

from __future__ import annotations

from pathlib import Path

from .....core.storage_taxonomy import StorageCategory
from .....core.storage_taxonomy_locations import storage_location
from ._layout import BucketPaths, bucket_paths, validate_path_component
from .errors import BucketValidationError

_KEYSTORE_VALIDATION_SURFACE = "bucket_keystore"


def keystore_root(root: Path) -> Path:
    """Return the keystore parent ``<root>/keystore/`` (no IO)."""
    return root / storage_location(StorageCategory.BUCKET_KEYSTORE).relative_path()


def keystore_path(root: Path, bucket_id: str) -> Path:
    """Return ``<root>/keystore/<bucket_id>/`` (no IO).

    Args:
        root: The Cadrumo storage root.
        bucket_id: Bucket identifier to include in the path.

    Returns:
        The computed keystore directory path.

    Raises:
        BucketValidationError: When ``bucket_id`` is empty or carries a path separator.
    """
    validate_path_component(bucket_id, subject="bucket_id")
    return keystore_root(root) / bucket_id


def _is_under(child: Path, parent: Path) -> bool:
    """True if ``child`` resolves to a path beneath ``parent``.

    Uses ``Path.relative_to`` semantics on the lexically-resolved forms so
    the check is OS-portable; symlink traversal is intentionally not
    followed because the call site validates configuration before any
    filesystem state exists.
    """
    try:
        resolved_child = child.resolve(strict=False)
        resolved_parent = parent.resolve(strict=False)
    except OSError:
        resolved_child = child
        resolved_parent = parent
    try:
        resolved_child.relative_to(resolved_parent)
    except ValueError:
        return False
    return True


def validate_keystore_separation(
    root: Path,
    bucket_id: str,
    *,
    configured_keystore: Path | None = None,
) -> None:
    """Fail closed if the keystore path resolves under the buckets parent or db dir.

    Args:
        root: The Cadrumo storage root.
        bucket_id: The bucket identifier whose layout to validate against.
        configured_keystore: Optional override path; defaults to
            :func:`keystore_path`. A custom configuration that points at a
            location nested under the buckets parent or the per-bucket
            relational database directory is rejected.

    Raises:
        BucketValidationError: When the configured keystore path violates separation.
    """
    paths: BucketPaths = bucket_paths(root, bucket_id)
    target = configured_keystore if configured_keystore is not None else keystore_path(root, bucket_id)

    # The already-resolved bucket dir's parent IS the buckets container -- no
    # second read of the governed name is needed.
    buckets_parent = paths.bucket_dir.parent
    if _is_under(target, paths.db_dir):
        raise BucketValidationError(
            "keystore path resolves under bucket db dir",
            context={
                "reason": "under_bucket_db_dir",
                "surface": _KEYSTORE_VALIDATION_SURFACE,
            },
        )
    if _is_under(target, buckets_parent):
        raise BucketValidationError(
            "keystore path resolves under buckets parent",
            context={
                "reason": "under_buckets_parent",
                "surface": _KEYSTORE_VALIDATION_SURFACE,
            },
        )


def keystore_sidecar_path(*, storage_root: Path, bucket_id: str, filename: str) -> Path:
    """Return ``<root>/keystore/<bucket_id>/<filename>``, refusing an unseparated keystore.

    Validates the keystore-separation invariant via
    :func:`validate_keystore_separation` before joining ``filename`` onto the
    bucket's keystore directory, so a violation raises before any sidecar
    path is returned to the caller. Canonical join point for every
    keystore-resident sidecar (the persisted session record, the wrapped
    bucket DEK, the login-throttle cache).

    Args:
        storage_root: The Cadrumo storage root.
        bucket_id: Bucket identifier whose keystore directory to resolve.
        filename: The sidecar filename to join onto the keystore directory.

    Returns:
        The keystore-separated sidecar path.

    Both inputs are checked, which they were not before: separation is a
    statement about ``bucket_id``, and ``filename`` was joined unexamined. This
    is the join point for the persisted session record, the wrapped bucket DEK
    and the login-throttle cache, so an unchecked filename places key material
    wherever it says -- measured, ``"../../secrets.json"`` reached the storage
    root and ``"C:/evil.json"`` reached the drive root. Every caller passes a
    module constant today; the check is here so that stays a property of the
    join rather than of the callers.

    Raises:
        BucketValidationError: When the keystore path violates separation, or
            when ``bucket_id`` or ``filename`` is not a single containable path
            component.
    """
    validate_keystore_separation(storage_root, bucket_id)
    validate_path_component(filename, subject="filename")
    return keystore_path(storage_root, bucket_id) / filename


__all__ = ["keystore_path", "keystore_root", "keystore_sidecar_path", "validate_keystore_separation"]
