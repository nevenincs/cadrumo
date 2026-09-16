"""A ledger field update decrypts the bucket's transaction catalogue once.

The catalogue is the whole bucket re-validated row by row on every load, so an
update that reads it twice pays that twice for nothing: no write happens between
the two reads. The count is taken on the real encrypted repository.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import override

import pytest

from .....application.ledger.action_ports import LedgerActionPorts
from .....application.ledger.actions_manual import (
    create_manual_transaction,
    update_manual_transaction,
    update_manual_transaction_fields,
)
from .....application.ledger.models import ManualLedgerTransactionCommand, ManualLedgerTransactionPatch
from .....domain.transactions.enums import BusinessClassification, TransactionDirection
from .....domain.transactions.models import TransactionCatalogue
from ...storage.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ..buckets import BucketEventHistoryRepository
from ..modelos_calculation import CalculationRevisionCatalogueRepository
from ..modelos_work_units import WorkUnitCatalogueRepository
from ..transactions import TransactionCatalogueRepository
from .ledger_action_create_support import ledger_ports_for_test

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_BUCKET = "41414141-4141-4141-8141-414141414141"


class _CountingTransactionRepository(TransactionCatalogueRepository):
    """The real encrypted repository, counting whole-catalogue decrypts."""

    loads = 0

    @override
    def load(self) -> TransactionCatalogue:
        self.loads += 1
        return super().load()


type _Counted = tuple[_CountingTransactionRepository, str, LedgerActionPorts]


@pytest.fixture
def profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as runtime:
        yield runtime


def _seed_command() -> ManualLedgerTransactionCommand:
    return ManualLedgerTransactionCommand(
        bucket_id=_BUCKET,
        booked_date=date(2026, 2, 11),
        amount=Decimal("121.00"),
        direction=TransactionDirection.OUTGOING,
        description="material oficina",
        business_classification=BusinessClassification.BUSINESS,
        idempotency_key="loads-once",
    )


def _seed(profile: TestRuntimeProfile, repository: TransactionCatalogueRepository) -> str:
    with ledger_ports_for_test(
        bucket_id=_BUCKET,
        objects=profile.repository,
        transaction_repository=repository,
        bucket_event_repository=BucketEventHistoryRepository(objects=profile.repository),
        work_unit_repository=WorkUnitCatalogueRepository(objects=profile.repository),
        calculation_repository=CalculationRevisionCatalogueRepository(objects=profile.repository),
    ) as ports:
        created = create_manual_transaction(
            _seed_command(),
            ports=ports,
            occurred_at=datetime(2026, 2, 11, 8, 0, tzinfo=UTC),
        )
    return created.ref.transaction_id


@pytest.fixture
def counted(profile: TestRuntimeProfile) -> Iterator[_Counted]:
    repository = _CountingTransactionRepository(bucket_id=_BUCKET, objects=profile.repository)
    transaction_id = _seed(profile, repository)
    with ledger_ports_for_test(
        bucket_id=_BUCKET,
        objects=profile.repository,
        transaction_repository=repository,
        bucket_event_repository=BucketEventHistoryRepository(objects=profile.repository),
        work_unit_repository=WorkUnitCatalogueRepository(objects=profile.repository),
        calculation_repository=CalculationRevisionCatalogueRepository(objects=profile.repository),
    ) as ports:
        repository.loads = 0
        yield repository, transaction_id, ports


def test_a_field_update_loads_the_catalogue_once(counted: _Counted) -> None:
    repository, transaction_id, ports = counted

    result = update_manual_transaction_fields(
        bucket_id=_BUCKET,
        transaction_id=transaction_id,
        patch=ManualLedgerTransactionPatch(group_label="Cierre 2025"),
        actor="operator",
        source_command="aeat app ledger update",
        ports=ports,
    )

    assert result.bucket_event_ids, "the update must actually write, or the count proves nothing"
    assert repository.loads == 1


def test_an_update_handed_no_snapshot_loads_its_own(counted: _Counted) -> None:
    """The count sees a second read: the shape a dropped pass-through reintroduces."""
    repository, transaction_id, ports = counted
    repository.load()

    update_manual_transaction(
        transaction_id=transaction_id,
        command=_seed_command().model_copy(update={"notes": "revisado"}),
        ports=ports,
    )

    assert repository.loads == 2
