"""Manifest-scan discovery for profile bucket pointers.

A profile bucket lives at ``<aeat-root>/buckets/<profile-id>/`` where
``<profile-id>`` is the immutable UUIDv4 profile identity. The
plaintext ``manifest.toml`` inside carries that ``bucket_id`` (the
UUID) and a decoupled mutable ``label`` (the operator-chosen display
name). The bucket directory name and the profile identity are one and
the same; the operator never sees the UUID and addresses profiles by
their label.

This module exposes the scanner that enumerates profile buckets by
reading those plaintext manifests. It never opens the encrypted
database engine. ``read_profile_bucket`` resolves an operator label to
a bucket pointer (UUID + label); ``list_profile_buckets`` returns every
registered pointer keyed by UUID.

The manifest carries a plaintext ``status`` lifecycle marker. The
live-surface resolvers — ``read_profile_bucket`` and, by default,
``list_profile_buckets`` — exclude tombstoned profiles so a deleted
profile never leaks into ``list`` / ``switch`` / name-uniqueness. The
by-id resolver ``read_profile_bucket_by_id`` resolves a profile
regardless of status: surfaces that legitimately inspect a tombstoned
profile (``show``, diagnostics) address it by UUID.
"""

from __future__ import annotations

from pathlib import Path

from ...adapters.persistence.storage.bucket._layout import bucket_paths
from ...adapters.persistence.storage.bucket._manifest import BucketLifecycleStatus, BucketManifest
from ...adapters.persistence.storage.bucket._manifest_io import manifest_path, read_manifest
from ._models import ProfileBucketPointer

_BUCKETS_DIRNAME = "buckets"


def read_profile_bucket(
    label: str, *, root: Path | None = None, include_tombstoned: bool = False
) -> ProfileBucketPointer | None:
    """Return the bucket pointer for the profile whose label is ``label``.

    Scans every ``<root>/buckets/*/manifest.toml`` and matches the
    manifest ``label`` against ``label`` case-insensitively. Returns a
    :class:`ProfileBucketPointer` carrying the UUID ``bucket_id``, the
    manifest ``label``, and the lifecycle ``status`` when exactly one
    profile matches; returns ``None`` when no profile carries the label.

    By default tombstoned profiles are excluded: a deleted profile is
    off the live surface, so its label resolves to ``None`` (re-usable)
    and it can never be switched into. The ``show`` inspect surface
    passes ``include_tombstoned=True`` so an operator can still inspect
    a deleted profile by name and see its tombstoned status; it then
    branches on the returned ``status``.

    Args:
        label: Operator-facing profile label. Must be non-empty.
        root: Optional AEAT root override. When ``None``, resolves
            ``Settings.aeat_local_storage_root`` via ``load_settings``.
        include_tombstoned: When ``True``, a tombstoned profile is also
            a candidate; default ``False`` matches only live profiles.

    Raises:
        ValueError: when two matching profiles share the label (an
            ambiguous resolution the name-uniqueness guard should have
            prevented among live profiles).
    """

    if not label or not label.strip():
        return None
    needle = label.strip().casefold()
    matches = [
        pointer
        for pointer in list_profile_buckets(
            root=root, include_tombstoned=include_tombstoned
        ).values()
        if pointer.label.casefold() == needle
    ]
    if not matches:
        return None
    if len(matches) > 1:
        # With tombstoned profiles included, a freed name may be carried
        # by both a tombstoned profile and a live one. The live profile
        # is the unambiguous resolution; a single live match wins.
        live = [p for p in matches if p.status is BucketLifecycleStatus.ACTIVE]
        if len(live) == 1:
            return live[0]
        raise ValueError(
            f"profile label {label!r} is ambiguous: {len(matches)} buckets carry it"
        )
    return matches[0]


def read_profile_bucket_by_id(profile_id: str, *, root: Path | None = None) -> ProfileBucketPointer | None:
    """Return the bucket pointer for the profile whose UUID is ``profile_id``.

    Resolves ``<root>/buckets/<profile_id>/manifest.toml`` directly.
    Returns ``None`` when the manifest is absent. Resolves a profile
    regardless of lifecycle status — a tombstoned profile is still
    addressable by its UUID so ``show`` and diagnostics can inspect it;
    the returned pointer carries the manifest ``status`` so the caller
    can branch on it.
    """

    if not profile_id or not profile_id.strip():
        return None
    resolved_root = _resolve_root(root)
    try:
        paths = bucket_paths(resolved_root, profile_id.strip())
    except ValueError:
        return None
    target = manifest_path(paths)
    if not target.is_file():
        return None
    manifest = read_manifest(paths)
    return ProfileBucketPointer(
        bucket_id=manifest.bucket_id, label=manifest.label, status=manifest.status
    )


def list_profile_buckets(
    *, root: Path | None = None, include_tombstoned: bool = False
) -> dict[str, ProfileBucketPointer]:
    """Return registered profile-bucket pointers keyed by profile UUID.

    Scans ``<root>/buckets/*/manifest.toml`` for every directory that
    carries a manifest file, parses each manifest, and returns a
    pointer carrying the manifest ``bucket_id`` (UUID), ``label``
    (operator name), and ``status`` lifecycle marker. Directories
    without a manifest are treated as torn or pre-provisioned state and
    skipped.

    By default only live (non-tombstoned) profiles are returned: a
    tombstoned profile has left the live operator surface. Pass
    ``include_tombstoned=True`` to enumerate every registered profile —
    used by repair / audit surfaces that must see deleted profiles.

    Args:
        root: Optional AEAT root override. When ``None``, resolves
            ``Settings.aeat_local_storage_root`` via ``load_settings``.
        include_tombstoned: When ``True``, tombstoned profiles are
            included; default ``False`` returns only live profiles.
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
        manifest: BucketManifest = read_manifest(paths)
        if not include_tombstoned and manifest.status is BucketLifecycleStatus.TOMBSTONED:
            continue
        result[manifest.bucket_id] = ProfileBucketPointer(
            bucket_id=manifest.bucket_id,
            label=manifest.label,
            status=manifest.status,
        )
    return result


def _resolve_root(root: Path | None) -> Path:
    if root is not None:
        return root
    from ...core.config import load_settings

    return load_settings().aeat_local_storage_root


__all__ = ["list_profile_buckets", "read_profile_bucket", "read_profile_bucket_by_id"]
