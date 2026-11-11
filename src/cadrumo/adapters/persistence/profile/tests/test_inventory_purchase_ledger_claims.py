"""A purchase's claim on its ledger row and its recargo, through the real service, repositories and secure storage."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.inventory import InventoryLedgerRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from cadrumo.adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile
from cadrumo.application.inventory.errors import InventoryServiceInputError
from cadrumo.application.inventory.service import InventoryMovementCommand, InventoryService

from .....domain.contribuyente.inventory.corrections import inventory_refusal_key
from .....domain.contribuyente.inventory.records import (
    InventoryAcquisitionCost,
    InventoryHistoryKind,
    MovementKind,
    PurchaseLedgerRow,
    derive_inventory_acquisition_totals,
)
from .....domain.transactions.enums import BusinessClassification, TransactionDirection
from .....domain.transactions.models import Transaction, TransactionCatalogue
from .....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from .inventory_service_integration_support import acquisition, authority_record, make_svc

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

YEAR = authority_record().decision.filing_year
_BASE, _IVA, _RECARGO = Decimal("6800.00"), Decimal("1428.00"), Decimal("353.60")


def _recargo_cost() -> InventoryAcquisitionCost:
    """A recargo purchase deducts no IVA, so its IVA and recargo join the cost."""
    template = acquisition(str(_BASE))
    totals = derive_inventory_acquisition_totals(
        consideration_excluding_iva=_BASE,
        consideration_iva_amount=_IVA,
        consideration_recargo_amount=_RECARGO,
        consideration_deductible_iva_ratio=Decimal(0),
        attributable_cost_components=(),
    )
    return template.model_copy(
        update={
            "consideration_iva_amount": _IVA,
            "consideration_recargo_amount": _RECARGO,
            "consideration_deductible_iva_ratio": Decimal(0),
            "nonrecoverable_iva_included": totals.nonrecoverable_iva_included,
            "recoverable_iva_excluded": totals.recoverable_iva_excluded,
            "total_acquisition_cost": totals.total_acquisition_cost,
        }
    )


def _ledger_row(provider_id: str, *, base: Decimal = _BASE) -> Transaction:
    gross = base + _IVA + _RECARGO
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id=provider_id,
                booked_date=date(YEAR, 2, 10),
                value_date=date(YEAR, 2, 10),
                amount=gross,
                currency="EUR",
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
            "iva_amount": _IVA,
            "recargo_amount": _RECARGO,
        },
    )


def _book_rows(profile: TestRuntimeProfile, *rows: Transaction) -> None:
    objects = secure_object_repository_for_bucket(profile.bucket_id, profile.settings)
    TransactionCatalogueRepository(bucket_id=profile.bucket_id, objects=objects).save(
        TransactionCatalogue.from_transactions(list(rows))
    )


def _purchase(movement_id: str, *, claim: str | None) -> InventoryMovementCommand:
    return InventoryMovementCommand(
        movement_id=movement_id,
        movement_date=date(YEAR, 2, 10),
        kind=MovementKind.PURCHASE,
        quantity=Decimal(1),
        acquisition_cost=_recargo_cost(),
        ledger_row=PurchaseLedgerRow.CLAIMED if claim is not None else PurchaseLedgerRow.UNSTATED,
        claimed_transaction_id=claim,
    )


def _create(svc: InventoryService, bucket: str) -> None:
    svc.create(bucket_id=bucket, actividad_id="A1", year=YEAR, valuation_method="fifo", opening_stock=Decimal("100.00"))


def test_a_claimed_recargo_purchase_round_trips_through_secure_storage(secure_engine: TestRuntimeProfile) -> None:
    svc = make_svc(secure_engine)
    bucket = secure_engine.bucket_id
    row = _ledger_row("row-1")
    _book_rows(secure_engine, row)
    _create(svc, bucket)

    svc.movement_add(
        bucket_id=bucket, actividad_id="A1", year=YEAR, movement=_purchase("BUY-1", claim=row.transaction_id)
    )

    (stored,) = (
        InventoryLedgerRepository(objects=secure_object_repository_for_bucket(bucket, secure_engine.settings))
        .load()
        .ledgers
    )
    purchase = stored.period_movements[0]
    assert purchase.ledger_row is PurchaseLedgerRow.CLAIMED
    assert purchase.claimed_transaction_id == row.transaction_id
    assert purchase.acquisition_cost is not None
    assert purchase.acquisition_cost.consideration_recargo_amount == _RECARGO
    assert purchase.acquisition_cost.total_acquisition_cost == _BASE + _IVA + _RECARGO


@pytest.mark.parametrize(
    ("row_base", "claim_other_row", "reason"),
    [
        (_BASE + Decimal("0.01"), False, "claimed_transaction_amount_mismatch"),
        (_BASE, True, "claimed_transaction_missing"),
    ],
)
def test_a_claim_that_does_not_match_the_ledger_is_refused_and_writes_nothing(
    secure_engine: TestRuntimeProfile, row_base: Decimal, claim_other_row: bool, reason: str
) -> None:
    svc = make_svc(secure_engine)
    bucket = secure_engine.bucket_id
    row = _ledger_row("row-1", base=row_base)
    _book_rows(secure_engine, row)
    _create(svc, bucket)
    claim = _ledger_row("row-not-booked").transaction_id if claim_other_row else row.transaction_id

    with pytest.raises(InventoryServiceInputError) as refused:
        svc.movement_add(bucket_id=bucket, actividad_id="A1", year=YEAR, movement=_purchase("BUY-1", claim=claim))

    assert refused.value.translated_message == inventory_refusal_key(reason)
    assert svc.show(bucket_id=bucket, actividad_id="A1", year=YEAR).period_movements == ()


def test_a_purchase_states_its_ledger_row_after_the_closing_authority(secure_engine: TestRuntimeProfile) -> None:
    svc = make_svc(secure_engine)
    bucket = secure_engine.bucket_id
    row = _ledger_row("row-1")
    _book_rows(secure_engine, row)
    _create(svc, bucket)
    svc.movement_add(bucket_id=bucket, actividad_id="A1", year=YEAR, movement=_purchase("BUY-1", claim=None))
    svc.closing_authority_record(bucket_id=bucket, actividad_id="A1", year=YEAR, authority_record=authority_record())

    result = svc.movement_ledger_row(
        bucket_id=bucket,
        actividad_id="A1",
        year=YEAR,
        correction_id="claim-1",
        movement_id="BUY-1",
        ledger_row=PurchaseLedgerRow.CLAIMED,
        claimed_transaction_id=row.transaction_id,
    )

    assert result.changed is True
    ledger = svc.show(bucket_id=bucket, actividad_id="A1", year=YEAR)
    assert ledger.period_movements[0].claimed_transaction_id == row.transaction_id
    assert ledger.history[-1].kind is InventoryHistoryKind.LEDGER_ROW_STATED
    assert ledger.closing_authority_record is not None
