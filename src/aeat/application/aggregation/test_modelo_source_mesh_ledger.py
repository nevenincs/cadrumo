"""Source mesh parity tests for existing ledger-backed modelo bindings."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...core.resources import resources
from ...domain.calculations.registry import ModeloRevision
from ...domain.categories import SpendingCategory
from ...domain.invoices import (
    Invoice,
    InvoiceCatalogue,
    InvoiceCatalogueRepository,
    InvoiceLine,
    IvaRate,
    PaymentStatus,
)
from ...domain.invoices import (
    InvoiceKind as CatalogueInvoiceKind,
)
from ...domain.iva import (
    EUMemberState,
    IvaRateKind,
    OssIossRegime,
    TransactionKind,
)
from ...domain.iva import (
    InvoiceKind as IvaInvoiceKind,
)
from ...domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionDirection,
)
from ...tests.secure_sql import isolated_runtime_profile
from . import (
    CalculationSourceContext,
    LedgerIvaAggregationSourceResolver,
    LedgerRentaExpenseAggregationSourceResolver,
    OssIossLedgerCandidate,
    OssIossLedgerSourceResolver,
    aggregate_oss_ioss_bindings,
    resolve_modelo_ledger_binding_values_from_repositories,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        yield profile.repository


def _revision(modelo: str, revision_id: str) -> ModeloRevision:
    modelo_definition = next(item for item in resources().modelos.all() if item.id == modelo)
    return modelo_definition.revisions[revision_id]


def _raw_transaction(
    provider_id: str,
    *,
    booked_date: date,
    amount: Decimal,
) -> RawTransaction:
    return RawTransaction(
        transaction_id=provider_id,
        booked_date=booked_date,
        value_date=booked_date,
        amount=amount,
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


def _iva_transaction(
    provider_id: str,
    *,
    direction: TransactionDirection,
    amount: Decimal,
    taxable_base: Decimal,
    iva_amount: Decimal,
    booked_date: date = date(2026, 2, 10),
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(provider_id, booked_date=booked_date, amount=amount),
            "direction": direction,
            "business_classification": BusinessClassification.BUSINESS,
            "category_id": "test_iva_operation",
            "taxable_base": taxable_base,
            "iva_rate": Decimal("0.21"),
            "iva_amount": iva_amount,
            "classified_at": datetime(2026, 2, 11, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        }
    )


def _renta_transaction(
    provider_id: str,
    *,
    purchase_invoice_evidence_id: str | None,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(
                provider_id,
                booked_date=date(2025, 4, 5),
                amount=Decimal("-121.00"),
            ),
            "direction": TransactionDirection.OUTGOING,
            "business_classification": BusinessClassification.BUSINESS,
            "purchase_invoice_evidence_id": purchase_invoice_evidence_id,
            "category_id": SpendingCategory.ASESORIA_FISCAL.value,
            "classified_at": datetime(2025, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        }
    )


def _invoice(tx_id: str, *, bucket_id: str = "bucket-a") -> Invoice:
    line = InvoiceLine(
        description="Asesoria fiscal",
        quantity=Decimal("1"),
        unit_price=Decimal("100.00"),
        subtotal=Decimal("100.00"),
        iva_rate=IvaRate.RATE_21,
        iva_amount=Decimal("21.00"),
    )
    return Invoice.model_validate(
        {
            "bucket_id": bucket_id,
            "kind": CatalogueInvoiceKind.RECEIVED,
            "invoice_number": f"INV-{tx_id}",
            "issued_at": date(2025, 4, 1),
            "counterparty_name": "Proveedor SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": Decimal("100.00"),
            "iva_total": Decimal("21.00"),
            "grand_total": Decimal("121.00"),
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "linked_transaction_ids": (tx_id,),
        }
    )


def test_iva_source_mesh_resolver_matches_existing_bucket_ledger_bridge(secure_objects: SecureObjectRepository) -> None:
    revision = _revision("303", "2009-y-siguientes")
    tx_repo = TransactionCatalogueRepository(
        bucket_id="bucket-a",
        objects=secure_objects,
    )
    incoming = _iva_transaction(
        "sale-general",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("121.00"),
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
    )
    outgoing = _iva_transaction(
        "purchase-general",
        direction=TransactionDirection.OUTGOING,
        amount=Decimal("-60.50"),
        taxable_base=Decimal("50.00"),
        iva_amount=Decimal("10.50"),
    )
    tx_repo.save(TransactionCatalogue.from_transactions((incoming, outgoing)))

    legacy = resolve_modelo_ledger_binding_values_from_repositories(
        bucket_id="bucket-a",
        modelo="303",
        revision=revision,
        filing_year=2026,
        period="1T",
        transaction_repository=tx_repo,
    )
    resolution = LedgerIvaAggregationSourceResolver(transaction_repository=tx_repo).resolve(
        CalculationSourceContext(
            bucket_id="bucket-a",
            modelo="303",
            filing_year=2026,
            period="1T",
            revision=revision,
        )
    )

    assert resolution.binding_values == legacy.binding_values
    assert resolution.source_transaction_ids == legacy.source_transaction_ids
    assert resolution.diagnostics == ()
    assert {item.source_ref for item in resolution.provenance} == {
        f"transaction:{incoming.transaction_id}",
        f"transaction:{outgoing.transaction_id}",
    }


def test_renta_source_mesh_resolver_preserves_purchase_invoice_evidence_provenance(
    secure_objects: SecureObjectRepository,
) -> None:
    revision = _revision("100", "2025")
    tx_repo = TransactionCatalogueRepository(
        bucket_id="bucket-a",
        objects=secure_objects,
    )
    invoice_repo = InvoiceCatalogueRepository(objects=secure_objects)
    initial = _renta_transaction("renta-linked", purchase_invoice_evidence_id=None)
    invoice = _invoice(initial.transaction_id)
    linked = _renta_transaction("renta-linked", purchase_invoice_evidence_id=invoice.invoice_id)
    tx_repo.save(TransactionCatalogue.from_transactions((linked,)))
    invoice_repo.save(InvoiceCatalogue.from_invoices((invoice,)))

    legacy = resolve_modelo_ledger_binding_values_from_repositories(
        bucket_id="bucket-a",
        modelo="100",
        revision=revision,
        filing_year=2025,
        period="0A",
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
    )
    resolution = LedgerRentaExpenseAggregationSourceResolver(
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
    ).resolve(
        CalculationSourceContext(
            bucket_id="bucket-a",
            modelo="100",
            filing_year=2025,
            period="0A",
            revision=revision,
        )
    )

    assert resolution.binding_values == legacy.binding_values
    assert resolution.source_transaction_ids == (linked.transaction_id,)
    assert resolution.diagnostics == ()
    assert {item.source_ref for item in resolution.provenance} == {
        f"transaction:{linked.transaction_id}",
        f"purchase-invoice-evidence:{invoice.invoice_id}",
    }


def test_oss_source_mesh_resolver_matches_existing_candidate_binding_wrapper() -> None:
    revision = _revision("369", "esquema-union")
    candidates = (
        OssIossLedgerCandidate(
            ledger_id="oss-ledger-1",
            transaction_date=date(2025, 6, 15),
            regime=OssIossRegime.UNION_SCHEME,
            destination_member_state=EUMemberState.DE,
            rate_kind=IvaRateKind.GENERAL,
            invoice_direction=IvaInvoiceKind.ISSUED,
            transaction_kind=TransactionKind.OSS_UNION_SERVICES,
            base_amount=Decimal("100.00"),
            iva_amount=Decimal("19.00"),
        ),
    )

    legacy = aggregate_oss_ioss_bindings(revision, candidates)
    resolution = OssIossLedgerSourceResolver(candidates=candidates).resolve(
        CalculationSourceContext(
            bucket_id="bucket-a",
            modelo="369",
            filing_year=2025,
            period="4T",
            revision=revision,
        )
    )

    assert resolution.binding_values == legacy
    assert resolution.source_transaction_ids == ("oss-ledger-1",)
    assert resolution.diagnostics == ()
    assert tuple(item.source_ref for item in resolution.provenance) == ("transaction:oss-ledger-1",)
