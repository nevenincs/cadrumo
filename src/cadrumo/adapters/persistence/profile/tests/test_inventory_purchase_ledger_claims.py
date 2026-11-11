"""A purchase's claim on its ledger row and its recargo, through the real service, repositories and secure storage."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.adapters.persistence.profile.inventory import InventoryLedgerRepository
from cadrumo.adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from cadrumo.adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile
from cadrumo.application.inventory.errors import InventoryServiceInputError

from .....domain.contribuyente.inventory.corrections import inventory_refusal_key
from .....domain.contribuyente.inventory.records import (
    InventoryHistoryKind,
    PurchaseLedgerRow,
)
from .inventory_purchase_claim_support import (
    BASE,
    IVA,
    RECARGO,
    YEAR,
    book_rows,
    create_book,
    ledger_row_of,
    purchase_movement,
)
from .inventory_service_integration_support import authority_record, make_svc

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


def test_a_claimed_recargo_purchase_round_trips_through_secure_storage(secure_engine: TestRuntimeProfile) -> None:
    svc = make_svc(secure_engine)
    bucket = secure_engine.bucket_id
    row = ledger_row_of("row-1")
    book_rows(secure_engine, row)
    create_book(svc, bucket)

    svc.movement_add(
        bucket_id=bucket, actividad_id="A1", year=YEAR, movement=purchase_movement("BUY-1", claim=row.transaction_id)
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
    assert purchase.acquisition_cost.consideration_recargo_amount == RECARGO
    assert purchase.acquisition_cost.total_acquisition_cost == BASE + IVA + RECARGO


@pytest.mark.parametrize(
    ("row_base", "claim_other_row", "reason"),
    [
        (BASE + Decimal("0.01"), False, "claimed_transaction_amount_mismatch"),
        (BASE, True, "claimed_transaction_missing"),
    ],
)
def test_a_claim_that_does_not_match_the_ledger_is_refused_and_writes_nothing(
    secure_engine: TestRuntimeProfile, row_base: Decimal, claim_other_row: bool, reason: str
) -> None:
    svc = make_svc(secure_engine)
    bucket = secure_engine.bucket_id
    row = ledger_row_of("row-1", base=row_base)
    book_rows(secure_engine, row)
    create_book(svc, bucket)
    claim = ledger_row_of("row-not-booked").transaction_id if claim_other_row else row.transaction_id

    with pytest.raises(InventoryServiceInputError) as refused:
        svc.movement_add(
            bucket_id=bucket, actividad_id="A1", year=YEAR, movement=purchase_movement("BUY-1", claim=claim)
        )

    assert refused.value.translated_message == inventory_refusal_key(reason)
    assert svc.show(bucket_id=bucket, actividad_id="A1", year=YEAR).period_movements == ()


def test_a_purchase_states_its_ledger_row_after_the_closing_authority(secure_engine: TestRuntimeProfile) -> None:
    svc = make_svc(secure_engine)
    bucket = secure_engine.bucket_id
    row = ledger_row_of("row-1")
    book_rows(secure_engine, row)
    create_book(svc, bucket)
    svc.movement_add(bucket_id=bucket, actividad_id="A1", year=YEAR, movement=purchase_movement("BUY-1", claim=None))
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
