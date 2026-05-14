"""Unit tests for transaction models and identity semantics."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from aeat.domain.transactions import (
    BusinessClassification,
    ClassificationHistoryEntry,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionDirection,
    TransactionLifecycleState,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _sample_raw(
    *,
    provider_id: str = "provider-row-1",
    value_date: date | None = date(2026, 4, 10),
    amount: Decimal = Decimal("123.45"),
    description: str = "Office rent",
    source_row_index: int = 1,
    counterparty: str | None = "Landlord SL",
) -> RawTransaction:
    return RawTransaction(
        transaction_id=provider_id,
        booked_date=date(2026, 4, 10),
        value_date=value_date,
        amount=amount,
        currency="EUR",
        counterparty=counterparty,
        description=description,
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="a" * 64,
            source_row_index=source_row_index,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2026, 4, 14, 9, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": description},
    )


def test_transaction_id_hash_is_stable_for_same_identity_tuple() -> None:
    """Equal identity tuples must derive the same transaction ID."""
    raw_a = _sample_raw(source_row_index=1, counterparty="First counterparty")
    raw_b = _sample_raw(source_row_index=99, counterparty="Second counterparty")

    tx_a = Transaction.model_validate({"raw": raw_a, "direction": TransactionDirection.OUTGOING})
    tx_b = Transaction.model_validate({"raw": raw_b, "direction": TransactionDirection.OUTGOING})

    assert tx_a.transaction_id == tx_b.transaction_id


def test_direction_enum_round_trips_through_json() -> None:
    """TransactionDirection must survive a JSON round-trip."""
    original = Transaction.model_validate(
        {
            "raw": _sample_raw(),
            "direction": TransactionDirection.INTERNAL_TRANSFER,
        }
    )

    restored = Transaction.model_validate_json(original.model_dump_json())

    assert restored == original
    assert restored.direction is TransactionDirection.INTERNAL_TRANSFER


def test_business_pct_is_only_allowed_for_mixed_transactions() -> None:
    """business_pct must be constrained to MIXED transactions in the 0..1 range."""
    with pytest.raises(ValidationError):
        Transaction(
            transaction_id="x" * 64,
            raw=_sample_raw(),
            direction=TransactionDirection.OUTGOING,
            business_classification=BusinessClassification.BUSINESS,
            business_pct=Decimal("0.2"),
        )

    with pytest.raises(ValidationError):
        Transaction(
            transaction_id="x" * 64,
            raw=_sample_raw(),
            direction=TransactionDirection.OUTGOING,
            business_classification=BusinessClassification.MIXED,
            business_pct=Decimal("1.2"),
        )

    mixed = Transaction.model_validate(
        {
            "raw": _sample_raw(),
            "direction": TransactionDirection.OUTGOING,
            "business_classification": BusinessClassification.MIXED,
            "business_pct": Decimal("0.5"),
        }
    )

    assert mixed.business_pct == Decimal("0.5")


def test_transaction_tax_fields_are_typed_and_round_trip_through_json() -> None:
    """Manual ledger tax fields must be first-class transaction attributes."""

    original = Transaction.model_validate(
        {
            "raw": _sample_raw(),
            "direction": TransactionDirection.OUTGOING,
            "business_classification": BusinessClassification.BUSINESS,
            "category_id": "office-supplies",
            "taxable_base": Decimal("100.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("21.00"),
            "irpf_category": "professional-services",
            "usage_ratio_id": "ratio-office",
            "prorrata_reference": "prorrata-2026",
            "purchase_invoice_evidence_id": "purchase-evidence-1",
            "attachment_ids": ("attachment-1",),
        }
    )

    restored = Transaction.model_validate_json(original.model_dump_json())

    assert restored.taxable_base == Decimal("100.00")
    assert restored.iva_rate == Decimal("0.21")
    assert restored.iva_amount == Decimal("21.00")
    assert restored.irpf_category == "professional-services"
    assert restored.usage_ratio_id == "ratio-office"
    assert restored.prorrata_reference == "prorrata-2026"
    assert restored.purchase_invoice_evidence_id == "purchase-evidence-1"
    assert restored.attachment_ids == ("attachment-1",)


def test_transaction_lineage_fields_are_typed_and_round_trip_through_json() -> None:
    """Evidence provenance and edit lineage must stay on the transaction payload."""

    original = Transaction.model_validate(
        {
            "raw": _sample_raw(),
            "direction": TransactionDirection.OUTGOING,
            "created_by": "operator-A",
            "source_command": "aeat app ledger create",
            "created_event_id": "c" * 64,
            "purchase_invoice_evidence_id": "purchase-evidence-1",
            "attachment_ids": ("a" * 64,),
            "evidence_provenance": (
                {
                    "evidence_id": "purchase-evidence-1",
                    "evidence_kind": "purchase_invoice_evidence",
                    "actor": "operator-A",
                    "source_command": "aeat app ledger create",
                    "linked_at": datetime(2026, 4, 14, 10, 0, tzinfo=UTC),
                    "bucket_event_id": "c" * 64,
                },
            ),
            "edit_lineage": (
                {
                    "previous_transaction_id": "b" * 64,
                    "actor": "operator-B",
                    "source_command": "aeat app ledger edit",
                    "edited_at": datetime(2026, 4, 15, 10, 0, tzinfo=UTC),
                    "bucket_event_id": "d" * 64,
                },
            ),
        }
    )

    restored = Transaction.model_validate_json(original.model_dump_json())

    assert restored.created_by == "operator-A"
    assert restored.source_command == "aeat app ledger create"
    assert restored.created_event_id == "c" * 64
    assert restored.evidence_provenance[0].evidence_kind == "purchase_invoice_evidence"
    assert restored.evidence_provenance[0].actor == "operator-A"
    assert restored.edit_lineage[0].previous_transaction_id == "b" * 64
    assert restored.edit_lineage[0].actor == "operator-B"


def test_transaction_lifecycle_lineage_round_trips_through_json() -> None:
    original = Transaction.model_validate(
        {
            "raw": _sample_raw(),
            "direction": TransactionDirection.OUTGOING,
            "lifecycle_state": TransactionLifecycleState.ARCHIVED,
            "lifecycle_lineage": (
                {
                    "previous_state": TransactionLifecycleState.ACTIVE,
                    "state": TransactionLifecycleState.ARCHIVED,
                    "actor": "operator-A",
                    "source_command": "aeat app ledger archive",
                    "changed_at": datetime(2026, 4, 15, 10, 0, tzinfo=UTC),
                    "reason": "wrong account import",
                    "bucket_event_id": "e" * 64,
                },
            ),
        }
    )

    restored = Transaction.model_validate_json(original.model_dump_json())

    assert restored.lifecycle_state is TransactionLifecycleState.ARCHIVED
    assert restored.lifecycle_lineage[0].previous_state is TransactionLifecycleState.ACTIVE
    assert restored.lifecycle_lineage[0].state is TransactionLifecycleState.ARCHIVED
    assert restored.lifecycle_lineage[0].reason == "wrong account import"
    assert restored.lifecycle_lineage[0].bucket_event_id == "e" * 64


def test_transaction_lifecycle_lineage_rejects_noop_transition() -> None:
    with pytest.raises(ValidationError, match="lifecycle transition must change state"):
        Transaction.model_validate(
            {
                "raw": _sample_raw(),
                "direction": TransactionDirection.OUTGOING,
                "lifecycle_state": TransactionLifecycleState.ACTIVE,
                "lifecycle_lineage": (
                    {
                        "previous_state": TransactionLifecycleState.ACTIVE,
                        "state": TransactionLifecycleState.ACTIVE,
                        "actor": "operator-A",
                        "source_command": "aeat app ledger archive",
                        "changed_at": datetime(2026, 4, 15, 10, 0, tzinfo=UTC),
                    },
                ),
            }
        )


def test_transaction_tax_fields_reject_negative_values_and_legacy_multi_purchase_evidence() -> None:
    """Tax substrate values and evidence refs must fail at the domain boundary."""

    with pytest.raises(ValidationError):
        Transaction.model_validate(
            {
                "raw": _sample_raw(),
                "direction": TransactionDirection.OUTGOING,
                "taxable_base": Decimal("-1.00"),
            }
        )

    with pytest.raises(ValidationError):
        Transaction.model_validate(
            {
                "raw": _sample_raw(),
                "direction": TransactionDirection.OUTGOING,
                "purchase_invoice_evidence_id": ("evidence-1", "evidence-2"),
            }
        )


def test_classified_by_accepts_only_whitelisted_shapes() -> None:
    """classified_by must be auto, manual, or rule:<rule-id>."""
    auto = Transaction.model_validate(
        {"raw": _sample_raw(), "direction": TransactionDirection.INCOMING, "classified_by": "auto"}
    )
    manual = Transaction.model_validate(
        {"raw": _sample_raw(), "direction": TransactionDirection.INCOMING, "classified_by": "manual"}
    )
    rule = Transaction.model_validate(
        {"raw": _sample_raw(), "direction": TransactionDirection.INCOMING, "classified_by": "rule:vendor-map"}
    )

    assert auto.classified_by == "auto"
    assert manual.classified_by == "manual"
    assert rule.classified_by == "rule:vendor-map"

    with pytest.raises(ValidationError):
        Transaction.model_validate(
            {"raw": _sample_raw(), "direction": TransactionDirection.INCOMING, "classified_by": "rule:"}
        )

    with pytest.raises(ValidationError):
        Transaction.model_validate(
            {"raw": _sample_raw(), "direction": TransactionDirection.INCOMING, "classified_by": "bot"}
        )


def test_business_classification_rejects_unclassified_literal() -> None:
    """`BusinessClassification("UNCLASSIFIED")` must raise."""
    with pytest.raises(ValueError):
        BusinessClassification("UNCLASSIFIED")


def test_classification_history_entry_round_trips_through_json() -> None:
    """`ClassificationHistoryEntry` must survive JSON round-trip with reserved slots."""
    entry = ClassificationHistoryEntry(
        business_classification=BusinessClassification.BUSINESS,
        classified_at=datetime(2026, 4, 18, 9, 0, tzinfo=UTC),
        classified_by="manual",
        reason="client invoice",
    )
    restored = ClassificationHistoryEntry.model_validate_json(entry.model_dump_json())
    assert restored == entry
    assert restored.confidence is None
    assert restored.provenance is None
