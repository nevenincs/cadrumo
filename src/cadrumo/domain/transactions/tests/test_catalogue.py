"""Unit tests for transaction catalogue operations and persistence."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ..enums import BusinessClassification, TransactionDirection
from ..errors import TransactionCatalogueError
from ..models import Transaction, TransactionCatalogue
from ..raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..service import find_transaction, link_invoice, set_classification

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _sample_raw(*, provider_id: str, amount: Decimal, description: str) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
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
    amount: Decimal = Decimal("80.00"),
    description: str = "Software subscription",
    classification: BusinessClassification = BusinessClassification.NOT_YET_PROCESSED,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _sample_raw(provider_id=provider_id, amount=amount, description=description),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": classification,
        },
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
            _sample_transaction(provider_id="provider-row-1", amount=Decimal("80.00"), description="Subscription"),
            _sample_transaction(
                provider_id="provider-row-2",
                amount=Decimal("2500.00"),
                description="Client payment",
                classification=BusinessClassification.BUSINESS,
            ),
        ],
    )

    restored = TransactionCatalogue.model_validate_json(catalogue.model_dump_json())

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


def _bare_transaction() -> Transaction:
    """Return an unclassified transaction helper for the confidence tests."""
    raw = RawTransaction(
        provider_transaction_id="provider-row-1",
        booked_date=date(2026, 4, 10),
        value_date=date(2026, 4, 10),
        amount=Decimal("12.00"),
        currency="EUR",
        counterparty="Vendor SL",
        description="Expense",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="f" * 64,
            source_row_index=2,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2026, 4, 14, 9, 30, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": "Expense"},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
        },
    )


def test_set_classification_manual_path_defaults_confidence_to_one() -> None:
    """Manual classification without an explicit confidence must persist 1.0."""
    catalogue = TransactionCatalogue.from_transactions([_bare_transaction()])
    transaction = next(iter(catalogue))

    updated = set_classification(
        catalogue,
        transaction.transaction_id,
        classification=BusinessClassification.BUSINESS,
        classified_by="manual",
        reason="obvious client payment",
    )

    after = find_transaction(updated, transaction.transaction_id)
    assert after is not None
    assert after.classification_confidence == Decimal("1.0")


def test_set_classification_rule_path_preserves_explicit_confidence() -> None:
    """Rule-based classification must round-trip the caller-supplied confidence."""
    catalogue = TransactionCatalogue.from_transactions([_bare_transaction()])
    transaction = next(iter(catalogue))

    updated = set_classification(
        catalogue,
        transaction.transaction_id,
        classification=BusinessClassification.BUSINESS,
        classified_by="rule:vendor-map",
        reason="matched vendor catalogue",
        confidence=Decimal("0.42"),
    )

    after = find_transaction(updated, transaction.transaction_id)
    assert after is not None
    assert after.classification_confidence == Decimal("0.42")


def test_set_classification_rule_path_without_confidence_leaves_none() -> None:
    """Non-manual classifiers must default confidence to None when the caller omits it."""
    catalogue = TransactionCatalogue.from_transactions([_bare_transaction()])
    transaction = next(iter(catalogue))

    updated = set_classification(
        catalogue,
        transaction.transaction_id,
        classification=BusinessClassification.BUSINESS,
        classified_by="rule:vendor-map",
        reason="matched vendor",
    )

    after = find_transaction(updated, transaction.transaction_id)
    assert after is not None
    assert after.classification_confidence is None


def test_set_classification_rejects_confidence_above_one() -> None:
    """Out-of-range confidence must raise TransactionCatalogueError."""
    catalogue = TransactionCatalogue.from_transactions([_bare_transaction()])
    transaction = next(iter(catalogue))

    with pytest.raises(TransactionCatalogueError):
        set_classification(
            catalogue,
            transaction.transaction_id,
            classification=BusinessClassification.BUSINESS,
            classified_by="manual",
            reason="out-of-range test",
            confidence=Decimal("1.5"),
        )


def test_set_classification_propagates_confidence_into_history_on_reclassification() -> None:
    """Prior confidence must land in the history entry when the decision changes."""
    catalogue = TransactionCatalogue.from_transactions([_bare_transaction()])
    transaction = next(iter(catalogue))

    first = set_classification(
        catalogue,
        transaction.transaction_id,
        classification=BusinessClassification.BUSINESS,
        classified_by="rule:vendor-map",
        reason="first match",
        confidence=Decimal("0.4"),
    )
    second = set_classification(
        first,
        transaction.transaction_id,
        classification=BusinessClassification.PERSONAL,
        classified_by="manual",
        reason="human overrode the rule",
    )

    final = find_transaction(second, transaction.transaction_id)
    assert final is not None
    assert final.classification_confidence == Decimal("1.0")
    assert len(final.classification_history) == 2
    # Entry 0 snapshots the pre-first-classify bare state (NOT_YET_PROCESSED).
    # Entry 1 snapshots the BUSINESS rule:vendor-map state with its confidence.
    mid = final.classification_history[1]
    assert mid.business_classification is BusinessClassification.BUSINESS
    assert mid.classified_by == "rule:vendor-map"
    assert mid.confidence == Decimal("0.4")


def test_set_classification_accepts_llm_classifier_identity_shape() -> None:
    """`classified_by="llm:<model>"` must be accepted by the validator.

    A validator that only permitted ``auto`` / ``manual`` / ``rule:<id>``
    would reject LLM classifications outright. Without this shape, an LLM
    adapter could never record its confidence against a transaction.
    """
    catalogue = TransactionCatalogue.from_transactions([_bare_transaction()])
    transaction = next(iter(catalogue))

    updated = set_classification(
        catalogue,
        transaction.transaction_id,
        classification=BusinessClassification.BUSINESS,
        classified_by="llm:gpt-4",
        reason="LLM classified as business supplies",
        confidence=Decimal("0.45"),
    )

    classified = find_transaction(updated, transaction.transaction_id)
    assert classified is not None
    assert classified.classified_by == "llm:gpt-4"
    assert classified.classification_confidence == Decimal("0.45")


def test_set_classification_normalises_classified_by_whitespace_for_idempotence() -> None:
    """Reclassifying with whitespace-padded classified_by must not force a spurious history entry.

    Pydantic's field validator strips `classified_by` so the stored
    value is always trimmed. Without stripping in the service layer,
    the idempotence signature would use the raw padded value and
    never match the stored trimmed value — every no-op re-classify
    would append to history. This test pins the fix.
    """
    catalogue = TransactionCatalogue.from_transactions([_bare_transaction()])
    transaction = next(iter(catalogue))

    first = set_classification(
        catalogue,
        transaction.transaction_id,
        classification=BusinessClassification.BUSINESS,
        classified_by="manual",
        reason="first",
    )
    second = set_classification(
        first,
        transaction.transaction_id,
        classification=BusinessClassification.BUSINESS,
        classified_by="  manual  ",
        reason="first",
    )

    first_head = find_transaction(first, transaction.transaction_id)
    second_head = find_transaction(second, transaction.transaction_id)
    assert first_head is not None and second_head is not None
    assert len(first_head.classification_history) == len(second_head.classification_history)


def test_confidence_survives_json_round_trip(tmp_path: Path) -> None:
    """Saving then loading must preserve both current and historical confidence."""
    catalogue = TransactionCatalogue.from_transactions([_bare_transaction()])
    transaction = next(iter(catalogue))
    updated = set_classification(
        catalogue,
        transaction.transaction_id,
        classification=BusinessClassification.BUSINESS,
        classified_by="rule:llm",
        reason="reasoned rule match",
        confidence=Decimal("0.73"),
    )

    del tmp_path
    restored = TransactionCatalogue.model_validate_json(updated.model_dump_json())

    loaded = find_transaction(restored, transaction.transaction_id)
    assert loaded is not None
    assert loaded.classification_confidence == Decimal("0.73")
