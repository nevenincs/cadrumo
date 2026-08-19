"""Concurrent event emissions do not discard each other's audit entries.

The bucket event history is a SINGLETON row, so appending one event rewrites the
whole catalogue. Performed unguarded, two callers recording DIFFERENT
transitions both read the same catalogue and the later write discards the
earlier event.

This is the worst shape that loss can take. The events are content-addressed, so
every survivor is internally consistent and the discarded one leaves no gap to
notice: the trail reads as complete while an operator action has vanished from
it. An append-only audit trail that silently drops entries is less trustworthy
than one that refuses, because nothing downstream can tell the difference.

Observed deterministically, by landing the interloping emission inside the
guarded unit of work's read-to-write window rather than by racing threads.

Real behaviour throughout: a real isolated bucket runtime, the real encrypted SQL
backend, independent repository instances. Nothing is mocked.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from .....domain.buckets import (
    BucketEventObjectType,
    BucketEventType,
    append_bucket_event,
    build_bucket_event,
    emit_bucket_events,
)
from ...tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ..buckets import BucketEventHistoryRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "7e7e7e7e-7e7e-47e7-8e7e-7e7e7e7e7e7e"

_runtime_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID)


def _event(object_id: str):
    """Build one distinguishable lifecycle event."""
    return build_bucket_event(
        bucket_id=_BUCKET_ID,
        event_type=BucketEventType.PROFILE_VALUES_UPDATED,
        occurred_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
        actor="test",
        object_type=BucketEventObjectType.PROFILE,
        object_id=object_id,
        payload={"marker": object_id},
        payload_version=1,
    )


#: Marker ids this module emits. The runtime fixture records its own profile
#: lifecycle event, so the catalogue is never empty and an assertion over EVERY
#: entry would be asserting the fixture's behaviour alongside the subject's.
_MARKERS = frozenset({"first", "second", "interloper", "batch-a", "batch-b"})


def _object_ids() -> list[str]:
    catalogue = BucketEventHistoryRepository().load()
    return sorted(
        event.object_id for event in catalogue.events.values() if (event.object_id or "") in _MARKERS
    )


def test_sequentially_emitted_events_accumulate() -> None:
    """Baseline: two emissions do not lose an entry on their own."""
    emit_bucket_events(repository=BucketEventHistoryRepository(), events=[_event("first")])
    emit_bucket_events(repository=BucketEventHistoryRepository(), events=[_event("second")])

    assert _object_ids() == ["first", "second"]


def test_a_concurrent_emission_is_not_discarded() -> None:
    """DISCRIMINATING: the interleaving that used to lose an audit entry.

    The interloper records its own transition inside the first emission's
    read-to-write window. Unguarded, the first write rebuilds from the catalogue
    it read before the interloper existed and overwrites it away.
    """
    repository = BucketEventHistoryRepository()
    interloper_written = False

    def _emit_one_while_another_lands(current):
        nonlocal interloper_written
        if not interloper_written:
            interloper_written = True
            emit_bucket_events(
                repository=BucketEventHistoryRepository(),
                events=[_event("interloper")],
            )
        return append_bucket_event(current, _event("first"))

    repository.append_guarded(_emit_one_while_another_lands)

    assert _object_ids() == ["first", "interloper"]


def test_a_batch_emission_does_not_discard_a_concurrent_entry() -> None:
    """A batch rewrites the catalogue once, so it can discard more at a time.

    The batch path exists to pay one round-trip for N events. That makes its
    read-to-write window wider than a single emission's, not narrower, so it
    needs the guard at least as much.
    """
    repository = BucketEventHistoryRepository()
    interloper_written = False

    def _emit_batch_while_another_lands(current):
        nonlocal interloper_written
        if not interloper_written:
            interloper_written = True
            emit_bucket_events(
                repository=BucketEventHistoryRepository(),
                events=[_event("interloper")],
            )
        catalogue = current
        for object_id in ("batch-a", "batch-b"):
            catalogue = append_bucket_event(catalogue, _event(object_id))
        return catalogue

    repository.append_guarded(_emit_batch_while_another_lands)

    assert _object_ids() == ["batch-a", "batch-b", "interloper"]
