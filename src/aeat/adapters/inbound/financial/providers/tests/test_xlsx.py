"""Unit tests for the XLSX financial ingestion provider.

Verifies :class:`aeat.adapters.inbound.financial.providers.XlsxProvider`
correctly auto-detects the header row of a synthetic worksheet and that
malformed workbooks fail validation cleanly without leaking pikepdf /
openpyxl exceptions.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ......domain.transactions import TransactionDirection
from ......tests import FIXTURES_DIR
from .. import XlsxProvider

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_FIXTURES = FIXTURES_DIR / "financial"


def test_xlsx_provider_ingests_header_detected_worksheet() -> None:
    """XlsxProvider should locate the header row and ingest transactions."""
    provider = XlsxProvider()
    fixture = _FIXTURES / "synthetic-transactions.xlsx"
    validation = provider.validate_source(fixture)
    assert validation.is_valid, validation.warnings
    parsed_rows = tuple(provider.ingest(fixture))
    assert len(parsed_rows) == 2
    assert parsed_rows[0].raw.description == "Cobro factura F-2026-021"
    # The second source row is a debit: magnitude stored, OUTGOING direction.
    assert parsed_rows[1].raw.amount >= 0
    assert parsed_rows[1].direction is TransactionDirection.OUTGOING


def test_xlsx_provider_validation_handles_unopenable_workbook(tmp_path: Path) -> None:
    """Validation should fail cleanly for malformed workbooks without cleanup errors."""
    source = tmp_path / "broken.xlsx"
    source.write_text("not a workbook", encoding="utf-8")
    validation = XlsxProvider().validate_source(source)
    assert not validation.is_valid
    assert "could not open workbook" in validation.warnings[0].lower()
