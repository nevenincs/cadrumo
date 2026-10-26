"""Real-behavior coverage for inbound financial provider dispatch."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.adapters.inbound.financial.ledger_import import FinancialProviderResolverAdapter
from cadrumo.adapters.inbound.financial.providers.csv import CsvProvider
from cadrumo.adapters.inbound.financial.providers.ofx import OfxProvider
from cadrumo.adapters.inbound.financial.providers.pdf_statement import PdfStatementProvider
from cadrumo.adapters.inbound.financial.providers.xls import XlsProvider
from cadrumo.adapters.inbound.financial.providers.xlsx import XlsxProvider
from cadrumo.domain.transactions.errors import TransactionValidationError

pytestmark = [pytest.mark.integration, pytest.mark.hex_inbound_adapter]


@pytest.mark.parametrize(
    ("provider", "expected_type"),
    [
        ("csv", CsvProvider),
        ("ofx", OfxProvider),
        ("qfx", OfxProvider),
        ("xlsx", XlsxProvider),
        ("xls", XlsProvider),
        ("pdf", PdfStatementProvider),
    ],
    ids=("csv", "ofx", "qfx", "xlsx", "xls", "pdf"),
)
def test_ledger_provider_id_dispatch_resolves_real_provider(provider: str, expected_type: type[object]) -> None:
    """Explicit provider IDs construct the concrete parser owned by this adapter."""

    resolved = FinancialProviderResolverAdapter._resolve_concrete_provider(
        provider_id=provider,
        path=Path("statement.placeholder"),
    )

    assert isinstance(resolved, expected_type)


@pytest.mark.parametrize("provider", ["n26", "pdf-n26", "excel"])
def test_ledger_provider_id_dispatch_refuses_tokens_that_name_no_parser(provider: str) -> None:
    """A token that would silently run detection or a different parser is refused."""

    with pytest.raises(TransactionValidationError):
        FinancialProviderResolverAdapter._resolve_concrete_provider(
            provider_id=provider,
            path=Path("statement.placeholder"),
        )
