"""Profile-persistence integration coverage for structural IVA routing advisories."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from cadrumo.application.aggregation.tests.unroutable_iva_base_support import domestic_general_sale, domestic_zero_sale

from .....application.aggregation.modelo_bindings_iva import LedgerIvaAggregationSourceResolver
from .....application.aggregation.source_mesh import CalculationSourceContext
from .....application.invoices.catalogue_reads_ports import InvoiceCatalogueReadPorts
from .....core.period import Period
from .....domain.bienes_inversion.register import BienesInversionIvaRegister
from .....domain.calculations.registry.schema import ModeloRevision
from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .....domain.invoices.catalogue import InvoiceCatalogue
from .....domain.transactions.date_partition import LedgerDatePartition
from .....domain.transactions.models import TransactionCatalogue
from ...storage.tests.secure_sql import isolated_runtime_profile
from ..prorrata_register import ProrrataRegisterRepository
from ..transactions import TransactionCatalogueRepository
from .published_authority_support import published_authority_operation

_YEAR = filing_year_envelope().horizon

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_Q1 = Period.from_year_and_code(_YEAR, "1T")
_BUCKET_ID = "38383838-3838-4838-8838-383838383838"


class _EmptyInvoiceCatalogueReader:
    def __init__(self, catalogue: InvoiceCatalogue) -> None:
        self._catalogue = catalogue

    def load(self) -> InvoiceCatalogue:
        return self._catalogue


class _EmptyTransactionCatalogueReader:
    def __init__(self, catalogue: TransactionCatalogue) -> None:
        self._catalogue = catalogue

    def load(self) -> TransactionCatalogue:
        return self._catalogue

    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        return LedgerDatePartition(in_window=self._catalogue, index_complete=True)


def _catalogue_read_ports(
    *,
    invoices: InvoiceCatalogue,
    transactions: TransactionCatalogue,
) -> InvoiceCatalogueReadPorts:
    return InvoiceCatalogueReadPorts(
        invoice_reader=_EmptyInvoiceCatalogueReader(invoices),
        transaction_reader=_EmptyTransactionCatalogueReader(transactions),
    )


def _m303_revision() -> ModeloRevision:
    return published_authority_operation().snapshot("303", filing_year=_Q1.filing_year, period="1T").revision


def _resolve_q1_2025(repository: TransactionCatalogueRepository):
    """Resolve the first-quarter 2025 IVA ledger sources over ``repository`` with no invoices or investment assets."""
    return LedgerIvaAggregationSourceResolver(
        transaction_repository=repository,
        invoice_catalogue_read_ports=_catalogue_read_ports(
            invoices=InvoiceCatalogue(),
            transactions=TransactionCatalogue(),
        ),
        prorrata_register_repository=ProrrataRegisterRepository(bucket_id=_BUCKET_ID),
        investment_asset_register=BienesInversionIvaRegister(),
        investment_asset_profile_id=_BUCKET_ID,
    ).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="303",
            filing_year=_YEAR,
            period=_Q1,
            revision=_m303_revision(),
        ),
    )


def test_the_advisory_fires_live_for_a_present_unroutable_category(tmp_path: Path) -> None:
    """Positive control end to end: live wiring, scoped to this ledger's own categories."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository)
        repository.save(TransactionCatalogue.from_transactions((domestic_zero_sale(),)))
        resolution = _resolve_q1_2025(repository)

    advisories = [
        diagnostic
        for diagnostic in resolution.diagnostics
        if diagnostic.reason == "structurally_unroutable_base_category"
    ]
    assert len(advisories) == 1, "the live domestic_zero residue must surface exactly one advisory"
    message = advisories[0].message
    assert "domestic_zero" in message
    assert "no tax is lost" in message


def test_the_advisory_stays_silent_when_the_category_never_appears(tmp_path: Path) -> None:
    """Negative control: an unroutable category not present in this ledger must not fire."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository)
        repository.save(TransactionCatalogue.from_transactions((domestic_general_sale(),)))
        resolution = _resolve_q1_2025(repository)

    assert not [
        diagnostic
        for diagnostic in resolution.diagnostics
        if diagnostic.reason == "structurally_unroutable_base_category"
    ]
