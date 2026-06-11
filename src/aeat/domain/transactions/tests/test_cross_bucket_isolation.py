"""Cross-profile (cross-bucket) ledger isolation.

The cross-profile runtime-pegged ledger goal: each profile bucket owns an
independent transaction catalogue, keyed by ``bucket_id`` in the secure store.
This proves no cross-bucket leakage: a row saved under one bucket never appears
under another, and each bucket reloads exactly its own rows.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage import SecureObjectRepository
from ....tests.secure_sql import isolated_runtime_profile
from .. import (
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionDirection,
    TransactionLifecycleState,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_NOW = datetime(2026, 6, 3, 12, 0, tzinfo=UTC)


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        yield profile.repository


def _tx(
    provider_id: str,
    *,
    amount: Decimal,
    direction: TransactionDirection = TransactionDirection.OUTGOING,
) -> Transaction:
    raw = RawTransaction(
        transaction_id=provider_id,
        booked_date=date(2026, 4, 5),
        value_date=date(2026, 4, 5),
        amount=amount,
        currency="EUR",
        counterparty="Counterparty",
        description=f"row {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_NOW,
            provider_name="manual",
        ),
        raw_fields={"k": "v"},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": direction,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
        },
    )


def test_each_bucket_ledger_is_independent(secure_objects: SecureObjectRepository) -> None:
    marta = TransactionCatalogueRepository(bucket_id="marta", objects=secure_objects)
    retailer = TransactionCatalogueRepository(bucket_id="retailer", objects=secure_objects)

    marta_tx = _tx("marta-1", amount=Decimal("100.00"))
    retailer_tx = _tx("retailer-1", amount=Decimal("250.00"))
    marta.save(TransactionCatalogue.from_transactions((marta_tx,)))
    retailer.save(TransactionCatalogue.from_transactions((retailer_tx,)))

    marta_rows = tuple(marta.load().values())
    retailer_rows = tuple(retailer.load().values())

    assert [t.transaction_id for t in marta_rows] == [marta_tx.transaction_id]
    assert [t.transaction_id for t in retailer_rows] == [retailer_tx.transaction_id]
    # No cross-bucket leakage in either direction.
    assert retailer_tx.transaction_id not in {t.transaction_id for t in marta_rows}
    assert marta_tx.transaction_id not in {t.transaction_id for t in retailer_rows}


def test_unknown_bucket_loads_empty(secure_objects: SecureObjectRepository) -> None:
    TransactionCatalogueRepository(bucket_id="marta", objects=secure_objects).save(
        TransactionCatalogue.from_transactions((_tx("marta-1", amount=Decimal("100.00")),)),
    )
    fresh = TransactionCatalogueRepository(bucket_id="never-used", objects=secure_objects).load()
    assert tuple(fresh.values()) == ()
