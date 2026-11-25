"""The ledger-row statement of a purchase through the registered operation, the real service and secure storage."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest
from pydantic import BaseModel, ValidationError

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.inventory import InventoryLedgerRepository
from cadrumo.adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from cadrumo.adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile
from cadrumo.application.inventory.ports import InventoryServicePorts
from cadrumo.application.inventory.registered_execution_result import InventoryOperationExecutionResult
from cadrumo.application.inventory.registered_executor import InventoryOperationExecutor
from cadrumo.application.inventory.registered_requests import (
    INVENTORY_MOVEMENT_CLAIM_OPERATION_DEFINITION_ID,
    InventoryMovementClaimRequest,
)
from cadrumo.application.inventory.service import InventoryMovementCommand, InventoryService
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.refusal_evidence import OperationRefusalEvidence
from cadrumo.core.config import override_settings
from cadrumo.core.operations import OperationEffect, profile_operation_subject

from .....application.tests.operation_host_fakes import IrreversibleSectionGrant, RecordingEvents, RecordingOperands
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....domain.contribuyente.inventory.corrections import inventory_refusal_key
from .....domain.contribuyente.inventory.records import MovementKind, MovementRecord, PurchaseLedgerRow
from .....domain.transactions.models import Transaction
from .inventory_purchase_claim_support import (
    BASE,
    YEAR,
    book_rows,
    create_book,
    ledger_row_of,
    purchase_movement,
    recargo_cost,
)
from .inventory_service_integration_support import claim_reads, make_svc

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DEFINITION_ID = INVENTORY_MOVEMENT_CLAIM_OPERATION_DEFINITION_ID


def _runner(
    profile: TestRuntimeProfile,
    authority: PinnedAuthorityOperation,
) -> tuple[
    Callable[[InventoryMovementClaimRequest], str | OperationRefusalEvidence], RecordingEvents, RecordingOperands
]:
    bucket = profile.bucket_id

    def ports(*, bucket_id: str) -> InventoryServicePorts:
        del bucket_id
        return InventoryServicePorts(
            inventory_repository_factory=lambda inner: InventoryLedgerRepository(
                objects=secure_object_repository_for_bucket(inner, profile.settings),
            ),
            document_file_name=lambda _digest: None,
            bucket_event_repository=BucketEventHistoryRepository(objects=profile.repository),
            claim_reads_factory=lambda inner: claim_reads(profile, inner),
        )

    events, operands = RecordingEvents(), RecordingOperands("d" * 64)
    subject = profile_operation_subject(bucket)
    context = SimpleNamespace(
        identity=SimpleNamespace(definition_id=_DEFINITION_ID, subject_ref=subject),
        authority_operation=authority,
        events=events,
        cancellation=IrreversibleSectionGrant(),
        operands=operands,
    )
    executor = InventoryOperationExecutor(ports, definition_id=_DEFINITION_ID)

    def execute(request: InventoryMovementClaimRequest) -> str | OperationRefusalEvidence:
        wrapped = OperationRequest[BaseModel](definition_id=_DEFINITION_ID, subject_ref=subject, payload=request)
        with override_settings(cadrumo_active_profile=bucket):
            return asyncio.run(executor.execute(wrapped, cast(Any, context)))

    return execute, events, operands


def _request(
    profile: TestRuntimeProfile,
    correction_id: str,
    ledger_row: PurchaseLedgerRow,
    row: Transaction | None = None,
    *,
    actividad_id: str = "A1",
) -> InventoryMovementClaimRequest:
    return InventoryMovementClaimRequest(
        profile_id=UUID(profile.bucket_id),
        actividad_id=actividad_id,
        year=YEAR,
        correction_id=correction_id,
        movement_id="BUY-1",
        ledger_row=ledger_row,
        claimed_transaction_id=None if row is None else row.transaction_id,
    )


def _book(profile: TestRuntimeProfile, *rows: Transaction) -> InventoryService:
    svc = make_svc(profile)
    book_rows(profile, *rows)
    create_book(svc, profile.bucket_id)
    svc.movement_add(
        bucket_id=profile.bucket_id,
        actividad_id="A1",
        year=YEAR,
        movement=purchase_movement("BUY-1", claim=None),
    )
    return svc


def _stored_purchase(svc: InventoryService, profile: TestRuntimeProfile) -> MovementRecord:
    return svc.show(bucket_id=profile.bucket_id, actividad_id="A1", year=YEAR).period_movements[0]


def _last_result(operands: RecordingOperands) -> InventoryOperationExecutionResult:
    stored = operands.stored[-1]
    assert isinstance(stored, InventoryOperationExecutionResult)
    return stored


def test_the_operation_links_a_purchase_to_its_ledger_row_and_the_statement_persists(
    secure_engine: TestRuntimeProfile,
    operation: PinnedAuthorityOperation,
) -> None:
    row = ledger_row_of("row-1")
    svc = _book(secure_engine, row)
    execute, events, operands = _runner(secure_engine, operation)

    reference = execute(_request(secure_engine, "claim-1", PurchaseLedgerRow.CLAIMED, row))

    assert reference == "d" * 64
    assert events.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
    result = _last_result(operands)
    assert result.operation_id == "movement.claim"
    assert result.outcome == "success"
    assert result.ledger_result is not None
    assert result.ledger_result.changed
    stored = _stored_purchase(svc, secure_engine)
    assert stored.ledger_row is PurchaseLedgerRow.CLAIMED
    assert stored.claimed_transaction_id == row.transaction_id


def test_a_replay_changes_nothing_and_a_clear_returns_the_purchase_to_unstated(
    secure_engine: TestRuntimeProfile,
    operation: PinnedAuthorityOperation,
) -> None:
    row = ledger_row_of("row-1")
    svc = _book(secure_engine, row)
    execute, events, operands = _runner(secure_engine, operation)
    execute(_request(secure_engine, "claim-1", PurchaseLedgerRow.CLAIMED, row))

    execute(_request(secure_engine, "claim-1", PurchaseLedgerRow.CLAIMED, row))
    assert events.effects[-1] is OperationEffect.NONE
    replayed = _last_result(operands).ledger_result
    assert replayed is not None
    assert not replayed.changed

    execute(_request(secure_engine, "clear-1", PurchaseLedgerRow.UNSTATED))
    assert events.effects[-1] is OperationEffect.UPDATED
    stored = _stored_purchase(svc, secure_engine)
    assert stored.ledger_row is PurchaseLedgerRow.UNSTATED
    assert stored.claimed_transaction_id is None


def test_the_operation_states_that_no_ledger_row_books_the_purchase(
    secure_engine: TestRuntimeProfile, operation: PinnedAuthorityOperation
) -> None:
    svc = _book(secure_engine)
    execute, _events, _operands = _runner(secure_engine, operation)

    execute(_request(secure_engine, "none-1", PurchaseLedgerRow.NONE))

    stored = _stored_purchase(svc, secure_engine)
    assert stored.ledger_row is PurchaseLedgerRow.NONE
    assert stored.claimed_transaction_id is None


@pytest.mark.parametrize(
    ("book_base", "claim_unbooked_row", "reason"),
    [
        (BASE + Decimal("0.01"), False, "claimed_transaction_amount_mismatch"),
        (BASE, True, "claimed_transaction_missing"),
    ],
)
def test_a_refused_claim_settles_as_a_typed_refusal_with_served_words_and_writes_nothing(
    secure_engine: TestRuntimeProfile,
    operation: PinnedAuthorityOperation,
    book_base: Decimal,
    claim_unbooked_row: bool,
    reason: str,
) -> None:
    booked = ledger_row_of("row-1", base=book_base)
    svc = _book(secure_engine, booked)
    execute, events, operands = _runner(secure_engine, operation)
    target = ledger_row_of("row-unbooked") if claim_unbooked_row else booked

    refusal = execute(_request(secure_engine, "claim-1", PurchaseLedgerRow.CLAIMED, target))

    assert isinstance(refusal, OperationRefusalEvidence)
    assert events.effects == [OperationEffect.UNKNOWN, OperationEffect.NONE]
    detail = _last_result(operands).refusal
    assert detail is not None
    assert detail.reason == reason
    assert detail.reason_key == inventory_refusal_key(reason)
    assert detail.movement_id == "BUY-1"
    assert detail.refusal_words is not None
    assert detail.refusal_words != ""
    assert "%{" not in detail.refusal_words
    assert _stored_purchase(svc, secure_engine).ledger_row is PurchaseLedgerRow.UNSTATED


def test_a_second_book_cannot_claim_a_row_the_first_book_claims(
    secure_engine: TestRuntimeProfile, operation: PinnedAuthorityOperation
) -> None:
    row = ledger_row_of("row-1")
    svc = _book(secure_engine, row)
    execute, _events, operands = _runner(secure_engine, operation)
    execute(_request(secure_engine, "claim-1", PurchaseLedgerRow.CLAIMED, row))
    svc.create(
        bucket_id=secure_engine.bucket_id,
        actividad_id="A2",
        year=YEAR,
        valuation_method="fifo",
        opening_stock=Decimal(0),
    )
    svc.movement_add(
        bucket_id=secure_engine.bucket_id,
        actividad_id="A2",
        year=YEAR,
        movement=InventoryMovementCommand(
            movement_id="BUY-1",
            movement_date=date(YEAR, 2, 10),
            kind=MovementKind.PURCHASE,
            quantity=Decimal(1),
            acquisition_cost=recargo_cost(),
        ),
    )

    refusal = execute(_request(secure_engine, "claim-2", PurchaseLedgerRow.CLAIMED, row, actividad_id="A2"))

    assert isinstance(refusal, OperationRefusalEvidence)
    detail = _last_result(operands).refusal
    assert detail is not None
    assert detail.reason == "claimed_transaction_double_claim"


def test_the_request_names_a_transaction_exactly_when_the_purchase_claims_one(
    secure_engine: TestRuntimeProfile,
    operation: PinnedAuthorityOperation,
) -> None:
    row = ledger_row_of("row-1")
    with pytest.raises(ValidationError):
        _request(secure_engine, "claim-1", PurchaseLedgerRow.CLAIMED)
    with pytest.raises(ValidationError):
        _request(secure_engine, "none-1", PurchaseLedgerRow.NONE, row)
