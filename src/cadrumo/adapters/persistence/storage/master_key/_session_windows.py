"""Per-bucket session-window overrides read from the bucket manifest.

Both helpers resolve one session-lifetime axis for a bucket, falling back to
the deployment default when the manifest states nothing. A bucket whose
manifest is absent is not an error here: it simply has no override, so the
caller's configured default stands.

These read the manifest and nothing else. They lived beside the retired
master-key keystore route for historical reasons rather than by ownership, and
survived its deletion because they are live on the session path: a caller that
lost them would silently collapse every profile's idle and absolute session
windows to the deployment defaults, which is a behaviour change wearing the
costume of a cleanup.

See Also:
    :class:`~cadrumo.adapters.persistence.storage.master_key.BucketSession`
        The session these windows bound.
"""

from __future__ import annotations

from pathlib import Path


def idle_minutes_for_bucket(*, storage_root: Path, bucket_id: str, default_minutes: int) -> int:
    """Resolve the idle window from the bucket manifest, falling back to settings."""
    from ..bucket import MISSING_BUCKET_MANIFEST_MESSAGE, bucket_paths, read_manifest
    from ..errors import StorageValidationError

    try:
        manifest = read_manifest(bucket_paths(storage_root, bucket_id))
    except StorageValidationError as exc:
        if str(exc) == MISSING_BUCKET_MANIFEST_MESSAGE:
            return default_minutes
        raise
    configured = manifest.idle_lock_minutes
    return configured if configured is not None else default_minutes


def session_absolute_minutes_for_bucket(*, storage_root: Path, bucket_id: str, default_minutes: int) -> int:
    """Resolve the absolute session cap from the bucket manifest, falling back to settings."""
    from ..bucket import MISSING_BUCKET_MANIFEST_MESSAGE, bucket_paths, read_manifest
    from ..errors import StorageValidationError

    try:
        manifest = read_manifest(bucket_paths(storage_root, bucket_id))
    except StorageValidationError as exc:
        if str(exc) == MISSING_BUCKET_MANIFEST_MESSAGE:
            return default_minutes
        raise
    configured = manifest.session_absolute_minutes
    return configured if configured is not None else default_minutes


__all__ = ["idle_minutes_for_bucket", "session_absolute_minutes_for_bucket"]
