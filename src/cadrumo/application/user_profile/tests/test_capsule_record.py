"""Real-crypto contracts for the capsule-resident profile record."""

from __future__ import annotations

from base64 import b64encode
from uuid import UUID

import pytest

from ....adapters.persistence.storage.custody import (
    ProfileCustodyEnvelope,
    ProfileCustodyKdfParameters,
    ProfileCustodyWrappedDek,
)
from ....domain.user_profile import ProfileSetupState, UserProfileRecord
from .._capsule_record import ProfileRecordConflictError, ProfileRecordSession

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = UUID("cc0aeac5-30af-460d-b2cc-dcbbf30c578a")
_DEK = bytes(range(32))


def _envelope() -> ProfileCustodyEnvelope:
    return ProfileCustodyEnvelope.create(
        profile_id=_PROFILE_ID,
        password_generation=7,
        dek_epoch=b64encode(b"e" * 16).decode("ascii"),
        kdf=ProfileCustodyKdfParameters(
            algorithm="argon2id",
            version=19,
            memory_mib=19,
            iterations=2,
            parallelism=1,
            salt_b64=b64encode(b"k" * 16).decode("ascii"),
            output_bytes=32,
        ),
        wrapped_dek=ProfileCustodyWrappedDek(
            nonce_b64=b64encode(b"n" * 12).decode("ascii"),
            ciphertext_b64=b64encode(b"c" * 32).decode("ascii"),
            tag_b64=b64encode(b"t" * 16).decode("ascii"),
        ),
    )


def test_initial_record_is_encrypted_and_bound_to_the_exact_envelope_session() -> None:
    session = ProfileRecordSession.from_envelope(envelope=_envelope(), dek=_DEK)
    record = UserProfileRecord(profile_id=str(_PROFILE_ID))

    payload = session.create_initial(record)
    restored, artifact = session.decode_current(payload, expected_revision=1)

    assert restored == record
    assert artifact.previous_record_digest is None
    assert "Initial operator" not in payload.decode("utf-8")


def test_record_compare_and_swap_carries_the_previous_current_digest() -> None:
    session = ProfileRecordSession.from_envelope(envelope=_envelope(), dek=_DEK)
    initial = UserProfileRecord(profile_id=str(_PROFILE_ID), setup_state=ProfileSetupState.INCOMPLETE)
    current, current_artifact = session.decode_current(session.create_initial(initial))
    replacement = UserProfileRecord.model_validate(
        current.model_dump(exclude={"content_digest"})
        | {"setup_state": ProfileSetupState.COMPLETE, "record_revision": 2, "previous_record_digest": current.content_digest}
    )

    next_payload = session.prepare_replace(
        current_artifact,
        replacement,
        expected_revision=current_artifact.revision,
        expected_content_digest=current_artifact.content_digest,
    )
    restored, next_artifact = session.decode_current(next_payload, expected_revision=2)

    assert restored == replacement
    assert next_artifact.previous_record_digest == current_artifact.content_digest
    with pytest.raises(ProfileRecordConflictError):
        session.prepare_replace(
            current_artifact,
            replacement,
            expected_revision=2,
            expected_content_digest=current_artifact.content_digest,
        )


def test_record_refuses_a_session_for_a_different_current_envelope() -> None:
    initial_session = ProfileRecordSession.from_envelope(envelope=_envelope(), dek=_DEK)
    payload = initial_session.create_initial(UserProfileRecord(profile_id=str(_PROFILE_ID)))
    changed_envelope = _envelope().model_copy(update={"password_generation": 8})
    changed_session = ProfileRecordSession.from_envelope(envelope=changed_envelope, dek=_DEK)

    with pytest.raises(ProfileRecordConflictError):
        changed_session.decode_current(payload)
