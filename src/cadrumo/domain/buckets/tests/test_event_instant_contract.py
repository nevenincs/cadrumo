"""Direct domain tests: a bucket event's instant is UTC or it is refused.

``occurred_at`` documents a UTC timestamp but was a bare ``datetime``, so
the model accepted a naive value and a non-UTC offset. That is worse here
than at an ordinary field, because the instant is *hashed as text* into the
event's content-addressed id: each spelling of one moment produced a
different id, and the append path assigns by id. The same event submitted
under two spellings therefore became two immutable audit rows instead of
collapsing to one, which is the opposite of the idempotence the catalogue
documents.

These tests pin refusal at both boundaries an event can enter through --
the derivation helper and the model -- and pin that a valid UTC event still
survives a real encrypted round-trip.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from ....core.errors.hierarchy import CoreValidationError
from ..event import (
    BucketEvent,
    BucketEventObjectType,
    BucketEventType,
    derive_bucket_event_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BUCKET = "5612ee74-f4e5-47c2-9df9-2afa04286b2a"  # was 'operator-a'
_OBJECT_ID = "b" * 64
_UTC_INSTANT = datetime(2026, 4, 1, 10, 0, 0, tzinfo=UTC)
_NAIVE_INSTANT = datetime(2026, 4, 1, 10, 0, 0)  # the refused shape under test
_OFFSET_INSTANT = datetime(2026, 4, 1, 11, 0, 0, tzinfo=timezone(timedelta(hours=1)))

_REFUSED_INSTANTS = (_NAIVE_INSTANT, _OFFSET_INSTANT)


def _derive(occurred_at: datetime) -> str:
    return derive_bucket_event_id(
        bucket_id=_BUCKET,
        event_type=BucketEventType.BUCKET_RENAMED,
        occurred_at=occurred_at,
        actor="operator",
        object_type=BucketEventObjectType.BUCKET,
        object_id=_OBJECT_ID,
        payload={},
    )


@pytest.mark.parametrize("instant", _REFUSED_INSTANTS, ids=("naive", "offset"))
def test_derivation_refuses_a_non_utc_instant(instant: datetime) -> None:
    with pytest.raises(CoreValidationError):
        _derive(instant)


@pytest.mark.parametrize("instant", _REFUSED_INSTANTS, ids=("naive", "offset"))
def test_model_refuses_a_non_utc_instant(instant: datetime) -> None:
    event_id = _derive(_UTC_INSTANT)

    with pytest.raises(ValidationError):
        BucketEvent(
            event_id=event_id,
            bucket_id=_BUCKET,
            event_type=BucketEventType.BUCKET_RENAMED,
            occurred_at=instant,
            actor="operator",
            object_type=BucketEventObjectType.BUCKET,
            object_id=_OBJECT_ID,
            payload_version=1,
            payload={},
        )


def test_model_refuses_a_non_utc_instant_from_serialized_text() -> None:
    """The refusal must hold on the hydration path, not only on construction."""
    event = _valid_event()
    payload = event.model_dump(mode="json")
    payload["occurred_at"] = "2026-04-01T10:00:00"

    with pytest.raises(ValidationError):
        BucketEvent.model_validate(payload)


def _valid_event() -> BucketEvent:
    return BucketEvent(
        event_id=_derive(_UTC_INSTANT),
        bucket_id=_BUCKET,
        event_type=BucketEventType.BUCKET_RENAMED,
        occurred_at=_UTC_INSTANT,
        actor="operator",
        object_type=BucketEventObjectType.BUCKET,
        object_id=_OBJECT_ID,
        payload_version=1,
        payload={},
    )


def test_a_utc_event_round_trips_unchanged() -> None:
    event = _valid_event()

    restored = BucketEvent.model_validate_json(event.model_dump_json())

    assert restored == event
    assert restored.occurred_at == _UTC_INSTANT
    assert restored.occurred_at.utcoffset() == timedelta(0)


def test_one_moment_has_exactly_one_derived_identity() -> None:
    """The reason refusal beats coercion here: admitting spellings forks the id."""
    same_moment_as_offset = _UTC_INSTANT.astimezone(timezone(timedelta(hours=2)))

    assert same_moment_as_offset == _UTC_INSTANT
    with pytest.raises(CoreValidationError):
        _derive(same_moment_as_offset)
