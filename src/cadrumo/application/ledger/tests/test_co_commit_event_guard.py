"""The guarded co-commit retries instead of discarding a concurrent event.

Some ledger writes must land their audit entry in the SAME batch as the record
it describes. The application policy therefore reads the event catalogue with
its revision and retries when the owning transaction repository rejects a stale
write. These tests keep that policy inward: both repositories are small,
protocol-shaped in-memory fakes. The real encrypted SQL/runtime integration
lives at the profile-persistence adapter boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from ....domain.buckets.event import (
    BucketEvent,
    BucketEventHistoryCatalogue,
    BucketEventObjectType,
    BucketEventType,
)
from ....domain.buckets.event_repository import append_bucket_event, build_bucket_event
from ....domain.transactions.models import TransactionCatalogue
from ..actions_common import _commit_with_guarded_events
from ..persistence_ports import LedgerPersistenceConflictError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "3f3f3f3f-3f3f-43f3-8f3f-3f3f3f3f3f3f"
_AT = datetime(2026, 7, 1, 9, 0, tzinfo=UTC)

#: Markers this module emits.
_MARKERS = frozenset({"co-committed", "interloper"})


@dataclass(frozen=True)
class _PreparedEventWrite:
    """Small in-memory equivalent of the event port's prepared write."""

    catalogue: BucketEventHistoryCatalogue
    expected_revision_id: str | None


class _EventRepository:
    """In-memory revisioned event-history port for application policy tests."""

    def __init__(self) -> None:
        self.catalogue = BucketEventHistoryCatalogue()
        self.revision = "0"

    def exists(self) -> bool:
        return bool(self.catalogue.events)

    def load(self) -> BucketEventHistoryCatalogue:
        return self.catalogue

    def save(self, catalogue: BucketEventHistoryCatalogue) -> None:
        self.catalogue = catalogue
        self.revision = str(int(self.revision) + 1)

    def load_revisioned(self) -> tuple[BucketEventHistoryCatalogue, str]:
        return self.catalogue, self.revision

    def to_secure_object_write(
        self,
        catalogue: BucketEventHistoryCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> _PreparedEventWrite:
        return _PreparedEventWrite(catalogue, expected_revision_id)

    def commit(self, write: _PreparedEventWrite) -> None:
        if write.expected_revision_id != self.revision:
            raise LedgerPersistenceConflictError("event-history revision changed during co-commit")
        self.save(write.catalogue)


class _TransactionRepository:
    """In-memory transaction co-commit port with an optional first-write race."""

    def __init__(self, events: _EventRepository, *, interloper: bool = False) -> None:
        self.events = events
        self.interloper = interloper
        self.attempts = 0

    def save_with_secure_object_writes(
        self,
        _catalogue: TransactionCatalogue,
        extra_writes: tuple[_PreparedEventWrite, ...],
    ) -> None:
        self.attempts += 1
        if self.interloper and self.attempts == 1:
            self.events.save(append_bucket_event(self.events.load(), _event("interloper")))
        self.events.commit(extra_writes[0])


def _event(object_id: str) -> BucketEvent:
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


def _recorded(repository: _EventRepository) -> list[str]:
    catalogue = repository.load()
    return sorted(event.object_id for event in catalogue.events.values() if (event.object_id or "") in _MARKERS)


def test_a_co_committed_event_is_persisted() -> None:
    """Baseline: the application composition supplies its event to the batch."""
    events = _EventRepository()
    transactions = _TransactionRepository(events)

    _commit_with_guarded_events(
        event_repository=events,
        events=(_event("co-committed"),),
        commit=lambda write: transactions.save_with_secure_object_writes(
            TransactionCatalogue.from_transactions([]),
            (write,),
        ),
    )

    assert _recorded(events) == ["co-committed"]


def test_a_concurrent_event_is_not_discarded_by_the_co_commit() -> None:
    """The interleaving that used to lose an audit entry is retried."""
    events = _EventRepository()
    transactions = _TransactionRepository(events, interloper=True)

    _commit_with_guarded_events(
        event_repository=events,
        events=(_event("co-committed"),),
        commit=lambda write: transactions.save_with_secure_object_writes(
            TransactionCatalogue.from_transactions([]),
            (write,),
        ),
    )

    assert transactions.attempts == 2
    assert _recorded(events) == ["co-committed", "interloper"]
