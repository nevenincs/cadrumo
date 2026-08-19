"""Direct domain tests: same-instant bucket events order deterministically.

Ordering on ``occurred_at`` alone is not a total order. Emissions inside one
operation share an instant by design -- a rename emits the lifecycle event
and the maintenance event at the same ``now()`` -- so ties fell through to
whatever order the catalogue mapping happened to hold. Two readers of the
same persisted events could render the operator different timelines, and
one reader could change its mind after a reload, with no validation error
anywhere: nothing was wrong with the data.

These tests build one event set twice in opposite insertion orders. Under
the old key the two catalogues disagreed; under the shared
``(occurred_at, event_id)`` key they cannot.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from .._event import (
    BucketEvent,
    BucketEventHistoryCatalogue,
    BucketEventObjectType,
    BucketEventType,
    bucket_event_order_key,
    derive_bucket_event_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BUCKET = "5612ee74-f4e5-47c2-9df9-2afa04286b2a"  # was 'operator-a'
_OBJECT_ID = "c" * 64
_SAME_INSTANT = datetime(2026, 4, 1, 10, 0, 0, tzinfo=UTC)
_LATER = datetime(2026, 4, 1, 11, 0, 0, tzinfo=UTC)


def _event(actor: str, occurred_at: datetime = _SAME_INSTANT) -> BucketEvent:
    """Build a valid event distinguished only by ``actor`` (and so by id)."""
    shared = {
        "bucket_id": _BUCKET,
        "event_type": BucketEventType.PROFILE_RENAMED,
        "occurred_at": occurred_at,
        "actor": actor,
        "object_type": BucketEventObjectType.PROFILE,
        "object_id": _OBJECT_ID,
        "payload": {},
    }
    return BucketEvent(
        event_id=derive_bucket_event_id(**shared),
        payload_version=1,
        **shared,
    )


def _catalogue(*events: BucketEvent) -> BucketEventHistoryCatalogue:
    return BucketEventHistoryCatalogue(events={event.event_id: event for event in events})


def test_for_object_is_insertion_order_independent() -> None:
    first = _event("profile-lifecycle")
    second = _event("bucket-maintenance")

    forward = _catalogue(first, second).for_object(
        object_type=BucketEventObjectType.PROFILE,
        object_id=_OBJECT_ID,
    )
    reversed_insertion = _catalogue(second, first).for_object(
        object_type=BucketEventObjectType.PROFILE,
        object_id=_OBJECT_ID,
    )

    assert first.occurred_at == second.occurred_at
    assert forward == reversed_insertion


def test_for_bucket_is_insertion_order_independent() -> None:
    first = _event("profile-lifecycle")
    second = _event("bucket-maintenance")

    forward = _catalogue(first, second).for_bucket(_BUCKET)
    reversed_insertion = _catalogue(second, first).for_bucket(_BUCKET)

    assert forward == reversed_insertion


def test_the_tie_break_never_overrides_chronology() -> None:
    """The id only decides ties; a later instant still sorts later."""
    early = _event("zzz-actor", _SAME_INSTANT)
    late = _event("aaa-actor", _LATER)

    ordered = _catalogue(late, early).for_bucket(_BUCKET)

    assert ordered == (early, late)


def test_the_order_key_is_the_instant_then_the_content_address() -> None:
    event = _event("profile-lifecycle")

    assert bucket_event_order_key(event) == (event.occurred_at, event.event_id)
