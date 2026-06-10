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

import time
from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import override

import pytest

from ....adapters.persistence.storage import SecureObjectRepository, SecureObjectWrite
from ....domain.buckets import BucketEventHistoryRepository
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionDirection,
)
from ....tests.secure_sql import isolated_runtime_profile
from .. import bulk_classify_from_csv

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ROW_COUNT = 270


class _CountingTxRepo(TransactionCatalogueRepository):
    """Real repository that counts the single atomic catalogue persist."""

    def __init__(self, *, bucket_id: str, objects: SecureObjectRepository | None = None) -> None:
        super().__init__(bucket_id=bucket_id, objects=objects)
        self.save_calls = 0

    @override
    def save_with_secure_object_writes(
        self,
        catalogue: TransactionCatalogue,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        self.save_calls += 1
        return super().save_with_secure_object_writes(catalogue, extra_writes)


def _raw(idx: int) -> RawTransaction:
    return RawTransaction(
        transaction_id=f"provider-row-{idx:04d}",
        booked_date=date(2026, 5, 1),
        value_date=date(2026, 5, 1),
        amount=Decimal("-80.00"),
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
            "business_classification": BusinessClassification.NOT_YET_PROCESSED,
        }
    )


@pytest.fixture
def _profile(tmp_path: Path) -> Iterator[object]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="bucket-a") as profile:
        yield profile


def test_bulk_classify_270_rows_persists_catalogue_once(_profile: object) -> None:
    assert hasattr(_profile, "repository") and hasattr(_profile, "bucket_id")
    objects_raw = _profile.repository  # type: ignore[union-attr]
    bucket_id_raw = _profile.bucket_id  # type: ignore[union-attr]

    assert isinstance(bucket_id_raw, str)
    assert isinstance(objects_raw, (SecureObjectRepository, type(None)))
    objects = objects_raw
    bucket_id = bucket_id_raw

    seed_repo = TransactionCatalogueRepository(bucket_id=bucket_id, objects=objects)
    transactions = tuple(_unclassified(i) for i in range(_ROW_COUNT))
    seed_repo.save(TransactionCatalogue.from_transactions(transactions))

    lines = ["transaction_id,classification,category_id"]
    lines += [f"{txn.transaction_id},BUSINESS,material_oficina" for txn in transactions]
    csv_text = "\n".join(lines) + "\n"

    counting_repo = _CountingTxRepo(bucket_id=bucket_id, objects=objects)
    event_repo = BucketEventHistoryRepository(objects=objects)

    start = time.perf_counter()
    result = bulk_classify_from_csv(
        bucket_id=bucket_id,
        csv_text=csv_text,
        actor="operator",
        transaction_repository=counting_repo,
        bucket_event_repository=event_repo,
    )
    elapsed = time.perf_counter() - start

    # Every row applied, none failed.
    assert result.applied == _ROW_COUNT, result
    assert result.failures == ()
    assert result.skipped == 0

    # The load-once/save-once contract: one atomic catalogue persist for the
    # whole batch, NOT one per row.
    assert counting_repo.save_calls == 1, counting_repo.save_calls

    # Smoke ceiling: a single save keeps a 270-row batch well under the prior
    # ~400s O(n) regression. Generous to absorb CI variance.
    assert elapsed < 30.0, f"bulk classify of {_ROW_COUNT} rows took {elapsed:.1f}s"

    # The classifications actually landed.
    reloaded = TransactionCatalogueRepository(bucket_id=bucket_id, objects=objects).load()
    assert all(txn.business_classification is BusinessClassification.BUSINESS for txn in reloaded.values())
