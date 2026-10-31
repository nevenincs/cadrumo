"""One manual-source outgoing ledger row, built the way the persisted rows are."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat


def outgoing_manual_row(
    provider_transaction_id: str,
    *,
    amount: Decimal,
    currency: str,
    counterparty: str,
    description: str,
    classification: BusinessClassification = BusinessClassification.NOT_YET_PROCESSED,
) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id=provider_transaction_id,
        booked_date=date(2026, 3, 1),
        value_date=None,
        amount=amount,
        currency=currency,
        counterparty=counterparty,
        description=description,
        provenance=RawProvenance(
            source_path=Path("x"),
            source_sha256="a" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 3, 1, tzinfo=UTC),
            provider_name="t",
        ),
        raw_fields={},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "business_classification": classification,
            "source_jurisdiction": "ES",
            "group_label": None,
            "created_at": datetime(2026, 3, 1, tzinfo=UTC),
            "modified_at": datetime(2026, 3, 1, tzinfo=UTC),
        },
    )
