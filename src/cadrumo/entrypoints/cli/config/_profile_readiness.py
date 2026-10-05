"""Profile readiness helpers for the config CLI surface."""

from __future__ import annotations


def _read_profile_record(*, profile_id: str, bucket_id: str):
    """Read through the exact live session established by the parsed root gate."""
    from ....adapters.persistence.storage.master_key.active_session import active_bucket_session_serves
    from ....application.user_profile.profile_record_repository import ProfileRecordRepository
    from ....domain.calculations.registry.authority import bundled_indexed_authority
    from ....domain.user_profile.errors import ProfileNotFoundError

    if active_bucket_session_serves(bucket_id):
        with bundled_indexed_authority().operation() as operation:
            return ProfileRecordRepository.for_current_session(
                bucket_id,
                profile_decode_context=operation.profile_decode_context(),
            ).load(profile_id)
    raise ProfileNotFoundError("profile record requires its active authenticated custody session")


__all__ = [
    "_read_profile_record",
]
