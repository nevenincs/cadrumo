"""Profile-persistence integration coverage for the IVA quantity screen."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.modelo_bindings import LedgerIvaAggregationSourceResolver
from cadrumo.application.aggregation.source_mesh import CalculationSourceContext
from cadrumo.application.invoices.catalogue_reads_ports import InvoiceCatalogueReadPorts
from cadrumo.core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from cadrumo.core.period import Period
from cadrumo.domain.bienes_inversion.register import BienesInversionIvaRegister
from cadrumo.domain.calculations.registry.authority import bundled_authority
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.invoices.models import InvoiceCatalogue
from cadrumo.domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from cadrumo.domain.iva.schema import IvaCategory
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from cadrumo.domain.transactions.models import LedgerDatePartition, Transaction, TransactionCatalogue
from cadrumo.domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_NOW = datetime(2025, 2, 10, 12, 0, tzinfo=UTC)
_Q1_2025 = Period.from_year_and_code(2025, "1T")
_BUCKET_ID = "28282828-2828-4828-8828-282828282828"


class _EmptyInvoiceCatalogueReader:
    def load(self) -> InvoiceCatalogue:
        return InvoiceCatalogue()


class _EmptyTransactionCatalogueReader:
    def load(self) -> TransactionCatalogue:
        return TransactionCatalogue()

    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        return LedgerDatePartition(in_window=TransactionCatalogue(), index_complete=True)


def _resolver(repository: TransactionCatalogueRepository) -> LedgerIvaAggregationSourceResolver:
    return LedgerIvaAggregationSourceResolver(
        transaction_repository=repository,
        invoice_catalogue_read_ports=InvoiceCatalogueReadPorts(
            invoice_reader=_EmptyInvoiceCatalogueReader(),
            transaction_reader=_EmptyTransactionCatalogueReader(),
        ),
        prorrata_register_repository=ProrrataRegisterRepository(bucket_id=repository.bucket_id),
        investment_asset_register=BienesInversionIvaRegister(),
        investment_asset_profile_id=repository.bucket_id,
    )


@cache
def _revision(modelo_id: str) -> ModeloRevision:
    """The committed revision governing each modelo's IVA ledger bindings."""
    period = "1T" if modelo_id == "303" else "0A"
    return bundled_authority().snapshot(modelo_id, filing_year=_Q1_2025.filing_year, period=period).revision


def _sale(
    provider_id: str,
    *,
    base: str,
    iva: str,
    recargo: str | None = None,
) -> Transaction:
    """A domestic standard-rate sale carrying base, cuota and optional recargo."""
    recargo_amount = None if recargo is None else Decimal(recargo)
    gross = Decimal(base) + Decimal(iva) + (recargo_amount or Decimal("0"))
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(2025, 2, 10),
        value_date=date(2025, 2, 10),
        amount=gross,
        currency="EUR",
        counterparty="Minorista Recargo SL",
        description=f"venta {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="a" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_NOW,
            provider_name="manual",
        ),
        raw_fields={"row": provider_id},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": Decimal(base),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal(iva),
            "iva_category": IvaCategory.DOMESTIC_GENERAL,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": _NOW,
            "classified_by": "manual",
        },
    )


def _third_country_import() -> Transaction:
    """A third-country import carrying a base that only the quantity screen sees."""
    raw = RawTransaction(
        provider_transaction_id="import-1",
        booked_date=date(2025, 2, 10),
        value_date=date(2025, 2, 10),
        amount=Decimal("1000.00"),
        currency="EUR",
        counterparty="Proveedor extracomunitario",
        description="importacion de bienes",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="d" * 64,
            source_row_index=2,
            source_format=SourceFormat.MANUAL,
            ingested_at=_NOW,
            provider_name="manual",
        ),
        raw_fields={"row": "import-1"},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": Decimal("1000.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("210.00"),
            "iva_category": IvaCategory.IMPORT_THIRD_COUNTRY,
            "deduction_fact_kind": IvaDeductionFactKind.IMPORT_CURRENT,
            "deduction_provenance": IvaDeductionClassificationProvenance(
                authority=IvaDeductionEvidenceAuthority.CUSTOMS_DECLARATION,
                source_locator="customs:import-1",
                evidence_digest="e" * 64,
            ),
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": _NOW,
            "classified_by": "manual",
        },
    )


def test_the_advisory_reaches_the_resolver_envelope(tmp_path: Path) -> None:
    """The quantity screen is wired into the live resolver envelope."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository)
        repository.save(
            TransactionCatalogue.from_transactions((_sale("s-1", base="1000.00", iva="210.00"),)),
        )
        resolution = _resolver(repository).resolve(
            CalculationSourceContext(
                bucket_id=_BUCKET_ID,
                modelo="303",
                filing_year=2025,
                period=_Q1_2025,
                revision=_revision("303"),
            ),
        )

    advisories = [
        diagnostic for diagnostic in resolution.diagnostics if diagnostic.reason == "unrouted_declarable_quantity"
    ]
    assert len(advisories) == 1, "a revision drawing no base must surface exactly one advisory"
    assert "base_amount_sum" in advisories[0].message
    assert "1000.00" in advisories[0].message, "the advisory must name the amount that goes undeclared"
    assert advisories[0].resolver_id == "ledger_iva_aggregation"


def test_the_committed_revision_raises_no_advisory_in_the_envelope(tmp_path: Path) -> None:
    """Against the committed revision, a covered row stays silent."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository)
        repository.save(
            TransactionCatalogue.from_transactions((_sale("s-1", base="1000.00", iva="210.00"),)),
        )
        resolution = _resolver(repository).resolve(
            CalculationSourceContext(
                bucket_id=_BUCKET_ID,
                modelo="303",
                filing_year=2025,
                period=_Q1_2025,
                revision=_revision("303"),
            ),
        )

    assert not [
        diagnostic for diagnostic in resolution.diagnostics if diagnostic.reason == "unrouted_declarable_quantity"
    ]


def test_the_advisory_names_the_categories_carrying_the_residue(tmp_path: Path) -> None:
    """A live residue advisory identifies the category carrying the amount."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository)
        repository.save(TransactionCatalogue.from_transactions((_third_country_import(),)))
        resolution = _resolver(repository).resolve(
            CalculationSourceContext(
                bucket_id=_BUCKET_ID,
                modelo="303",
                filing_year=2025,
                period=_Q1_2025,
                revision=_revision("303"),
            ),
        )

    advisories = [
        diagnostic for diagnostic in resolution.diagnostics if diagnostic.reason == "unrouted_declarable_quantity"
    ]
    assert len(advisories) == 1, "the live import base residue must surface exactly one advisory"
    message = advisories[0].message
    assert "base_amount_sum" in message
    assert "import_third_country" in message
    for covered in (
        "domestic_general",
        "domestic_reduced",
        "domestic_super_reduced",
        "intra_community_acquisition_reverse_charge",
        "intra_community_service_acquisition_reverse_charge",
    ):
        assert covered not in message, f"{covered} draws base on this revision and must not be blamed"
