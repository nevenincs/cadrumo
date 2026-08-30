"""Scale gate for ``bulk_classify_from_csv``.

The per-row implementation re-encrypted the entire transaction catalogue on
every update, so a 270-row batch cost ~400s of O(n) re-encryption. The
load-once/save-once contract collapses that to a single atomic catalogue write.

The robust regression gate is structural, not wall-clock: a 270-row batch must
persist the catalogue exactly **once**. A generous wall-clock ceiling rides
along as a smoke check, but the save-count assertion is what fails loudly if the
O(n)-save regression ever returns.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....tests.secure_sql import TestRuntimeProfile
from ..actions_classification import bulk_classify_from_csv

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ROW_COUNT = 270
_BUCKET_ID = "18181818-1818-4818-8818-181818181818"


def _raw(idx: int) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=f"provider-row-{idx:04d}",
        booked_date=date(2026, 5, 1),
        value_date=date(2026, 5, 1),
        amount=Decimal("80.00"),
        currency="EUR",
        counterparty="Proveedor SL",
        description=f"Compra material oficina lote {idx}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="d" * 64,
            source_row_index=idx + 1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": f"row {idx}"},
    )


def _unclassified(idx: int) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw(idx),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "business_classification": BusinessClassification.NOT_YET_PROCESSED,
            "source_jurisdiction": "ES",
        },
    )


profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID, autouse=False, name="profile")


def test_bulk_classify_270_rows_persists_catalogue_once(
    profile: TestRuntimeProfile,
    caplog: pytest.LogCaptureFixture,
) -> None:
    objects = profile.repository
    bucket_id = profile.bucket_id

    seed_repo = TransactionCatalogueRepository(bucket_id=bucket_id, objects=objects)
    transactions = tuple(_unclassified(i) for i in range(_ROW_COUNT))
    seed_repo.save(TransactionCatalogue.from_transactions(transactions))

    lines = ["transaction_id,classification,category_id"]
    lines += [f"{txn.transaction_id},BUSINESS,material_oficina" for txn in transactions]
    csv_text = "\n".join(lines) + "\n"

    transaction_repo = TransactionCatalogueRepository(bucket_id=bucket_id, objects=objects)
    event_repo = BucketEventHistoryRepository(objects=objects)

    caplog.clear()
    with caplog.at_level(logging.INFO, logger="cadrumo.adapters.persistence.profile.transactions"):
        start = time.perf_counter()
        result = bulk_classify_from_csv(
            bucket_id=bucket_id,
            csv_text=csv_text,
            actor="operator",
            transaction_repository=transaction_repo,
            bucket_event_repository=event_repo,
        )
    elapsed = time.perf_counter() - start

    # Every row applied, none failed.
    assert result.applied == _ROW_COUNT, result
    assert result.failures == ()
    assert result.skipped == 0

    atomic_save_events = [
        record
        for record in caplog.records
        if record.name == "cadrumo.adapters.persistence.profile.transactions"
        and record.getMessage().startswith("saved transaction catalogue")
    ]
    assert len(atomic_save_events) == 1
    assert f"entries={_ROW_COUNT}" in atomic_save_events[0].getMessage()

    # Smoke ceiling: a single save keeps a 270-row batch well under the prior
    # ~400s O(n) regression. Generous to absorb CI variance.
    assert elapsed < 30.0, f"bulk classify of {_ROW_COUNT} rows took {elapsed:.1f}s"

    # The classifications actually landed.
    reloaded = TransactionCatalogueRepository(bucket_id=bucket_id, objects=objects).load()
    assert all(txn.business_classification is BusinessClassification.BUSINESS for txn in reloaded.values())
