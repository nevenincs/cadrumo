"""Application-owned provider-ID normalization and refusal contracts."""

from __future__ import annotations

from pathlib import Path

import pytest

from ....domain.transactions.errors import TransactionValidationError
from ..actions_import import LedgerProviderID, _resolve_financial_provider
from ..import_ports import LedgerImportPorts

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _ProviderResolverFake:
    """Record normalized IDs without constructing a concrete parser."""

    def __init__(self, result: object | None = object()) -> None:
        self.result = result
        self.provider_ids: list[str] = []

    def resolve(self, *, provider_id: str, path: Path) -> object | None:
        del path
        self.provider_ids.append(provider_id)
        return self.result


class _CatalogueLocationFake:
    def path_for(self, *, bucket_id: str) -> str:
        return f"fake://{bucket_id}"


def _ports(resolver: _ProviderResolverFake) -> LedgerImportPorts:
    return LedgerImportPorts(
        provider_resolver=resolver,
        catalogue_location=_CatalogueLocationFake(),
    )


def test_ledger_provider_id_enum_contract() -> None:
    """LedgerProviderID covers every operator-facing dispatch value."""
    expected = {"auto", "csv", "ofx", "qfx", "xlsx", "excel", "n26", "pdf", "pdf-n26"}
    actual = {provider.value for provider in LedgerProviderID}
    assert actual == expected
    for member in LedgerProviderID:
        reconstructed = LedgerProviderID(member.value)
        assert reconstructed is member


def test_ledger_provider_id_dispatch_is_case_and_whitespace_normalised() -> None:
    """Application input normalization precedes the provider capability."""
    resolver = _ProviderResolverFake()

    resolved = _resolve_financial_provider("  CSV  ", Path("statement.csv"), ports=_ports(resolver))

    assert resolved is resolver.result
    assert resolver.provider_ids == ["csv"]


def test_unknown_ledger_provider_reports_known_enum_values() -> None:
    """Unknown provider refusal cites the complete application enum."""
    resolver = _ProviderResolverFake(result=None)

    with pytest.raises(TransactionValidationError) as exc_info:
        _resolve_financial_provider("bank-json", Path("statement.json"), ports=_ports(resolver))

    assert exc_info.value.translated_message == "errors.transaction.unknown_ledger_provider"
    context = exc_info.value.context
    assert context is not None
    assert context["provider"] == "bank-json"
    assert context["providers"] == ", ".join(provider.value for provider in LedgerProviderID)
