"""Real-behavior tests for ledger provider ID dispatch coverage.

The ledger import service accepts provider IDs as operator text, normalises them
through :class:`~application.ledger.actions_import.LedgerProviderID`, and then
dispatches to the concrete inbound financial provider implementations. These
tests pin the enum's public strings, alias handling, and unknown-provider
diagnostic surface.

See Also:
    :class:`~application.ledger.actions_import.LedgerProviderID`
        Canonical set of ledger import provider IDs accepted by the service.
    :func:`~application.ledger.actions_import._resolve_financial_provider`
        Resolver that maps provider IDs to concrete parser implementations.
    :mod:`~adapters.inbound.financial.providers`
        Provider package supplying CSV, OFX, XLSX, and N26 PDF parsers.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....adapters.inbound.financial.providers import CsvProvider, OfxProvider, PdfN26Provider, XlsxProvider
from ....domain.transactions import TransactionValidationError
from ..actions_import import LedgerProviderID, _resolve_financial_provider

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_ledger_provider_id_enum_contract() -> None:
    """LedgerProviderID covers every dispatch value and round-trips through StrEnum construction."""
    expected = {"auto", "csv", "ofx", "qfx", "xlsx", "excel", "n26", "pdf", "pdf-n26"}
    actual = {p.value for p in LedgerProviderID}
    assert actual == expected
    for member in LedgerProviderID:
        reconstructed = LedgerProviderID(member.value)
        assert reconstructed is member, f"LedgerProviderID({member.value!r}) did not return the canonical member"


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
    """Explicit provider IDs dispatch through the canonical enum-backed resolver."""

    resolved = _resolve_financial_provider(provider, Path("statement.placeholder"))

    assert isinstance(resolved, expected_type)


def test_ledger_provider_id_dispatch_is_case_and_whitespace_normalised() -> None:
    """Operator input is normalised before enum construction."""

    resolved = _resolve_financial_provider("  CSV  ", Path("statement.csv"))

    assert isinstance(resolved, CsvProvider)


def test_unknown_ledger_provider_reports_known_enum_values() -> None:
    """Unknown provider refusal cites the current enum values."""

    with pytest.raises(TransactionValidationError) as exc_info:
        _resolve_financial_provider("bank-json", Path("statement.json"))

    assert exc_info.value.translated_message == "errors.transaction.unknown_ledger_provider"
    context = exc_info.value.context
    assert context is not None
    assert context["provider"] == "bank-json"
    assert context["providers"] == ", ".join(provider.value for provider in LedgerProviderID)
