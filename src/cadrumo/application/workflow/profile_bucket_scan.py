"""Committed-capsule profile discovery for workflow projections.

Workflow sees only the non-authoritative UUID and label projection emitted by
the custody capsule owner.  It does not inspect manifests, buckets, deleted
directories, or record facts.

That projection is exactly what the profile summary inventory observes, so this
module reads it rather than building a second one.  It previously went through
the authenticated aggregate, which took a per-profile custody lock and could
publish a label head as a side effect of *resolving a name* -- work no consumer
here needs, and a second definition of "which profiles exist" that could
disagree with the first.
"""

from __future__ import annotations

from pathlib import Path

from ..user_profile.profile_summary import ProfileSummary, summary_inventory
from .errors import ProfileLabelAmbiguousError
from .profile_bucket_models import ProfileBucketPointer


def _summaries(root: Path | None) -> tuple[ProfileSummary, ...]:
    return summary_inventory(root=root).summaries


def _pointer(summary: ProfileSummary) -> ProfileBucketPointer:
    return ProfileBucketPointer(bucket_id=summary.profile_id, label=summary.label)


def read_profile_bucket(
    label: str,
    *,
    root: Path | None = None,
) -> ProfileBucketPointer | None:
    """Resolve one exact label from committed-capsule label projections."""
    if not label or not label.strip():
        return None
    matches = [item for item in _summaries(root) if item.label.casefold() == label.strip().casefold()]
    if not matches:
        return None
    if len(matches) != 1:
        raise ProfileLabelAmbiguousError(
            translated_message="application.workflow.errors.profile_label_ambiguous",
            context={"label": label, "count": str(len(matches))},
        )
    return _pointer(matches[0])


def read_profile_bucket_by_id(profile_id: str, *, root: Path | None = None) -> ProfileBucketPointer | None:
    """Resolve one UUID only when its current capsule is committed."""
    if not profile_id or not profile_id.strip():
        return None
    identity = profile_id.strip()
    return next((_pointer(item) for item in _summaries(root) if item.profile_id == identity), None)


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
    return {item.profile_id: _pointer(item) for item in _summaries(root)}


__all__ = [
    "list_profile_buckets",
    "read_profile_bucket",
    "read_profile_bucket_by_id",
    "resolve_profile_bucket",
]
