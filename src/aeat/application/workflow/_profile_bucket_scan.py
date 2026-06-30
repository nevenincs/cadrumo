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

See Also:
    :class:`~aeat.application.workflow.ProfileBucketPointer`
        Public pointer record returned by the manifest scanners.
    :mod:`aeat.application.workflow._profile_health`
        Consumes by-id manifest lookup to classify active-profile readiness.
    :class:`~aeat.adapters.persistence.storage.bucket.BucketManifest`
        Plaintext manifest shape parsed from each profile bucket directory.
    :class:`~aeat.adapters.persistence.storage.bucket.BucketLifecycleStatus`
        Lifecycle marker used to hide tombstoned profiles from live surfaces.
    :mod:`aeat.application.user_profile._orchestration`
        Owns profile creation, selection, and encrypted profile-record access
        around the same bucket identity.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from ...adapters.persistence.storage import BUCKETS_DIRNAME
from ...adapters.persistence.storage.bucket import (
    BucketLifecycleStatus,
    BucketManifest,
    BucketPaths,
    bucket_paths,
    manifest_path,
    read_manifest,
)
from ...adapters.persistence.storage.errors import StorageValidationError
from ...core.logging import get_logger
from ._errors import ProfileLabelAmbiguousError
from ._models import ProfileBucketPointer

_log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ProfileBucketScanIssue:
    """One bucket manifest skipped by the live profile scanner."""

    bucket_id: str
    reason: str


def read_profile_bucket(
    label: str,
    *,
    root: Path | None = None,
    include_tombstoned: bool = False,
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

    Returns:
        A :class:`ProfileBucketPointer` for the matching profile, or
        ``None`` when no profile carries the label.

    Raises:
        ProfileLabelAmbiguousError: when two or more matching profiles
            share the label (an ambiguous resolution the name-uniqueness
            guard should have prevented among live profiles).
    """
    if not label or not label.strip():
        return None
    needle = label.strip().casefold()
    matches = [
        pointer
        for pointer in list_profile_buckets(root=root, include_tombstoned=include_tombstoned).values()
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
        raise ProfileLabelAmbiguousError(
            translated_message="application.workflow.errors.profile_label_ambiguous",
            context={"label": label, "count": str(len(matches))},
        )
    return matches[0]


def read_profile_bucket_by_id(profile_id: str, *, root: Path | None = None) -> ProfileBucketPointer | None:
    """Return the :class:`ProfileBucketPointer` for the profile whose UUID is ``profile_id``.

    Resolves ``<root>/buckets/<profile_id>/manifest.toml`` directly.
    Returns ``None`` when the manifest is absent. Resolves a profile
    regardless of lifecycle status - a tombstoned profile is still
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
    return ProfileBucketPointer(bucket_id=manifest.bucket_id, label=manifest.label, status=manifest.status)


def resolve_profile_bucket(
    identifier: str,
    *,
    root: Path | None = None,
    include_tombstoned: bool = False,
) -> ProfileBucketPointer | None:
    """Resolve a profile identifier that may be a UUID bucket id OR a display label.

    The active-profile precedence chain (``AEAT_ACTIVE_PROFILE`` env var, the
    ``active-profile`` pointer file) and operator input both carry whichever
    identifier the operator knows. An operator addresses a profile by the
    label they chose at ``profile create`` — they never see the immutable
    UUIDv4 bucket id — so ``AEAT_ACTIVE_PROFILE=<label>`` is a natural,
    intended operator action. Resolving the value as a UUID bucket directory
    only would hard-miss on a label (``buckets/<label>`` does not exist),
    refusing every profile-scoped command with a "no manifest" error.

    This resolver tries the UUID-direct lookup first (the canonical bucket
    directory key), then falls back to the manifest-scan-by-label. The same
    lifecycle filter applies to both paths: by default tombstoned profiles are
    hidden from live surfaces whether the operator supplies a UUID or a label.
    A label is unique among live profiles (the name-uniqueness guard), so the
    fallback is unambiguous. Returns ``None`` when the identifier matches
    neither a live bucket UUID nor a live profile label.

    Args:
        identifier: A profile UUID bucket id or an operator display label.
        root: Optional AEAT root override. When ``None``, resolves
            ``Settings.aeat_local_storage_root`` via ``load_settings``.
        include_tombstoned: When ``True``, inspect surfaces can resolve a
            deleted profile by UUID or name; default ``False`` matches only
            live profiles.

    Returns:
        A :class:`ProfileBucketPointer` for the resolved profile, or ``None``.
    """
    if not identifier or not identifier.strip():
        return None
    by_id = read_profile_bucket_by_id(identifier, root=root)
    if by_id is not None:
        if not include_tombstoned and by_id.status is BucketLifecycleStatus.TOMBSTONED:
            return None
        return by_id
    return read_profile_bucket(identifier, root=root, include_tombstoned=include_tombstoned)


def list_profile_buckets(
    *,
    root: Path | None = None,
    include_tombstoned: bool = False,
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

    Returns:
        A dict mapping each profile UUID to its :class:`ProfileBucketPointer`.
    """
    resolved_root = _resolve_root(root)
    buckets_root = resolved_root / BUCKETS_DIRNAME
    if not buckets_root.is_dir():
        return {}
    result: dict[str, ProfileBucketPointer] = {}
    for entry in sorted(buckets_root.iterdir()):
        if not entry.is_dir():
            continue
        try:
            paths = bucket_paths(resolved_root, entry.name)
        except ValueError as exc:
            _log.debug(
                "profile bucket scan: skipping invalid bucket directory name bucket_id=%s",
                entry.name,
                exc_info=exc,
            )
            continue
        if not manifest_path(paths).is_file():
            continue
        manifest = _read_manifest_or_none(paths)
        if manifest is None:
            continue
        if not include_tombstoned and manifest.status is BucketLifecycleStatus.TOMBSTONED:
            continue
        result[manifest.bucket_id] = ProfileBucketPointer(
            bucket_id=manifest.bucket_id,
            label=manifest.label,
            status=manifest.status,
        )
    return result


def list_profile_bucket_scan_issues(*, root: Path | None = None) -> tuple[ProfileBucketScanIssue, ...]:
    """Return non-sensitive manifest-scan issues found under the profile root.

    Each element is a :class:`ProfileBucketScanIssue` describing one
    structural problem found in the profile bucket directories.
    """
    resolved_root = _resolve_root(root)
    buckets_root = resolved_root / BUCKETS_DIRNAME
    if not buckets_root.is_dir():
        return ()
    issues: list[ProfileBucketScanIssue] = []
    for entry in sorted(buckets_root.iterdir()):
        if not entry.is_dir():
            continue
        try:
            paths = bucket_paths(resolved_root, entry.name)
        except ValueError as exc:
            issues.append(ProfileBucketScanIssue(bucket_id=entry.name, reason=_compact_manifest_error(exc)))
            continue
        if not manifest_path(paths).is_file():
            continue
        issue = _profile_bucket_scan_issue(entry.name, paths)
        if issue is not None:
            issues.append(issue)
    return tuple(issues)


def _read_manifest_or_none(paths: BucketPaths) -> BucketManifest | None:
    try:
        return read_manifest(paths)
    except _MANIFEST_SCAN_EXCEPTIONS as exc:
        _log.debug(
            "profile bucket scan: skipping unreadable bucket manifest bucket_id=%s",
            paths.bucket_id,
            exc_info=exc,
        )
        return None


def _profile_bucket_scan_issue(bucket_id: str, paths: BucketPaths) -> ProfileBucketScanIssue | None:
    try:
        read_manifest(paths)
    except _MANIFEST_SCAN_EXCEPTIONS as exc:
        return ProfileBucketScanIssue(bucket_id=bucket_id, reason=_compact_manifest_error(exc))
    return None


_MANIFEST_SCAN_EXCEPTIONS = (
    OSError,
    StorageValidationError,
    ValidationError,
    tomllib.TOMLDecodeError,
    TypeError,
    ValueError,
)


def _compact_manifest_error(exc: BaseException) -> str:
    # Unwrap the storage-validation wrapper to the underlying cause so
    # the operator-facing scan issue names the actual fault class
    # (e.g. TOMLDecodeError) rather than the storage-layer envelope.
    root = exc.__cause__ if isinstance(exc, StorageValidationError) and exc.__cause__ is not None else exc
    message = str(root).splitlines()[0] if str(root) else type(root).__name__
    return f"{type(root).__name__}: {message}"


def _resolve_root(root: Path | None) -> Path:
    if root is not None:
        return root
    from ...core.config import load_settings

    return load_settings().aeat_local_storage_root


__all__ = [
    "ProfileBucketScanIssue",
    "list_profile_bucket_scan_issues",
    "list_profile_buckets",
    "read_profile_bucket",
    "read_profile_bucket_by_id",
    "resolve_profile_bucket",
]
