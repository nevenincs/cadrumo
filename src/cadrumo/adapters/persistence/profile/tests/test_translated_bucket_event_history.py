"""Translated history retains the encrypted repository's CAS append."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from .....domain.buckets.event import (
    BucketEvent,
    BucketEventHistoryCatalogue,
    BucketEventObjectType,
    BucketEventType,
)
from .....domain.buckets.event_repository import append_bucket_event, build_bucket_event, emit_bucket_events
from ...tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ..buckets import BucketEventHistoryRepository
from ..translated_bucket_event_history import TranslatedBucketEventHistoryRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "6e6e6e6e-6e6e-46e6-8e6e-6e6e6e6e6e6e"
_runtime_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID)


def _event(marker: str) -> BucketEvent:
    return build_bucket_event(
        bucket_id=_BUCKET_ID,
        event_type=BucketEventType.PROFILE_VALUES_UPDATED,
        occurred_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
        actor="test",
        object_type=BucketEventObjectType.PROFILE,
        object_id=marker,
        payload={"marker": marker},
        payload_version=1,
    )


def _translate[T](_operation: str, action: Callable[[], T]) -> T:
    return action()


def test_translated_append_retries_after_real_interleaved_history_write() -> None:
    repository = TranslatedBucketEventHistoryRepository(
        repository=BucketEventHistoryRepository(),
        translate=_translate,
    )
    interloper_written = False

    def append_with_interloper(current: BucketEventHistoryCatalogue) -> BucketEventHistoryCatalogue:
        nonlocal interloper_written
        if not interloper_written:
            interloper_written = True
            emit_bucket_events(
                repository=BucketEventHistoryRepository(),
                events=(_event("interloper"),),
            )
        return append_bucket_event(current, _event("export"))

    repository.append_guarded(append_with_interloper)

    stored = BucketEventHistoryRepository().load()
    markers = {event.object_id for event in stored.events.values() if event.object_id in {"interloper", "export"}}
    assert markers == {"interloper", "export"}
