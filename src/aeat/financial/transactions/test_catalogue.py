"""Unit tests for transaction catalogue operations and persistence."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from aeat.financial import RawProvenance, SourceFormat
from aeat.financial.providers import RawTransaction
from aeat.financial.transactions import (
    BusinessClassification,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
    find_transaction,
    link_invoice,
    load_transactions,
    save_transactions,
    set_classification,
)


def _sample_raw(*, provider_id: str, amount: Decimal, description: str) -> RawTransaction:
    return RawTransaction(
        transaction_id=provider_id,
        booked_date=date(2026, 4, 10),
        value_date=date(2026, 4, 10),
        amount=amount,
        currency="EUR",
        counterparty="Supplier SL",
        description=description,
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="b" * 64,
            source_row_index=7,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2026, 4, 14, 9, 30, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": description},
    )


def _sample_transaction(
    *,
    provider_id: str = "provider-row-1",
    amount: Decimal = Decimal("-80.00"),
    description: str = "Software subscription",
    classification: BusinessClassification = BusinessClassification.UNCLASSIFIED,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _sample_raw(provider_id=provider_id, amount=amount, description=description),
            "direction": TransactionDirection.OUTGOING,
            "business_classification": classification,
        }
    )


@pytest.mark.unit
def test_catalogue_rejects_duplicate_transaction_ids_on_construction() -> None:
    """Duplicate logical IDs must be rejected when building a catalogue."""
    transaction = _sample_transaction()

    with pytest.raises(ValidationError):
        TransactionCatalogue.from_transactions([transaction, transaction])


@pytest.mark.unit
def test_link_invoice_returns_new_catalogue_without_mutating_original() -> None:
    """link_invoice must preserve the original catalogue and raw transaction."""
    transaction = _sample_transaction()
    original = TransactionCatalogue.from_transactions([transaction])

    updated = link_invoice(original, transaction.transaction_id, "INV-001")
    original_transaction = find_transaction(original, transaction.transaction_id)
    assert original_transaction is not None

    assert updated is not original
    assert original_transaction.invoice_id is None
    linked = find_transaction(updated, transaction.transaction_id)
    assert linked is not None
    assert linked.invoice_id == "INV-001"
    assert linked.raw == transaction.raw


@pytest.mark.unit
def test_set_classification_returns_new_catalogue_without_mutating_original() -> None:
    """set_classification must return a fresh catalogue with validated metadata."""
    transaction = _sample_transaction()
    original = TransactionCatalogue.from_transactions([transaction])

    updated = set_classification(
        original,
        transaction.transaction_id,
        classification=BusinessClassification.MIXED,
        business_pct=Decimal("0.5"),
        classified_by="manual",
    )

    before = find_transaction(original, transaction.transaction_id)
    after = find_transaction(updated, transaction.transaction_id)

    assert before is not None and before.business_classification is BusinessClassification.UNCLASSIFIED
    assert after is not None
    assert after.business_classification is BusinessClassification.MIXED
    assert after.business_pct == Decimal("0.5")
    assert after.classified_by == "manual"
    assert after.classified_at is not None
    assert after.classified_at.tzinfo is not None
    assert after.raw == transaction.raw


@pytest.mark.unit
def test_persistence_round_trip_preserves_catalogue(tmp_path: Path) -> None:
    """Saving then loading should round-trip the full catalogue."""
    catalogue = TransactionCatalogue.from_transactions(
        [
            _sample_transaction(provider_id="provider-row-1", amount=Decimal("-80.00"), description="Subscription"),
            _sample_transaction(
                provider_id="provider-row-2",
                amount=Decimal("2500.00"),
                description="Client payment",
                classification=BusinessClassification.BUSINESS,
            ),
        ]
    )

    target = tmp_path / "transactions-round-trip.json"
    try:
        save_transactions(catalogue, target)
        restored = load_transactions(target)
    finally:
        target.unlink(missing_ok=True)

    assert restored == catalogue


@pytest.mark.unit
def test_find_transaction_returns_none_for_missing_transaction() -> None:
    """Missing transactions should yield None rather than raising."""
    catalogue = TransactionCatalogue.from_transactions([_sample_transaction()])

    assert find_transaction(catalogue, "missing-id") is None
