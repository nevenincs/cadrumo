"""Unit tests for XLSX financial ingestion."""

from __future__ import annotations

from pathlib import Path

import pytest

from .. import XlsxProvider

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_FIXTURES = Path(__file__).resolve().parents[5] / "tests" / "fixtures" / "financial"


def test_xlsx_provider_ingests_header_detected_worksheet() -> None:
    """XlsxProvider should locate the header row and ingest transactions."""
    provider = XlsxProvider()
    fixture = _FIXTURES / "synthetic-transactions.xlsx"
    validation = provider.validate_source(fixture)
    assert validation.is_valid, validation.warnings
    transactions = tuple(provider.ingest(fixture))
    assert len(transactions) == 2
    assert transactions[0].description == "Cobro factura F-2026-021"
    assert transactions[1].amount < 0


def test_xlsx_provider_validation_handles_unopenable_workbook(tmp_path: Path) -> None:
    """Validation should fail cleanly for malformed workbooks without cleanup errors."""
    source = tmp_path / "broken.xlsx"
    source.write_text("not a workbook", encoding="utf-8")
    validation = XlsxProvider().validate_source(source)
    assert not validation.is_valid
    assert "could not open workbook" in validation.warnings[0].lower()
