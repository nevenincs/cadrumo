"""Create and select a real committed profile capsule under a storage root."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from cadrumo.adapters.persistence.storage.custody.sentinel import create_profile_custody_sentinel
from cadrumo.application.user_profile.capsule_record import ProfileRecordSession
from cadrumo.application.user_profile.lifecycle import ProfileCapsuleLifecycle
from cadrumo.domain.user_profile.values import ProfileSetupState, create_user_profile_record

from .profile_capsule_runtime import profile_authority_contexts
from .registered_bucket import registration_envelope

_DEK = bytes(range(32))


def create_committed_profile(root: Path, *, bucket_id: str, label: str) -> None:
    """Create and select the real committed capsule that owns the label projection."""
    _profile_create_context_for_test, _profile_decode_context_for_test = profile_authority_contexts()
    profile_id = UUID(bucket_id)
    envelope = registration_envelope(profile_id)
    session = ProfileRecordSession.from_envelope(
        envelope=envelope, dek=_DEK, profile_decode_context=_profile_decode_context_for_test
    )
    lifecycle = ProfileCapsuleLifecycle(root=root)
    try:
        lifecycle.create(
            label=label,
            profile_id=profile_id,
            password_envelope=envelope,
            sentinel=create_profile_custody_sentinel(envelope=envelope, dek=_DEK),
            data_files={},
            initial_record=create_user_profile_record(
                profile_id=bucket_id, setup_state=ProfileSetupState.INCOMPLETE, context=_profile_create_context_for_test
            ),
            record_session=session,
        )
        lifecycle.select(label)
    finally:
        session.close()
