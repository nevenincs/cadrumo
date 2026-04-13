"""Unit tests for OFX financial ingestion."""

from __future__ import annotations

from pathlib import Path

import pytest

from aeat.financial import OfxProvider

_FIXTURES = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "financial"


@pytest.mark.unit
def test_ofx_provider_prefers_fitid_and_payee() -> None:
    """OfxProvider should preserve FITID and payee-derived description."""
    provider = OfxProvider()
    fixture = _FIXTURES / "synthetic-transactions.ofx"
    validation = provider.validate_source(fixture)
    assert validation.is_valid, validation.warnings
    transactions = tuple(provider.ingest(fixture))
    assert len(transactions) == 2
    assert transactions[0].transaction_id == "FIT-001"
    assert transactions[0].counterparty == "CLIENTE DOS"
    assert transactions[1].amount < 0
