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

from ....core.hashing import content_hash_hex
from ....domain.calculations.registry.tests.published_authority import published_profile_schema
from ...calculations.registry.authority_artifact import (
    AuthorityGenerationPin,
    ProfileCreateContext,
    ProfileDecodeContext,
)
from ..values import (
    ProfileSetupState,
    UserProfileFact,
    UserProfileRecord,
    UserProfileSnapshot,
    create_user_profile_record,
    decode_user_profile_record,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PROFILE_ID = "a4f1c2e0-1111-4222-8333-444455556666"
_UTC_INSTANT = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
_NAIVE_INSTANT = datetime(2026, 1, 1, 10, 0, 0)
_OFFSET_INSTANT = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone(timedelta(hours=1)))
_SCHEMA = published_profile_schema()
_PIN = AuthorityGenerationPin(
    content_hash_hex({"generation": "profile-lifecycle-fixture"}),
    content_hash_hex({"reader": "profile-lifecycle-fixture"}),
)
_CREATE = ProfileCreateContext(schema=_SCHEMA, generation=_PIN)
_DECODE = ProfileDecodeContext(schema=_SCHEMA, generation=_PIN)

_REFUSED = ((_NAIVE_INSTANT, "naive"), (_OFFSET_INSTANT, "offset"))
_REFUSED_INSTANTS = tuple(instant for instant, _ in _REFUSED)
_REFUSED_IDS = tuple(label for _, label in _REFUSED)


def _facts() -> tuple[UserProfileFact, ...]:
    return (UserProfileFact(path="identity.tax_id", value="12345678Z"),)


def _record() -> UserProfileRecord:
    return create_user_profile_record(
        context=_CREATE,
        profile_id=_PROFILE_ID,
        facts=_facts(),
        setup_state=ProfileSetupState.COMPLETE,
        created_at=_UTC_INSTANT,
        updated_at=_UTC_INSTANT,
    )


@pytest.mark.parametrize("instant", _REFUSED_INSTANTS, ids=_REFUSED_IDS)
@pytest.mark.parametrize("field", ("created_at", "updated_at"))
def test_record_refuses_a_non_utc_lifecycle_instant(field: str, instant: datetime) -> None:
    values = {"created_at": _UTC_INSTANT, "updated_at": _UTC_INSTANT, field: instant}

    payload = _record().model_dump()
    payload.update(values)
    with pytest.raises(ValidationError):
        decode_user_profile_record(payload, context=_DECODE)


@pytest.mark.parametrize("instant", _REFUSED_INSTANTS, ids=_REFUSED_IDS)
def test_snapshot_refuses_a_non_utc_created_at(instant: datetime) -> None:
    record = _record()

    with pytest.raises(ValidationError):
        UserProfileSnapshot.from_profile(record, context=_CREATE, created_at=instant)


def test_record_refuses_a_non_utc_instant_from_serialized_text() -> None:
    """Hydration is the path that mattered: a stored naive value must not reload."""
    record = _record()
    payload = record.model_dump(mode="json")
    payload["updated_at"] = "2026-01-01T10:00:00"

    with pytest.raises(ValidationError):
        decode_user_profile_record(payload, context=_DECODE)


def test_a_utc_record_round_trips_canonically() -> None:
    record = _record()

    restored = decode_user_profile_record(record.model_dump_json(), context=_DECODE)

    assert restored == record
    assert restored.created_at.utcoffset() == timedelta(0)
    assert restored.updated_at.utcoffset() == timedelta(0)
