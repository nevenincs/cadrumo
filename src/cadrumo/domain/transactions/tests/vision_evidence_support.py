"""Domain-owned transaction fixture for vision-evidence tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from ..enums import TransactionDirection
from ..models import Transaction
from ..raw_transaction import RawProvenance, RawTransaction, SourceFormat


def vision_transaction(evidence_id: str) -> Transaction:
    """Build a transaction that addresses one purchase-invoice evidence item."""
    raw = RawTransaction(
        provider_transaction_id="row-vision",
        booked_date=date(2025, 5, 1),
        value_date=date(2025, 5, 1),
        amount=Decimal("121.00"),
        currency="EUR",
        counterparty="Acme SL",
        description="office supplies",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="a" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
            provider_name="manual",
        ),
        raw_fields={"Concepto": "office supplies"},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "purchase_invoice_evidence_id": evidence_id,
        },
    )


__all__ = ["vision_transaction"]
