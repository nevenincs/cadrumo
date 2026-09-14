"""Real profile repositories preserve guarded ledger co-commit atomicity.

The application policy is exercised with inward fakes in
``application.ledger.tests.test_co_commit_event_guard``. This file owns the
outer seam: an isolated encrypted SQL runtime, concrete event and transaction
repositories, and the public ledger composition that joins them.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.ledger.actions_common import save_transaction_catalogue_and_events
from cadrumo.core.secure_object_write import SecureObjectWrite
from cadrumo.domain.buckets.event import BucketEventObjectType, BucketEventType
from cadrumo.domain.buckets.event_repository import build_bucket_event, emit_bucket_events
from cadrumo.domain.transactions.models import TransactionCatalogue

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

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


class _InterleavingTransactionWriter:
    """Inject one real competing event write before the first transaction batch."""

    def __init__(
        self,
        delegate: TransactionCatalogueRepository,
        event_repository: BucketEventHistoryRepository,
    ) -> None:
        self._delegate = delegate
        self._event_repository = event_repository
        self._interloper_written = False

    def save_with_secure_object_writes(
        self,
        catalogue: TransactionCatalogue,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        if not self._interloper_written:
            self._interloper_written = True
            emit_bucket_events(
                repository=self._event_repository,
                events=[_event("interloper")],
            )
        self._delegate.save_with_secure_object_writes(catalogue, extra_writes)


def test_a_co_committed_event_is_persisted(tmp_path: Path) -> None:
    """Baseline: the public ledger composition writes its event and record."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET):
        transactions = TransactionCatalogueRepository(bucket_id=_BUCKET)

        save_transaction_catalogue_and_events(
            transaction_repository=transactions,
            event_repository=BucketEventHistoryRepository(),
            catalogue=TransactionCatalogue.from_transactions([]),
            events=(_event("co-committed"),),
        )

        assert _recorded() == ["co-committed"]


def test_a_concurrent_event_is_not_discarded_by_the_co_commit(tmp_path: Path) -> None:
    """The guarded public composition retries after a real competing event."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET):
        event_repository = BucketEventHistoryRepository()
        transactions = _InterleavingTransactionWriter(
            TransactionCatalogueRepository(bucket_id=_BUCKET),
            event_repository,
        )

        save_transaction_catalogue_and_events(
            transaction_repository=transactions,
            event_repository=event_repository,
            catalogue=TransactionCatalogue.from_transactions([]),
            events=(_event("co-committed"),),
        )

        assert _recorded() == ["co-committed", "interloper"]
