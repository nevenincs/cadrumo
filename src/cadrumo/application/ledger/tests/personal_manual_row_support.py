"""One personal outgoing manual ledger row, shared by the lineage operation suites."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat


def personal_outgoing_manual_row(provider_transaction_id: str, *, amount: Decimal, description: str) -> Transaction:
    """Return a classified personal outgoing manual row whose id derives from the given identity fields."""
    raw = RawTransaction(
        provider_transaction_id=provider_transaction_id,
        booked_date=date(2026, 5, 2),
        value_date=None,
        amount=amount,
        currency="EUR",
        counterparty="Vendor SL",
        description=description,
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
            provider_name="test",
        ),
        raw_fields={"source": "test"},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "business_classification": BusinessClassification.PERSONAL,
            "source_jurisdiction": "ES",
            "group_label": None,
        },
    )
