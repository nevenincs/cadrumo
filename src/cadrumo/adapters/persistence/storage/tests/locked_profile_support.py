"""Shared capsule publisher for the locked-profile health proofs.

The locked state exists only where no process has authenticated, so the
capsule under test must be published by an interpreter that has since exited:
a publisher running inside the reading process leaves a live record authority
latched and the reader then sees an unlocked profile, which is the one
configuration in which the defect cannot appear.

This lives in a support module rather than inside a test module because the
CHILD interpreter imports it by name through ``python -c``; nothing here may
depend on a pytest fixture or on an already-running test session.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    identity_seeded_custody_envelope,
)
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    profile_authority_contexts as _profile_contexts_for_test,
)
from cadrumo.application.user_profile.tests.persona_profile_facts import persona_profile_facts
from cadrumo.domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test

from .....core.bucket_pointer import BucketPointer, write_pointer
from .....domain.user_profile.values import ProfileSetupState, UserProfileFact
from ..custody.records import (
    ProfileCustodyEnvelope,
)
from ..custody.sentinel import create_profile_custody_sentinel

PROFILE_ID = "31313131-3131-4313-8313-313131313131"
PROFILE_LABEL = "Operator"
DEK = bytes(range(32))
RECORD_NAMESPACE = "cadrumo.application.user_profile.value"

_READY_PERSONA_ID = "autonomo-fontanero"


def ready_facts() -> tuple[UserProfileFact, ...]:
    """The facts of a complete profile: the autonomo-fontanero persona's."""
    return persona_profile_facts(_READY_PERSONA_ID)


def build_envelope() -> ProfileCustodyEnvelope:
    """Return the deterministic password envelope both processes agree on."""
    return identity_seeded_custody_envelope(UUID(PROFILE_ID))


def publish_capsule_and_pointer(root: Path) -> None:
    """Publish one complete capsule at *root* and point the active selector at it."""
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    from .....application.user_profile.capsule_record import ProfileRecordSession
    from .....application.user_profile.lifecycle import ProfileCapsuleLifecycle

    envelope = build_envelope()
    session = ProfileRecordSession.from_envelope(
        envelope=envelope, dek=DEK, profile_decode_context=_profile_decode_context_for_test
    )
    try:
        ProfileCapsuleLifecycle(root=root).create(
            label=PROFILE_LABEL,
            profile_id=UUID(PROFILE_ID),
            password_envelope=envelope,
            sentinel=create_profile_custody_sentinel(envelope=envelope, dek=DEK),
            data_files={},
            initial_record=_create_profile_record_for_test(
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=PROFILE_ID,
                facts=ready_facts(),
                context=_profile_create_context_for_test,
            ),
            record_session=session,
        )
    finally:
        session.close()
    write_pointer(root, BucketPointer.selected(bucket_id=PROFILE_ID, transition_revision=1))


__all__ = [
    "DEK",
    "PROFILE_ID",
    "PROFILE_LABEL",
    "RECORD_NAMESPACE",
    "build_envelope",
    "publish_capsule_and_pointer",
    "ready_facts",
]
