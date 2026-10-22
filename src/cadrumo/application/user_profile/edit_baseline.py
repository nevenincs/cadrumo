"""Value-free diagnostics for revision-bound profile edits."""

from __future__ import annotations

from ...domain.user_profile.values import UserProfileRecord
from .capsule_record import ProfileRecordConflictError


def require_profile_edit_baseline(
    current: UserProfileRecord,
    *,
    expected_revision: int,
    expected_content_digest: str,
    field_paths: tuple[str, ...],
) -> None:
    """Refuse a stale edit and report addresses, never values or content hashes.

    Callers supply schema-owned addresses rather than unchecked input strings.

    Args:
        current: The profile's current :class:`UserProfileRecord`.
        expected_revision: The record revision the edit was prepared against.
        expected_content_digest: The content digest the edit was prepared against.
        field_paths: Schema-owned addresses of the fields the edit touches.
    """
    revision_matches = current.record_revision == expected_revision
    digest_matches = current.content_digest == expected_content_digest
    if revision_matches and digest_matches:
        return
    raise ProfileRecordConflictError(
        "profile edit baseline is stale",
        context={
            "field_paths": field_paths,
            "expected_revision": expected_revision,
            "current_revision": current.record_revision,
            "digest_matches": digest_matches,
        },
    )
