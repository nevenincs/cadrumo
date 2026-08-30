"""A co-committed audit entry does not discard a concurrent one.

Some ledger writes must land their audit entry in the SAME batch as the record
it describes -- otherwise a crash records a linkage that never happened, or
lands one with nothing saying so. That rules out the self-committing domain
emitter, which writes on its own.

What the composition lacked was the guard. It read the event catalogue and
handed it straight to the batch, writing back the revision it had read, so an
event another writer appended in between was discarded. It is the same
singleton-row loss ``append_guarded`` closes for the standalone path, surviving
on the one shape that could not use it -- and content-addressed events hide it
perfectly, because every survivor stays internally consistent and the missing
one leaves no gap.

Observed deterministically rather than by racing threads: the interloper is
landed INSIDE the composition's read-to-write window, which the retry makes
reachable. That matters here, because worker threads do not inherit the
active-session ContextVar and so cannot drive a second writer in-process at all.

Real bucket runtime, real encrypted SQL backend, real repositories. Nothing is
mocked; the only fault injected is a real second write.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....domain.buckets import (
    BucketEventObjectType,
    BucketEventType,
    build_bucket_event,
    emit_bucket_events,
)
from ....domain.transactions.models import TransactionCatalogue
from ....tests.secure_sql import isolated_runtime_profile
from ..actions_common import _commit_with_guarded_events

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "3f3f3f3f-3f3f-43f3-8f3f-3f3f3f3f3f3f"
_AT = datetime(2026, 7, 1, 9, 0, tzinfo=UTC)

#: Markers this module emits. The runtime fixture records its own lifecycle
#: events, so asserting over EVERY entry would assert the fixture's behaviour
#: alongside the subject's.
_MARKERS = frozenset({"co-committed", "interloper"})


def _event(object_id: str):
    """Build one distinguishable audit entry."""
    return build_bucket_event(
        bucket_id=_BUCKET,
        event_type=BucketEventType.PROFILE_VALUES_UPDATED,
        occurred_at=_AT,
        actor="test",
        object_type=BucketEventObjectType.PROFILE,
        object_id=object_id,
        payload={"marker": object_id},
        payload_version=1,
    )


def _recorded() -> list[str]:
    catalogue = BucketEventHistoryRepository().load()
    return sorted(event.object_id for event in catalogue.events.values() if (event.object_id or "") in _MARKERS)


def test_a_co_committed_event_is_persisted(tmp_path: Path) -> None:
    """Baseline: the composition still writes its event and its record."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET):
        transactions = TransactionCatalogueRepository(bucket_id=_BUCKET)

        _commit_with_guarded_events(
            event_repository=BucketEventHistoryRepository(),
            events=(_event("co-committed"),),
            commit=lambda write: transactions.save_with_secure_object_writes(
                TransactionCatalogue.from_transactions([]),
                (write,),
            ),
        )

        assert _recorded() == ["co-committed"]


def test_a_concurrent_event_is_not_discarded_by_the_co_commit(tmp_path: Path) -> None:
    """DISCRIMINATING: the interleaving that used to lose an audit entry.

    The interloper records its own transition inside the composition's
    read-to-write window. Unguarded, the batch writes back the catalogue it read
    before the interloper existed and overwrites it away -- leaving a trail that
    still reads as complete.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET):
        transactions = TransactionCatalogueRepository(bucket_id=_BUCKET)
        interloper_written = False

        def _commit_while_another_lands(write):
            nonlocal interloper_written
            if not interloper_written:
                interloper_written = True
                emit_bucket_events(
                    repository=BucketEventHistoryRepository(),
                    events=[_event("interloper")],
                )
            transactions.save_with_secure_object_writes(
                TransactionCatalogue.from_transactions([]),
                (write,),
            )

        _commit_with_guarded_events(
            event_repository=BucketEventHistoryRepository(),
            events=(_event("co-committed"),),
            commit=_commit_while_another_lands,
        )

        assert _recorded() == ["co-committed", "interloper"]
