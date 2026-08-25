"""Direct domain tests: appending never erases an immutable audit revision.

``derive_bucket_event_id`` hashes every event field except ``payload_version``,
and ``append_bucket_event`` assigned by id. Two events could therefore share
an id while disagreeing about their payload contract, and the later one
silently replaced the earlier -- leaving a catalogue that still looked like
one content-addressed record, so nothing downstream could tell a revision had
been erased.

The documented guarantee was "the existing entry is left in place", which is
indistinguishable from unconditional assignment for an identical event. That
equivalence is why the gap held: every ordinary emission exercised the path
and none of them could show the difference.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ..errors import BucketEventValidationError
from .._event import (
    BucketEvent,
    BucketEventHistoryCatalogue,
    BucketEventObjectType,
    BucketEventType,
    derive_bucket_event_id,
)
from .._event_repository import append_bucket_event

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BUCKET = "5612ee74-f4e5-47c2-9df9-2afa04286b2a"  # was 'operator-a'
_OBJECT_ID = "d" * 64
_INSTANT = datetime(2026, 4, 1, 10, 0, 0, tzinfo=UTC)


def _event(payload_version: int) -> BucketEvent:
    shared = {
        "bucket_id": _BUCKET,
        "event_type": BucketEventType.PROFILE_RENAMED,
        "occurred_at": _INSTANT,
        "actor": "operator",
        "object_type": BucketEventObjectType.PROFILE,
        "object_id": _OBJECT_ID,
        "payload": {"previous_display_name": "old"},
    }
    return BucketEvent(
        event_id=derive_bucket_event_id(**shared),
        payload_version=payload_version,
        **shared,
    )


def test_two_versions_of_one_body_share_a_derived_id() -> None:
    """The premise: payload_version is the one field outside the identity."""
    assert _event(1).event_id == _event(2).event_id


def test_a_colliding_version_is_refused_rather_than_folded_in() -> None:
    catalogue = append_bucket_event(BucketEventHistoryCatalogue(), _event(1))

    with pytest.raises(BucketEventValidationError) as raised:
        append_bucket_event(catalogue, _event(2))

    # Both versions travel as facts, which is what lets a caller see which
    # revision it would have overwritten without parsing a sentence.
    error = raised.value
    context = error.context
    assert context is not None
    assert context["recorded_payload_version"] == 1
    assert context["offered_payload_version"] == 2
    assert context["payload_versions_agree"] is False
    assert str(error) == error.translated_message, f"the raise site carries an authored sentence: {str(error)!r}"


def test_the_refused_append_leaves_the_original_revision_intact() -> None:
    catalogue = append_bucket_event(BucketEventHistoryCatalogue(), _event(1))

    with pytest.raises(BucketEventValidationError):
        append_bucket_event(catalogue, _event(2))

    assert len(catalogue) == 1
    assert next(iter(catalogue)).payload_version == 1


def test_an_identical_event_still_collapses_to_one_entry() -> None:
    """Idempotence for a true re-emission has to survive the refusal."""
    first = append_bucket_event(BucketEventHistoryCatalogue(), _event(1))

    second = append_bucket_event(first, _event(1))

    assert len(second) == 1
    assert second == first


def test_distinct_events_still_accumulate() -> None:
    catalogue = append_bucket_event(BucketEventHistoryCatalogue(), _event(1))
    other_body = {
        "bucket_id": _BUCKET,
        "event_type": BucketEventType.PROFILE_SELECTED,
        "occurred_at": _INSTANT,
        "actor": "operator",
        "object_type": BucketEventObjectType.PROFILE,
        "object_id": _OBJECT_ID,
        "payload": {},
    }
    other = BucketEvent(
        event_id=derive_bucket_event_id(**other_body),
        payload_version=1,
        **other_body,
    )

    assert len(append_bucket_event(catalogue, other)) == 2
