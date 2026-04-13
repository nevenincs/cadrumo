"""Unit tests for CSV financial ingestion."""

from __future__ import annotations

from pathlib import Path

import pytest

from aeat.financial import CsvProvider

_FIXTURES = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "financial"


@pytest.mark.unit
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


@pytest.mark.unit
def test_csv_provider_synthesizes_ids_when_source_has_none() -> None:
    """Synthetic CSV rows should receive deterministic synthetic IDs."""
    provider = CsvProvider()
    transactions = tuple(provider.ingest(_FIXTURES / "synthetic-transactions.csv"))
    assert len(transactions) == 2
    assert transactions[0].transaction_id.startswith("bbva-")
    assert transactions[0].provenance.source_row_index == 2


@pytest.mark.unit
def test_csv_provider_rejects_unknown_headers(tmp_path: Path) -> None:
    """Unknown CSV headers should fail validation instead of guessing."""
    source = tmp_path / "unknown.csv"
    source.write_text("foo,bar,baz\n1,2,3\n", encoding="utf-8")
    validation = CsvProvider().validate_source(source)
    assert not validation.is_valid
    assert "headers" in validation.warnings[0].lower()
