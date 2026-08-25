"""Manual ledger transaction result and public constant contracts."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.external_constants import CLASSIFIED_BY_MANUAL
from ....core.external_constants import CLASSIFIED_BY_MANUAL as _CLASSIFIED_BY_MANUAL_FROM_CORE
from ....domain.transactions import (
    BucketTransactionRef,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionDirection,
)
from ..models import ManualLedgerTransactionResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "21212121-2121-4121-8121-212121212121"


def test_manual_ledger_transaction_result_requires_matching_strict_shapes() -> None:
    raw = RawTransaction(
        provider_transaction_id="manual-row-1",
        booked_date=date(2026, 5, 1),
        value_date=date(2026, 5, 1),
        amount=Decimal("121.00"),
        currency="EUR",
        counterparty="Proveedor SL",
        description="manual ledger row",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
            provider_name="manual",
        ),
        raw_fields={"source": "manual"},
    )
    transaction = Transaction.model_validate(
        {"raw": raw, "direction": TransactionDirection.OUTGOING, "group_label": None, "source_jurisdiction": "ES"},
    )
    result = ManualLedgerTransactionResult(
        ref=BucketTransactionRef(bucket_id=_BUCKET_ID, transaction_id=transaction.transaction_id),
        transaction=transaction,
        bucket_event_ids=("event-1",),
    )

    assert result.ref.bucket_id == _BUCKET_ID
    assert result.ref.transaction_id == transaction.transaction_id
    assert result.transaction.raw.provenance.source_format is SourceFormat.MANUAL
    assert result.bucket_event_ids == ("event-1",)


def test_classified_by_manual_constant_is_core_export() -> None:
    assert CLASSIFIED_BY_MANUAL == "manual"
    assert CLASSIFIED_BY_MANUAL is _CLASSIFIED_BY_MANUAL_FROM_CORE
