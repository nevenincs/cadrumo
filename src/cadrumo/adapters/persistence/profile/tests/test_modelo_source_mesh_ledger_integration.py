"""Persistence integration for the ledger source-mesh degradation boundary."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import text

from cadrumo.adapters.persistence.profile.catalogue_reads import (
    InvoiceCatalogueReadAdapter,
    TransactionCatalogueReadAdapter,
)
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.errors import EnvelopeVersionError
from cadrumo.adapters.persistence.storage.secure_object_namespaces import TRANSACTION_CATALOGUE_NAMESPACE
from cadrumo.adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile
from cadrumo.adapters.persistence.tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from cadrumo.application.aggregation.modelo_bindings import LedgerIvaAggregationSourceResolver
from cadrumo.application.aggregation.source_mesh import CalculationSourceContext
from cadrumo.application.aggregation.source_resolution_operations import merge_source_resolutions
from cadrumo.application.invoices.catalogue_reads_ports import InvoiceCatalogueReadPorts
from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.classification.policies import SensitivityClass
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import bundled_authority
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection
from cadrumo.domain.transactions.models import Transaction, TransactionCatalogue
from cadrumo.domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from cadrumo.domain.transactions.repository import transaction_index_object_key

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "28282828-2828-4828-8828-282828282828"

runtime_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID, autouse=False, name="runtime_profile")


def _revision() -> ModeloRevision:
    return bundled_authority().modelo("303").revisions["2022"]


def _transaction(provider_id: str) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(2026, 2, 10),
        value_date=date(2026, 2, 10),
        amount=Decimal("121.00"),
        currency="EUR",
        counterparty="Cliente o proveedor",
        description=f"ledger row {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 2, 11, 12, 0, tzinfo=UTC),
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.INCOMING,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "group_label": None,
            "category_id": "test_iva_operation",
            "taxable_base": Decimal("100.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("21.00"),
            "classified_at": datetime(2026, 2, 11, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _resolver(*, transaction_repository: TransactionCatalogueRepository, objects: object) -> LedgerIvaAggregationSourceResolver:
    invoice_repository = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects)
    return LedgerIvaAggregationSourceResolver(
        transaction_repository=transaction_repository,
        invoice_catalogue_read_ports=InvoiceCatalogueReadPorts(
            invoice_reader=InvoiceCatalogueReadAdapter(repository=invoice_repository),
            transaction_reader=TransactionCatalogueReadAdapter(repository=transaction_repository),
        ),
        prorrata_register_repository=ProrrataRegisterRepository(bucket_id=_BUCKET_ID, objects=objects),
        investment_asset_profile_id=_BUCKET_ID,
    )


def test_iva_source_mesh_resolver_degrades_on_unreadable_storage(
    runtime_profile: TestRuntimeProfile,
    caplog: pytest.LogCaptureFixture,
) -> None:
    objects = runtime_profile.repository
    transaction_repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects)
    incoming = _transaction("sale-general")
    transaction_repository.save(TransactionCatalogue.from_transactions((incoming,)))
    with runtime_profile.repository._engine.begin() as connection:
        connection.execute(
            text("UPDATE secure_objects SET payload = X'00' WHERE namespace = :namespace"),
            {"namespace": TRANSACTION_CATALOGUE_NAMESPACE.namespace},
        )

    with caplog.at_level(logging.DEBUG, logger="cadrumo.application.aggregation.source_mesh"):
        resolution = _resolver(transaction_repository=transaction_repository, objects=objects).resolve(
            CalculationSourceContext(
                bucket_id=_BUCKET_ID,
                modelo="303",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
                revision=_revision(),
            ),
        )
    merged = merge_source_resolutions((resolution,))

    assert resolution.binding_values == {}
    assert resolution.source_transaction_ids == ()
    assert [diagnostic.reason for diagnostic in merged.diagnostics] == ["storage_degraded"]
    assert merged.diagnostics[0].source_kind == BindingSourceKind.LEDGER_IVA_AGGREGATION.value
    assert any("source mesh resolver storage degradation" in record.message for record in caplog.records)


def test_transaction_catalogue_refuses_new_legacy_drift_fixture(runtime_profile: TestRuntimeProfile) -> None:
    with pytest.raises(EnvelopeVersionError):
        runtime_profile.repository.save(
            namespace=TRANSACTION_CATALOGUE_NAMESPACE.namespace,
            object_key=transaction_index_object_key(_BUCKET_ID),
            classification=SensitivityClass.FINANCIAL,
            schema_version=1,
            written_at=datetime(2026, 6, 4, 12, 0, tzinfo=UTC),
            payload=b"{}",
        )
