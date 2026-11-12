"""Shared purchase, ledger-row and book fixtures for the inventory ledger-claim tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from cadrumo.adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile
from cadrumo.application.inventory.service import InventoryMovementCommand, InventoryService

from .....domain.contribuyente.inventory.records import (
    InventoryAcquisitionCost,
    MovementKind,
    PurchaseLedgerRow,
    derive_inventory_acquisition_totals,
)
from .....domain.transactions.enums import BusinessClassification, TransactionDirection
from .....domain.transactions.models import Transaction, TransactionCatalogue
from .....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from .inventory_service_integration_support import acquisition, authority_record

YEAR = authority_record().decision.filing_year
BASE, IVA, RECARGO = Decimal("6800.00"), Decimal("1428.00"), Decimal("353.60")


def recargo_cost() -> InventoryAcquisitionCost:
    """A recargo purchase deducts no IVA, so its IVA and recargo join the cost."""
    template = acquisition(str(BASE))
    totals = derive_inventory_acquisition_totals(
        consideration_excluding_iva=BASE,
        consideration_iva_amount=IVA,
        consideration_recargo_amount=RECARGO,
        consideration_deductible_iva_ratio=Decimal(0),
        attributable_cost_components=(),
    )
    return template.model_copy(
        update={
            "consideration_iva_amount": IVA,
            "consideration_recargo_amount": RECARGO,
            "consideration_deductible_iva_ratio": Decimal(0),
            "nonrecoverable_iva_included": totals.nonrecoverable_iva_included,
            "recoverable_iva_excluded": totals.recoverable_iva_excluded,
            "total_acquisition_cost": totals.total_acquisition_cost,
        }
    )


def ledger_row_of(provider_id: str, *, base: Decimal = BASE, currency: str = "EUR") -> Transaction:
    gross = base + IVA + RECARGO
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id=provider_id,
                booked_date=date(YEAR, 2, 10),
                value_date=date(YEAR, 2, 10),
                amount=gross,
                currency=currency,
                counterparty="Mayorista SL",
                description="Compra de existencias",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256="d" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.CSV,
                    ingested_at=datetime(YEAR, 2, 11, 9, 0, tzinfo=UTC),
                    provider_name="CSV provider",
                ),
                raw_fields={"Concepto": "Compra de existencias"},
            ),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": base,
            "iva_amount": IVA,
            "recargo_amount": RECARGO,
        },
    )


def book_rows(profile: TestRuntimeProfile, *rows: Transaction) -> None:
    objects = secure_object_repository_for_bucket(profile.bucket_id, profile.settings)
    TransactionCatalogueRepository(bucket_id=profile.bucket_id, objects=objects).save(
        TransactionCatalogue.from_transactions(list(rows))
    )


def purchase_movement(movement_id: str, *, claim: str | None) -> InventoryMovementCommand:
    return InventoryMovementCommand(
        movement_id=movement_id,
        movement_date=date(YEAR, 2, 10),
        kind=MovementKind.PURCHASE,
        quantity=Decimal(1),
        acquisition_cost=recargo_cost(),
        ledger_row=PurchaseLedgerRow.CLAIMED if claim is not None else PurchaseLedgerRow.UNSTATED,
        claimed_transaction_id=claim,
    )


def create_book(svc: InventoryService, bucket: str) -> None:
    svc.create(bucket_id=bucket, actividad_id="A1", year=YEAR, valuation_method="fifo", opening_stock=Decimal("100.00"))
