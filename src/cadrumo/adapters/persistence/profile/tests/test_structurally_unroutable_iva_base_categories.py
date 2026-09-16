"""Profile-persistence integration coverage for structural IVA routing advisories."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from .....application.aggregation.modelo_bindings import LedgerIvaAggregationSourceResolver
from .....application.aggregation.source_mesh import CalculationSourceContext
from .....application.invoices.catalogue_reads_ports import InvoiceCatalogueReadPorts
from .....core.period import Period
from .....domain.bienes_inversion.register import BienesInversionIvaRegister
from .....domain.calculations.registry.schema import ModeloRevision
from .....domain.invoices.models import InvoiceCatalogue
from .....domain.iva.schema import IvaCategory
from .....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from .....domain.transactions.models import LedgerDatePartition, Transaction, TransactionCatalogue
from .....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ...storage.tests.secure_sql import isolated_runtime_profile
from ..prorrata_register import ProrrataRegisterRepository
from ..transactions import TransactionCatalogueRepository
from .published_authority_support import published_authority_operation

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_NOW = datetime(2025, 2, 10, 12, 0, tzinfo=UTC)
_Q1_2025 = Period.from_year_and_code(2025, "1T")
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
    return published_authority_operation().snapshot("303", filing_year=_Q1_2025.filing_year, period="1T").revision


def _domestic_zero_sale() -> Transaction:
    """A zero-rated domestic sale: zero cuota by law, a real base by law."""
    raw = RawTransaction(
        provider_transaction_id="zero-rated-1",
        booked_date=date(2025, 2, 10),
        value_date=date(2025, 2, 10),
        amount=Decimal("500.00"),
        currency="EUR",
        counterparty="Comprador Nacional SL",
        description="venta tipo cero",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_NOW,
            provider_name="manual",
        ),
        raw_fields={"row": "zero-rated-1"},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": Decimal("500.00"),
            "iva_rate": Decimal("0.00"),
            "iva_amount": Decimal("0.00"),
            "iva_category": IvaCategory("domestic_zero"),
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": _NOW,
            "classified_by": "manual",
        },
    )


def _domestic_general_sale() -> Transaction:
    """A fully-covered domestic sale, the negative control."""
    raw = RawTransaction(
        provider_transaction_id="general-1",
        booked_date=date(2025, 2, 10),
        value_date=date(2025, 2, 10),
        amount=Decimal("1210.00"),
        currency="EUR",
        counterparty="Comprador Nacional SL",
        description="venta tipo general",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="f" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_NOW,
            provider_name="manual",
        ),
        raw_fields={"row": "general-1"},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": Decimal("1000.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("210.00"),
            "iva_category": IvaCategory("domestic_general"),
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": _NOW,
            "classified_by": "manual",
        },
    )


def test_the_advisory_fires_live_for_a_present_unroutable_category(tmp_path: Path) -> None:
    """Positive control end to end: live wiring, scoped to this ledger's own categories."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository)
        repository.save(TransactionCatalogue.from_transactions((_domestic_zero_sale(),)))
        resolution = LedgerIvaAggregationSourceResolver(
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
                filing_year=2025,
                period=_Q1_2025,
                revision=_m303_revision(),
            ),
        )

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
        repository.save(TransactionCatalogue.from_transactions((_domestic_general_sale(),)))
        resolution = LedgerIvaAggregationSourceResolver(
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
                filing_year=2025,
                period=_Q1_2025,
                revision=_m303_revision(),
            ),
        )

    assert not [
        diagnostic
        for diagnostic in resolution.diagnostics
        if diagnostic.reason == "structurally_unroutable_base_category"
    ]
