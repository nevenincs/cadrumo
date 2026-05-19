"""Manifest-scan discovery for profile bucket pointers.

The 2026-05-14 ``profile-bucket-lifecycle`` ADR §1 mandates a 1:1
profile↔bucket cardinality, and §4 mandates that
``aeat config profile list`` enumerate buckets via filesystem scan of
``<aeat-root>/buckets/*/manifest.toml`` without unlocking any bucket.
This module exposes the scanner that replaces the retired
``WorkflowState.profiles`` mapping for every consumer that previously
looked up "does this profile name exist? and what is its bucket id?".

Under the 1:1 cardinality the bucket id equals the profile id, so the
returned :class:`ProfileBucketPointer` simply records the profile name
as the bucket id. The scanner reads plaintext manifest files only and
never opens the encrypted database engine.
"""

from __future__ import annotations

from pathlib import Path

from ...adapters.persistence.storage.bucket._layout import bucket_paths
from ...adapters.persistence.storage.bucket._manifest_io import manifest_path
from ._models import ProfileBucketPointer

_BUCKETS_DIRNAME = "buckets"


def read_profile_bucket(profile_name: str, *, root: Path | None = None) -> ProfileBucketPointer | None:
    """Return the bucket pointer for ``profile_name`` if its bucket exists.

    Resolves ``<root>/buckets/<profile_name>/manifest.toml``; when the
    manifest is present, returns a :class:`ProfileBucketPointer` whose
    ``bucket_id`` equals ``profile_name`` per the 1:1 cardinality. When
    the manifest is absent (no such profile / no such bucket) returns
    ``None``.

    Args:
        profile_name: Operator-facing profile name. Must be non-empty.
        root: Optional AEAT root override. When ``None``, resolves
            ``Settings.aeat_local_storage_root`` via ``load_settings``.
    """

    if not profile_name:
        return None
    resolved_root = _resolve_root(root)
    try:
        paths = bucket_paths(resolved_root, profile_name)
    except ValueError:
        return None
    target = manifest_path(paths)
    if not target.is_file():
        return None
    return ProfileBucketPointer(bucket_id=profile_name)


def list_profile_buckets(*, root: Path | None = None) -> dict[str, ProfileBucketPointer]:
    """Return every registered profile-bucket pointer keyed by profile name.

    Scans ``<root>/buckets/*/manifest.toml`` for every directory that
    carries a manifest file. Directories without a manifest are
    treated as torn or pre-provisioned state and skipped.

    Args:
        root: Optional AEAT root override. When ``None``, resolves
            ``Settings.aeat_local_storage_root`` via ``load_settings``.
    """

    resolved_root = _resolve_root(root)
    buckets_root = resolved_root / _BUCKETS_DIRNAME
    if not buckets_root.is_dir():
        return {}
    result: dict[str, ProfileBucketPointer] = {}
    for entry in sorted(buckets_root.iterdir()):
        if not entry.is_dir():
            continue
        try:
            paths = bucket_paths(resolved_root, entry.name)
        except ValueError:
            continue
        if not manifest_path(paths).is_file():
            continue
        result[entry.name] = ProfileBucketPointer(bucket_id=entry.name)
    return result


def _resolve_root(root: Path | None) -> Path:
    if root is not None:
        return root
    from ...core.config import load_settings

    return load_settings().aeat_local_storage_root


__all__ = ["list_profile_buckets", "read_profile_bucket"]
