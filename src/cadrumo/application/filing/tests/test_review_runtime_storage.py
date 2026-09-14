"""Pure transaction-catalogue fingerprint coverage for filing review."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.application.filing.draft_review import _transaction_catalogue_fingerprint
from cadrumo.core.hashing import content_hash_hex
from cadrumo.domain.transactions.enums import TransactionDirection
from cadrumo.domain.transactions.models import Transaction, TransactionCatalogue
from cadrumo.domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_transaction_catalogue_fingerprint_has_core_canonical_digest_parity() -> None:
    transaction = _transaction("canonical")
    catalogue = TransactionCatalogue.from_transactions((transaction,))
    payload = [
        {
            "business_classification": transaction.business_classification.value,
            "business_pct": None,
            "category_id": None,
            "direction": transaction.direction.value,
            "invoice_id": None,
            "transaction_id": transaction.transaction_id,
        },
    ]

    assert _transaction_catalogue_fingerprint(catalogue) == content_hash_hex(payload)


def _transaction(label: str) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id=f"tx-{label}",
        booked_date=date(2026, 4, 5),
        value_date=date(2026, 4, 5),
        amount=Decimal("121.00"),
        currency="EUR",
        counterparty="Proveedor SL",
        description=f"filing review runtime storage {label}",
        provenance=RawProvenance(
            source_path=Path(f"/bank/{label}.csv"),
            source_sha256="a" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2026, 4, 5, 12, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": f"filing review runtime storage {label}"},
    )
    return Transaction.model_validate(
        {"raw": raw, "direction": TransactionDirection.OUTGOING, "group_label": None, "source_jurisdiction": "ES"},
    )
