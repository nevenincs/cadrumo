"""Real-behavior coverage for inbound financial provider dispatch."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.adapters.inbound.financial.ledger_import import FinancialProviderResolverAdapter
from cadrumo.adapters.inbound.financial.providers.csv import CsvProvider
from cadrumo.adapters.inbound.financial.providers.ofx import OfxProvider
from cadrumo.adapters.inbound.financial.providers.pdf_n26 import PdfN26Provider
from cadrumo.adapters.inbound.financial.providers.xlsx import XlsxProvider

pytestmark = [pytest.mark.integration, pytest.mark.hex_inbound_adapter]


@pytest.mark.parametrize(
    ("provider", "expected_type"),
    [
        ("csv", CsvProvider),
        ("ofx", OfxProvider),
        ("qfx", OfxProvider),
        ("xlsx", XlsxProvider),
        ("excel", XlsxProvider),
        ("pdf", PdfN26Provider),
        ("pdf-n26", PdfN26Provider),
    ],
    ids=("csv", "ofx", "qfx", "xlsx", "excel", "pdf", "pdf-n26"),
)
def test_ledger_provider_id_dispatch_resolves_real_provider(provider: str, expected_type: type[object]) -> None:
    """Explicit provider IDs construct the concrete parser owned by this adapter."""

    resolved = FinancialProviderResolverAdapter._resolve_concrete_provider(
        provider_id=provider,
        path=Path("statement.placeholder"),
    )

    assert isinstance(resolved, expected_type)
