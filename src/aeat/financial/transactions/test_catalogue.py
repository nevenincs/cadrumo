"""Unit tests for transaction catalogue operations and persistence."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from .. import RawProvenance, SourceFormat
from ..providers import RawTransaction
from . import (
    BusinessClassification,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueError,
    TransactionDirection,
    find_transaction,
    link_invoice,
    load_transactions,
    save_transactions,
    set_classification,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_financial_input]


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
    classification: BusinessClassification = BusinessClassification.NOT_YET_PROCESSED,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _sample_raw(provider_id=provider_id, amount=amount, description=description),
            "direction": TransactionDirection.OUTGOING,
            "business_classification": classification,
        }
    )


def test_catalogue_rejects_duplicate_transaction_ids_on_construction() -> None:
    """Duplicate logical IDs must be rejected when building a catalogue."""
    transaction = _sample_transaction()

    with pytest.raises(ValidationError):
        TransactionCatalogue.from_transactions([transaction, transaction])


def test_catalogue_iteration_yields_transactions() -> None:
    """TransactionCatalogue iteration must expose transactions, not model fields."""
    first = _sample_transaction(provider_id="provider-row-1")
    second = _sample_transaction(provider_id="provider-row-2", description="Client payment")
    catalogue = TransactionCatalogue.from_transactions([first, second])

    assert [transaction.transaction_id for transaction in catalogue] == [
        first.transaction_id,
        second.transaction_id,
    ]


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


def test_link_invoice_rejects_blank_invoice_identifier() -> None:
    """link_invoice must reject blank invoice IDs instead of clearing the link."""
    transaction = _sample_transaction()
    catalogue = TransactionCatalogue.from_transactions([transaction])

    with pytest.raises(TransactionCatalogueError):
        link_invoice(catalogue, transaction.transaction_id, "   ")


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

    assert before is not None and before.business_classification is BusinessClassification.NOT_YET_PROCESSED
    assert after is not None
    assert after.business_classification is BusinessClassification.MIXED
    assert after.business_pct == Decimal("0.5")
    assert after.classified_by == "manual"
    assert after.classified_at is not None
    assert after.classified_at.tzinfo is not None
    assert after.raw == transaction.raw


def test_set_classification_raises_typed_error_for_invalid_business_pct() -> None:
    """set_classification must not leak raw pydantic errors to callers."""
    transaction = _sample_transaction()
    catalogue = TransactionCatalogue.from_transactions([transaction])

    with pytest.raises(TransactionCatalogueError):
        set_classification(
            catalogue,
            transaction.transaction_id,
            classification=BusinessClassification.BUSINESS,
            business_pct=Decimal("0.5"),
            classified_by="manual",
        )


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


def test_find_transaction_returns_none_for_missing_transaction() -> None:
    """Missing transactions should yield None rather than raising."""
    catalogue = TransactionCatalogue.from_transactions([_sample_transaction()])

    assert find_transaction(catalogue, "missing-id") is None


def test_set_classification_appends_one_history_entry_on_first_transition() -> None:
    """The very first `set_classification` call should seed the history chain."""
    transaction = _sample_transaction()
    catalogue = TransactionCatalogue.from_transactions([transaction])

    updated = set_classification(
        catalogue,
        transaction.transaction_id,
        classification=BusinessClassification.BUSINESS,
        classified_by="manual",
    )
    result = find_transaction(updated, transaction.transaction_id)
    assert result is not None
    assert len(result.classification_history) == 1
    head = result.classification_history[0]
    assert head.business_classification is BusinessClassification.NOT_YET_PROCESSED
    assert head.classified_by == "auto"
    assert result.business_classification is BusinessClassification.BUSINESS


def test_set_classification_does_not_append_when_signature_is_byte_identical() -> None:
    """Idempotent re-classifies (same state / pct / classified_by / reason) must not append."""
    transaction = _sample_transaction()
    catalogue = TransactionCatalogue.from_transactions([transaction])

    once = set_classification(
        catalogue,
        transaction.transaction_id,
        classification=BusinessClassification.BUSINESS,
        classified_by="manual",
        reason="client invoice",
    )
    twice = set_classification(
        once,
        transaction.transaction_id,
        classification=BusinessClassification.BUSINESS,
        classified_by="manual",
        reason="client invoice",
    )
    first_result = find_transaction(once, transaction.transaction_id)
    second_result = find_transaction(twice, transaction.transaction_id)
    assert first_result is not None
    assert second_result is not None
    assert len(first_result.classification_history) == len(second_result.classification_history)


def test_set_classification_appends_when_only_reason_changes() -> None:
    """Changing only `reason` is a meaningful transition and must append."""
    transaction = _sample_transaction()
    catalogue = TransactionCatalogue.from_transactions([transaction])

    once = set_classification(
        catalogue,
        transaction.transaction_id,
        classification=BusinessClassification.BUSINESS,
        classified_by="manual",
        reason="initial",
    )
    twice = set_classification(
        once,
        transaction.transaction_id,
        classification=BusinessClassification.BUSINESS,
        classified_by="manual",
        reason="revised after review",
    )
    result = find_transaction(twice, transaction.transaction_id)
    assert result is not None
    assert len(result.classification_history) == 2
    assert result.classification_history[-1].reason == "initial"


def test_set_classification_skips_append_on_pure_timestamp_drift() -> None:
    """`classified_at` differences alone must not trigger a history append."""
    transaction = _sample_transaction()
    catalogue = TransactionCatalogue.from_transactions([transaction])

    once = set_classification(
        catalogue,
        transaction.transaction_id,
        classification=BusinessClassification.BUSINESS,
        classified_by="manual",
    )
    twice = set_classification(
        once,
        transaction.transaction_id,
        classification=BusinessClassification.BUSINESS,
        classified_by="manual",
    )
    first_result = find_transaction(once, transaction.transaction_id)
    second_result = find_transaction(twice, transaction.transaction_id)
    assert first_result is not None
    assert second_result is not None
    assert first_result.classified_at is not None
    assert second_result.classified_at is not None
    assert len(first_result.classification_history) == len(second_result.classification_history)


def test_legacy_unclassified_payload_loads_as_not_yet_processed(tmp_path: Path) -> None:
    """Pre-#237 catalogue JSON with `"UNCLASSIFIED"` must load transparently."""
    raw = _sample_raw(provider_id="legacy-row-1", amount=Decimal("-10.00"), description="Legacy row")
    transaction = Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "business_classification": BusinessClassification.BUSINESS,
        }
    )
    catalogue = TransactionCatalogue.from_transactions([transaction])
    target = tmp_path / "legacy-transactions.json"
    save_transactions(catalogue, target)

    # Hand-rewrite the on-disk payload so the classification field carries
    # the legacy literal.
    contents = target.read_text(encoding="utf-8")
    contents = contents.replace('"business_classification": "BUSINESS"', '"business_classification": "UNCLASSIFIED"')
    target.write_text(contents, encoding="utf-8")

    restored = load_transactions(target)
    legacy = find_transaction(restored, transaction.transaction_id)
    assert legacy is not None
    assert legacy.business_classification is BusinessClassification.NOT_YET_PROCESSED
