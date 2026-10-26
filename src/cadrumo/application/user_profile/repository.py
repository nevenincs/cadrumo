"""Secure-object key construction for immutable filing-time profile snapshots."""

from __future__ import annotations

from ...domain.user_profile.errors import UserProfileValidationError


def user_profile_snapshot_object_key(profile_id: str, snapshot_id: str) -> str:
    """Return the secure-object key for one of a profile's filing snapshots."""
    trimmed_profile = profile_id.strip()
    trimmed_snapshot = snapshot_id.strip()
    if not trimmed_profile:
        raise UserProfileValidationError(context={"field": "profile_id", "blank": True})
    if not trimmed_snapshot:
        raise UserProfileValidationError(context={"field": "snapshot_id", "blank": True})
    return f"user-profile-snapshot:{trimmed_profile}:{trimmed_snapshot}"


__all__ = ["user_profile_snapshot_object_key"]
