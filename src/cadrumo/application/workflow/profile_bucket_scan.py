"""Committed-capsule profile discovery for workflow projections.

Workflow sees only the non-authoritative UUID and label projection emitted by
the custody capsule owner.  It does not inspect manifests, buckets, deleted
directories, or record facts.
"""

from __future__ import annotations

from pathlib import Path

from ..user_profile.profile_repository import CommittedProfileRepository, ProfileNotFoundError
from .errors import ProfileLabelAmbiguousError
from .profile_bucket_models import ProfileBucketPointer


def _repository(root: Path | None) -> CommittedProfileRepository:
    return CommittedProfileRepository(root=root)


def _pointer(profile_id: str, label: str) -> ProfileBucketPointer:
    return ProfileBucketPointer(bucket_id=profile_id, label=label)


def read_profile_bucket(
    label: str,
    *,
    root: Path | None = None,
) -> ProfileBucketPointer | None:
    """Resolve one exact label from committed-capsule label projections."""
    if not label or not label.strip():
        return None
    matches = [item for item in _repository(root).list() if item.label.casefold() == label.strip().casefold()]
    if not matches:
        return None
    if len(matches) != 1:
        raise ProfileLabelAmbiguousError(
            translated_message="application.workflow.errors.profile_label_ambiguous",
            context={"label": label, "count": str(len(matches))},
        )
    match = matches[0]
    return _pointer(match.profile_id, match.label)


def read_profile_bucket_by_id(profile_id: str, *, root: Path | None = None) -> ProfileBucketPointer | None:
    """Resolve one UUID only when its current capsule is committed."""
    if not profile_id or not profile_id.strip():
        return None
    try:
        profile = _repository(root).load(profile_id)
    except ProfileNotFoundError:
        return None
    return _pointer(profile.profile_id, profile.label)


def resolve_profile_bucket(
    identifier: str,
    *,
    root: Path | None = None,
) -> ProfileBucketPointer | None:
    """Resolve a UUID or exact label through the current capsule projection."""
    if not identifier or not identifier.strip():
        return None
    return read_profile_bucket_by_id(identifier, root=root) or read_profile_bucket(identifier, root=root)


def list_profile_buckets(
    *,
    root: Path | None = None,
) -> dict[str, ProfileBucketPointer]:
    """Return every committed capsule's non-authoritative label projection."""
    return {item.profile_id: _pointer(item.profile_id, item.label) for item in _repository(root).list()}


__all__ = [
    "list_profile_buckets",
    "read_profile_bucket",
    "read_profile_bucket_by_id",
    "resolve_profile_bucket",
]
