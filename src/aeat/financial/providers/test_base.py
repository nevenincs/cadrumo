"""Unit tests for financial provider boundary models and detection."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from aeat.financial import ProviderValidation, RawTransaction, SourceFormat, detect_provider
from aeat.financial.providers._base import parse_amount_value

pytestmark = [pytest.mark.unit, pytest.mark.domain_financial_input]

_FIXTURES = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "financial"


def test_raw_transaction_round_trip_uses_mapping_field() -> None:
    """RawTransaction should round-trip through JSON with immutable raw_fields."""
    original = RawTransaction.model_validate(
        {
            "transaction_id": "csv-provider-deadbeef-2",
            "booked_date": date(2026, 4, 10),
            "value_date": date(2026, 4, 10),
            "amount": Decimal("123.45"),
            "currency": "eur",
            "counterparty": "Example SL",
            "description": "Consulting payment",
            "provenance": {
                "source_path": _FIXTURES / "synthetic-transactions.csv",
                "source_sha256": "a" * 64,
                "source_row_index": 2,
                "source_format": SourceFormat.CSV,
                "ingested_at": datetime(2026, 4, 13, 12, 0, tzinfo=UTC),
                "provider_name": "CSV provider",
            },
            "raw_fields": {"Concepto": "Consulting payment"},
        }
    )
    round_tripped = RawTransaction.model_validate_json(original.model_dump_json())
    assert round_tripped == original
    assert round_tripped.currency == "EUR"


def test_provider_validation_defaults() -> None:
    """ProviderValidation should remain a strict frozen boundary record."""
    validation = ProviderValidation(is_valid=True)
    assert validation.warnings == ()
    assert validation.detected_encoding is None
    assert validation.detected_dialect is None


@pytest.mark.parametrize(
    ("fixture_name", "provider_name"),
    [
        ("synthetic-transactions.csv", "CSV provider"),
        ("synthetic-transactions.xlsx", "XLSX provider"),
        ("synthetic-transactions.ofx", "OFX provider"),
    ],
)
def test_detect_provider_uses_extension_and_validation(fixture_name: str, provider_name: str) -> None:
    """detect_provider should select the correct provider for each fixture."""
    provider = detect_provider(_FIXTURES / fixture_name)
    assert provider is not None
    assert provider.name == provider_name


def test_parse_amount_value_respects_explicit_decimal_separator() -> None:
    """Explicit decimal separators should disambiguate locale-specific amounts."""
    assert parse_amount_value("1.234", decimal_separator=",") == Decimal("1234")
    assert parse_amount_value("1,234", decimal_separator=".") == Decimal("1234")
    assert parse_amount_value("1.234,56", decimal_separator=",") == Decimal("1234.56")
    assert parse_amount_value("1,234.56", decimal_separator=".") == Decimal("1234.56")
