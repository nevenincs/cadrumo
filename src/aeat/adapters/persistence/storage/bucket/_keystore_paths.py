"""Keystore separation contract enforcing the isolation invariant.

The KEK / DEK / passphrase / OS-keystore custody artefacts live under a
keystore root that is structurally outside the buckets parent. The two
invariants enforced here are:

- The keystore root is sibling to ``buckets/`` under the AEAT root
  (``<aeat-root>/keystore/<bucket-id>/``), never nested inside any bucket
  directory and never co-located under the relational database directory.
- A configuration that resolves the keystore path under either parent is
  rejected by :func:`validate_keystore_separation` so a subsequent unlock
  cannot silently violate the invariant.

The pure helpers do not materialise the directory; the cryptographic core
(P03) owns provisioning when an enrolment first lands.
"""

from __future__ import annotations

from pathlib import Path

from .._namespace_registry import BUCKETS_DIRNAME, KEYSTORE_DIRNAME
from ._errors import BucketValidationError
from ._layout import BucketPaths, bucket_paths

_KEYSTORE_VALIDATION_SURFACE = "bucket_keystore"


def keystore_root(root: Path) -> Path:
    """Return the keystore parent ``<root>/keystore/`` (no IO)."""
    return root / KEYSTORE_DIRNAME


def keystore_path(root: Path, bucket_id: str) -> Path:
    """Return ``<root>/keystore/<bucket_id>/`` (no IO).

    Args:
        root: The AEAT root directory.
        bucket_id: Bucket identifier to include in the path.

    Returns:
        The computed keystore directory path.

    Raises:
        BucketValidationError: When ``bucket_id`` is empty or carries a path separator.
    """
    if not bucket_id:
        raise BucketValidationError("bucket_id must be non-empty")
    if "/" in bucket_id or "\\" in bucket_id:
        raise BucketValidationError("bucket_id must not contain a path separator")
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
        root: The AEAT root directory.
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

    buckets_parent = root / BUCKETS_DIRNAME
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


__all__ = ["keystore_path", "keystore_root", "validate_keystore_separation"]
