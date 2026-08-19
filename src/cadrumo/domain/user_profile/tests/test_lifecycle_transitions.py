"""Current profile-record setup-state contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .. import ProfileSetupState, UserProfileRecord, UserProfileSnapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PROFILE_ID = "11111111-1111-4111-8111-111111111111"


def _incomplete_record() -> UserProfileRecord:
    return UserProfileRecord(
        profile_id=_PROFILE_ID,
        setup_state=ProfileSetupState.INCOMPLETE,
    )


def test_incomplete_record_is_explicitly_not_ready() -> None:
    record = _incomplete_record()
    assert record.setup_state is ProfileSetupState.INCOMPLETE


def test_a_record_must_declare_its_setup_state() -> None:
    """Readiness is stated, never defaulted.

    A default would let a record that never declared its readiness satisfy a
    completeness gate on the model's opinion rather than the writer's, which
    is the silent direction: an incomplete profile reading as complete.
    """
    with pytest.raises(ValidationError, match="setup_state"):
        UserProfileRecord(profile_id=_PROFILE_ID)  # ty: ignore[missing-argument]  # reason: the omission IS the refusal under test


def test_a_complete_record_states_it() -> None:
    record = UserProfileRecord(profile_id=_PROFILE_ID, setup_state=ProfileSetupState.COMPLETE)
    assert record.setup_state is ProfileSetupState.COMPLETE


def test_legacy_lifecycle_fields_are_rejected() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        UserProfileRecord.model_validate(
            {
                "profile_id": _PROFILE_ID,
                "status": "active",
            },
        )


def test_incomplete_record_cannot_be_snapshotted() -> None:
    with pytest.raises(ValueError, match="cannot snapshot an incomplete profile record"):
        UserProfileSnapshot.from_profile(_incomplete_record())
