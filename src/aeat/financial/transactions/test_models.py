"""Unit tests for transaction models and identity semantics."""

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
    TransactionDirection,
)


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


@pytest.mark.unit
def test_transaction_id_hash_is_stable_for_same_identity_tuple() -> None:
    """Equal identity tuples must derive the same transaction ID."""
    raw_a = _sample_raw(source_row_index=1, counterparty="First counterparty")
    raw_b = _sample_raw(source_row_index=99, counterparty="Second counterparty")

    tx_a = Transaction.model_validate({"raw": raw_a, "direction": TransactionDirection.OUTGOING})
    tx_b = Transaction.model_validate({"raw": raw_b, "direction": TransactionDirection.OUTGOING})

    assert tx_a.transaction_id == tx_b.transaction_id


@pytest.mark.unit
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


@pytest.mark.unit
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


@pytest.mark.unit
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
