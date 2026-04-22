"""Unit tests for N26 PDF financial ingestion."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from .. import PdfN26Provider

pytestmark = [pytest.mark.unit, pytest.mark.domain_financial_input]

_FIXTURES = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "financial" / "n26"


def _load_expected(name: str) -> list[dict[str, object]]:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("fixture_name", "expected_name"),
    [
        ("n26-savings-2024-06.pdf", "n26-savings-2024-06.expected.json"),
        ("n26-savings-2025-01.pdf", "n26-savings-2025-01.expected.json"),
        ("n26-savings-2025-05.pdf", "n26-savings-2025-05.expected.json"),
    ],
)
def test_pdf_n26_provider_ingests_fixture_rows(
    fixture_name: str,
    expected_name: str,
) -> None:
    """The provider should emit the manually transcribed rows for each fixture."""
    provider = PdfN26Provider()
    fixture = _FIXTURES / fixture_name
    validation = provider.validate_source(fixture)
    assert validation.is_valid, validation.warnings
    transactions = tuple(provider.ingest(fixture))
    expected_rows = _load_expected(expected_name)
    assert len(transactions) == len(expected_rows)
    for transaction, expected in zip(transactions, expected_rows, strict=True):
        assert transaction.booked_date.isoformat() == expected["booked_date"]
        expected_value_date = expected["value_date"]
        assert (
            transaction.value_date.isoformat() if transaction.value_date is not None else None
        ) == expected_value_date
        assert transaction.amount == Decimal(str(expected["amount"]))
        assert transaction.currency == expected["currency"]
        assert transaction.counterparty == expected["counterparty"]
        assert transaction.description == expected["description"]
        assert transaction.provenance.source_row_index == expected["source_row_index"]
        assert transaction.provenance.source_format.value == "pdf"
        assert transaction.transaction_id.startswith("n26-pdf-")
        assert transaction.transaction_id.endswith(f"-{expected['source_row_index']}")
        assert transaction.raw_fields["statement_period"]
        assert transaction.raw_fields["description_line"]


def test_pdf_n26_provider_rejects_non_n26_pdf(tmp_path: Path) -> None:
    """A generic PDF should not validate as an N26 statement."""
    source = tmp_path / "generic.pdf"
    source.write_bytes((_FIXTURES / "n26-savings-2025-01.pdf").read_bytes().replace(b"N26 Bank AG", b"Other Bank "))
    validation = PdfN26Provider().validate_source(source)
    assert not validation.is_valid
    assert "n26" in validation.warnings[0].lower()
