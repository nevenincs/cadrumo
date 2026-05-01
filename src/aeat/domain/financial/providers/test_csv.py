"""Unit tests for CSV financial ingestion."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from .. import CsvProvider

pytestmark = [pytest.mark.unit, pytest.mark.domain_financial_input]

_FIXTURES = Path(__file__).resolve().parents[5] / "tests" / "fixtures" / "financial"


@pytest.mark.parametrize(
    ("fixture_name", "expected_currency", "expected_description"),
    [
        ("bbva-sample.csv", "EUR", "Transferencia recibida CLIENTE UNO"),
        ("santander-sample.csv", "EUR", "Pago cuota autonomos"),
        ("caixabank-sample.csv", "EUR", "Cobro factura F-2026-014"),
        ("revolut-sample.csv", "EUR", "Coffee subscription"),
    ],
)
def test_csv_provider_ingests_supported_bank_layouts(
    fixture_name: str,
    expected_currency: str,
    expected_description: str,
) -> None:
    """The CSV provider should ingest each supported bank layout."""
    provider = CsvProvider()
    fixture = _FIXTURES / fixture_name
    validation = provider.validate_source(fixture)
    assert validation.is_valid, validation.warnings
    transactions = tuple(provider.ingest(fixture))
    assert transactions
    assert transactions[0].currency == expected_currency
    assert transactions[0].description == expected_description
    assert transactions[0].provenance.source_format.value == "csv"


def test_csv_provider_synthesizes_ids_when_source_has_none() -> None:
    """Synthetic CSV rows should receive deterministic synthetic IDs."""
    provider = CsvProvider()
    transactions = tuple(provider.ingest(_FIXTURES / "synthetic-transactions.csv"))
    assert len(transactions) == 2
    assert transactions[0].transaction_id.startswith("bbva-")
    assert transactions[0].provenance.source_row_index == 2


def test_csv_provider_rejects_unknown_headers(tmp_path: Path) -> None:
    """Unknown CSV headers should fail validation instead of guessing."""
    source = tmp_path / "unknown.csv"
    source.write_text("foo,bar,baz\n1,2,3\n", encoding="utf-8")
    validation = CsvProvider().validate_source(source)
    assert not validation.is_valid
    assert "headers" in validation.warnings[0].lower()


def test_csv_provider_ignores_invalid_configured_encoding_name() -> None:
    """An invalid preferred encoding should not break the fallback decode order."""
    key = "FINANCIAL_DEFAULT_CSV_ENCODING"
    previous = os.environ.get(key)
    os.environ[key] = "definitely-not-a-codec"
    try:
        validation = CsvProvider().validate_source(_FIXTURES / "bbva-sample.csv")
    finally:
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous
    assert validation.is_valid, validation.warnings
