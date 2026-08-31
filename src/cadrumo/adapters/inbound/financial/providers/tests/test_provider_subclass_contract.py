from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ......domain.transactions.raw_transaction import SourceFormat
from ..base import FinancialProvider, FinancialProviderConfigError, ParsedLedgerRow, ProviderValidation

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


class _ProviderMethods:
    def ingest(self, path: Path) -> Iterator[ParsedLedgerRow]:
        return iter(())

    def validate_source(self, path: Path) -> ProviderValidation:
        return ProviderValidation(is_valid=True)


def test_missing_verification_source_is_rejected() -> None:
    with pytest.raises(FinancialProviderConfigError, match="verification_source"):

        class MissingVerificationSource(_ProviderMethods, FinancialProvider):
            name = "missing-verification-source"
            supported_extensions = frozenset({".csv"})
            source_format = SourceFormat.CSV
            provisional_pending_specimen = False


def test_no_corpus_without_provisional_status_is_rejected() -> None:
    with pytest.raises(FinancialProviderConfigError, match="no_corpus"):

        class NonProvisionalNoCorpus(_ProviderMethods, FinancialProvider):
            name = "non-provisional-no-corpus"
            supported_extensions = frozenset({".csv"})
            source_format = SourceFormat.CSV
            verification_source = "no_corpus"
            provisional_pending_specimen = False


def test_compliant_provider_is_accepted() -> None:
    class CompliantProvider(_ProviderMethods, FinancialProvider):
        name = "compliant-provider"
        supported_extensions = frozenset({".csv"})
        source_format = SourceFormat.CSV
        verification_source = "no_corpus"
        provisional_pending_specimen = True

    assert CompliantProvider.verification_source == "no_corpus"
    assert CompliantProvider.provisional_pending_specimen is True
