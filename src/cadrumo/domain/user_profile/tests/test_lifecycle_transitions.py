"""Lifecycle-status transition contract for :class:`UserProfileRecord`.

Pins the ``SETUP_INCOMPLETE`` arm of :class:`UserProfileStatus`: a
mid-setup profile is a live record (no ``removed_at``), transitions to
``ACTIVE`` only through :meth:`UserProfileRecord.complete_setup`, and can
still be tombstoned when the operator discards the unfinished setup.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .. import UserProfileRecord, UserProfileStatus, UserProfileValidationError, utc_now

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PROFILE_ID = "11111111-1111-4111-8111-111111111111"


def _incomplete_record() -> UserProfileRecord:
    return UserProfileRecord(
        profile_id=_PROFILE_ID,
        display_name="Operator",
        status=UserProfileStatus.SETUP_INCOMPLETE,
    )


def test_setup_incomplete_record_is_live_without_removed_at() -> None:
    record = _incomplete_record()
    assert record.status is UserProfileStatus.SETUP_INCOMPLETE
    assert record.removed_at is None


def test_setup_incomplete_record_refuses_removed_at() -> None:
    with pytest.raises(ValidationError, match="must not carry removed_at"):
        UserProfileRecord(
            profile_id=_PROFILE_ID,
            display_name="Operator",
            status=UserProfileStatus.SETUP_INCOMPLETE,
            removed_at=utc_now(),
        )


def test_complete_setup_transitions_to_active() -> None:
    record = _incomplete_record()
    completed = record.complete_setup()
    assert completed.status is UserProfileStatus.ACTIVE
    assert completed.removed_at is None
    assert completed.updated_at >= record.updated_at


def test_complete_setup_refuses_an_active_profile() -> None:
    active = UserProfileRecord(profile_id=_PROFILE_ID, display_name="Operator")
    with pytest.raises(UserProfileValidationError):
        active.complete_setup()


def test_complete_setup_refuses_a_tombstoned_profile() -> None:
    tombstoned = UserProfileRecord(profile_id=_PROFILE_ID, display_name="Operator").tombstone()
    with pytest.raises(UserProfileValidationError):
        tombstoned.complete_setup()


def test_setup_incomplete_profile_can_be_tombstoned_on_discard() -> None:
    discarded = _incomplete_record().tombstone()
    assert discarded.status is UserProfileStatus.TOMBSTONED
    assert discarded.removed_at is not None
