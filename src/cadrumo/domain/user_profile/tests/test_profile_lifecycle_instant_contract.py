"""Direct domain tests: profile lifecycle and snapshot instants are UTC.

``UserProfileRecord``'s ``created_at`` / ``updated_at`` and
``UserProfileSnapshot.created_at`` are UTC instants, so direct construction
and encrypted hydration
could carry naive or local-time values into live profile state.

The ordering and tombstone validators on the record made that worse rather
than catching it: they compare these values, and comparing a naive datetime
with an aware one raises ``TypeError`` rather than returning a wrong answer.
So the invariants they enforce were only ever as sound as the timezone
discipline of whoever built the record, and the failure mode was an
unrelated-looking crash rather than a refusal that names the problem.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from ....domain.user_profile import ProfileSetupState
from .._values import UserProfileFact, UserProfileRecord, UserProfileSnapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PROFILE_ID = "a4f1c2e0-1111-4222-8333-444455556666"
_UTC_INSTANT = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
_NAIVE_INSTANT = datetime(2026, 1, 1, 10, 0, 0)
_OFFSET_INSTANT = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone(timedelta(hours=1)))

_REFUSED = ((_NAIVE_INSTANT, "naive"), (_OFFSET_INSTANT, "offset"))
_REFUSED_INSTANTS = tuple(instant for instant, _ in _REFUSED)
_REFUSED_IDS = tuple(label for _, label in _REFUSED)


def _facts() -> tuple[UserProfileFact, ...]:
    return (UserProfileFact(path="identity.tax_id", value="12345678Z"),)


@pytest.mark.parametrize("instant", _REFUSED_INSTANTS, ids=_REFUSED_IDS)
@pytest.mark.parametrize("field", ("created_at", "updated_at"))
def test_record_refuses_a_non_utc_lifecycle_instant(field: str, instant: datetime) -> None:
    values = {"created_at": _UTC_INSTANT, "updated_at": _UTC_INSTANT, field: instant}

    with pytest.raises(ValidationError):
        UserProfileRecord.model_validate(
            {
                "profile_id": _PROFILE_ID,
                "facts": _facts(),
                **values,
            },
        )


@pytest.mark.parametrize("instant", _REFUSED_INSTANTS, ids=_REFUSED_IDS)
def test_snapshot_refuses_a_non_utc_created_at(instant: datetime) -> None:
    record = UserProfileRecord(setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=_facts(),
        created_at=_UTC_INSTANT,
        updated_at=_UTC_INSTANT,
    )

    with pytest.raises(ValidationError):
        UserProfileSnapshot.from_profile(record, created_at=instant)


def test_record_refuses_a_non_utc_instant_from_serialized_text() -> None:
    """Hydration is the path that mattered: a stored naive value must not reload."""
    record = UserProfileRecord(setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=_facts(),
        created_at=_UTC_INSTANT,
        updated_at=_UTC_INSTANT,
    )
    payload = record.model_dump(mode="json")
    payload["updated_at"] = "2026-01-01T10:00:00"

    with pytest.raises(ValidationError):
        UserProfileRecord.model_validate(payload)


def test_a_utc_record_round_trips_canonically() -> None:
    record = UserProfileRecord(setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=_facts(),
        created_at=_UTC_INSTANT,
        updated_at=_UTC_INSTANT,
    )

    restored = UserProfileRecord.model_validate_json(record.model_dump_json())

    assert restored == record
    assert restored.created_at.utcoffset() == timedelta(0)
    assert restored.updated_at.utcoffset() == timedelta(0)
