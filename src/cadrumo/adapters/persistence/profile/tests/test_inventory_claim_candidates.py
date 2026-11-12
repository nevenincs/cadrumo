"""The transactions a purchase may claim, read through the registered operation and checked against the claim write."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo.adapters.persistence.profile.actividad_asset import ActividadAssetHistoryRepository
from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.inventory import InventoryLedgerRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from cadrumo.adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile
from cadrumo.application.inventory.movement_claim_checks import InventoryClaimLedgerReads
from cadrumo.application.inventory.ports import InventoryServicePorts
from cadrumo.application.inventory.registered_claim_candidates_operation import (
    INVENTORY_CLAIM_CANDIDATES_OPERATION_DEFINITION_ID,
    InventoryClaimCandidatesExecutionResult,
    InventoryClaimCandidatesExecutor,
    InventoryClaimCandidatesRequest,
)
from cadrumo.application.inventory.registered_execution_result import InventoryOperationExecutionResult
from cadrumo.application.inventory.registered_executor import InventoryOperationExecutor
from cadrumo.application.inventory.registered_requests import (
    INVENTORY_MOVEMENT_CLAIM_OPERATION_DEFINITION_ID,
    INVENTORY_NOT_FOUND_REFUSAL_CODE,
    INVENTORY_SERVICE_INPUT_REFUSAL_CODE,
    InventoryMovementClaimRequest,
)
from cadrumo.application.inventory.service import InventoryMovementCommand, InventoryService
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.refusal_evidence import OperationRefusalEvidence
from cadrumo.core.config import override_settings
from cadrumo.core.operations import OperationEffect, profile_operation_subject

from .....application.actividad_asset.tests.operations_support import build_revision
from .....application.tests.operation_host_fakes import IrreversibleSectionGrant, RecordingEvents, RecordingOperands
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....domain.contribuyente.inventory.records import MovementKind, PurchaseLedgerRow
from .....domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
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

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PURCHASE = "BUY-1"


def _ports(
    profile: TestRuntimeProfile, assets: tuple[ActivityAssetRevision, ...]
) -> Callable[..., InventoryServicePorts]:
    def ports(*, bucket_id: str) -> InventoryServicePorts:
        def reads(inner: str) -> InventoryClaimLedgerReads:
            objects = secure_object_repository_for_bucket(inner, profile.settings)
            return InventoryClaimLedgerReads(
                transactions=TransactionCatalogueRepository(bucket_id=inner, objects=objects).load,
                asset_revisions=lambda: (
                    *ActividadAssetHistoryRepository(bucket_id=inner, objects=objects).load().revisions,
                    *assets,
                ),
            )

        del bucket_id
        return InventoryServicePorts(
            inventory_repository_factory=lambda inner: InventoryLedgerRepository(
                objects=secure_object_repository_for_bucket(inner, profile.settings),
            ),
            document_file_name=lambda _digest: None,
            bucket_event_repository=BucketEventHistoryRepository(objects=profile.repository),
            claim_reads_factory=reads,
        )

    return ports


class _Host:
    """Run the candidates read and the claim write through their real executors against one profile."""

    def __init__(
        self,
        profile: TestRuntimeProfile,
        authority: PinnedAuthorityOperation,
        assets: tuple[ActivityAssetRevision, ...] = (),
    ) -> None:
        self.profile = profile
        self.authority = authority
        self.ports = _ports(profile, assets)
        self.events = RecordingEvents()
        self.operands = RecordingOperands("d" * 64)

    def _run(self, definition_id: str, executor: Any, payload: BaseModel) -> str | OperationRefusalEvidence:
        subject = profile_operation_subject(self.profile.bucket_id)
        context = SimpleNamespace(
            identity=SimpleNamespace(definition_id=definition_id, subject_ref=subject),
            authority_operation=self.authority,
            events=self.events,
            cancellation=IrreversibleSectionGrant(),
            operands=self.operands,
        )
        request = OperationRequest[BaseModel](definition_id=definition_id, subject_ref=subject, payload=payload)
        with override_settings(cadrumo_active_profile=self.profile.bucket_id):
            outcome = asyncio.run(executor.execute(request, cast(Any, context)))
        assert isinstance(outcome, str | OperationRefusalEvidence)
        return outcome

    def candidates(
        self, *, movement_id: str = _PURCHASE, actividad_id: str = "A1"
    ) -> InventoryClaimCandidatesExecutionResult:
        self._run(
            INVENTORY_CLAIM_CANDIDATES_OPERATION_DEFINITION_ID,
            InventoryClaimCandidatesExecutor(self.ports),
            InventoryClaimCandidatesRequest(
                profile_id=UUID(self.profile.bucket_id), actividad_id=actividad_id, year=YEAR, movement_id=movement_id
            ),
        )
        stored = self.operands.stored[-1]
        assert isinstance(stored, InventoryClaimCandidatesExecutionResult)
        return stored

    def claim(self, correction_id: str, transaction: Transaction, *, actividad_id: str = "A1") -> str:
        """Settle the claim write for one transaction; the refusal reason when it is refused, else ``accepted``."""
        outcome = self._run(
            INVENTORY_MOVEMENT_CLAIM_OPERATION_DEFINITION_ID,
            InventoryOperationExecutor(self.ports, definition_id=INVENTORY_MOVEMENT_CLAIM_OPERATION_DEFINITION_ID),
            InventoryMovementClaimRequest(
                profile_id=UUID(self.profile.bucket_id),
                actividad_id=actividad_id,
                year=YEAR,
                correction_id=correction_id,
                movement_id=_PURCHASE,
                ledger_row=PurchaseLedgerRow.CLAIMED,
                claimed_transaction_id=transaction.transaction_id,
            ),
        )
        stored = self.operands.stored[-1]
        assert isinstance(stored, InventoryOperationExecutionResult)
        if isinstance(outcome, OperationRefusalEvidence):
            assert stored.refusal is not None
            return stored.refusal.reason
        assert stored.outcome == "success"
        return "accepted"


def _seed_book(profile: TestRuntimeProfile, *rows: Transaction) -> InventoryService:
    svc = InventoryService(ports=_ports(profile, ())(bucket_id=profile.bucket_id))
    book_rows(profile, *rows)
    create_book(svc, profile.bucket_id)
    svc.movement_add(
        bucket_id=profile.bucket_id, actividad_id="A1", year=YEAR, movement=purchase_movement(_PURCHASE, claim=None)
    )
    return svc


def test_the_candidates_are_exactly_the_transactions_the_claim_write_accepts(
    secure_engine: TestRuntimeProfile, operation: PinnedAuthorityOperation
) -> None:
    equal, equal_too = ledger_row_of("equal"), ledger_row_of("equal-too")
    other_amount = ledger_row_of("other-amount", base=BASE + Decimal("0.01"))
    foreign = ledger_row_of("foreign", currency="USD")
    in_other_book = ledger_row_of("in-other-book")
    in_asset_register = ledger_row_of("in-asset-register")
    rows = (equal, equal_too, other_amount, foreign, in_other_book, in_asset_register)
    svc = _seed_book(secure_engine, *rows)
    svc.create(bucket_id=secure_engine.bucket_id, actividad_id="A2", year=YEAR, valuation_method="fifo")
    svc.movement_add(
        bucket_id=secure_engine.bucket_id,
        actividad_id="A2",
        year=YEAR,
        movement=InventoryMovementCommand(
            movement_id=_PURCHASE,
            movement_date=date(YEAR, 2, 10),
            kind=MovementKind.PURCHASE,
            quantity=Decimal(1),
            acquisition_cost=recargo_cost(),
        ),
    )
    assets = (
        build_revision().model_copy(
            update={
                "acquisition": build_revision().acquisition.model_copy(
                    update={"observed_transaction_id": in_asset_register.transaction_id}
                )
            }
        ),
    )
    host = _Host(secure_engine, operation, assets)
    assert host.claim("other-book-claims", in_other_book, actividad_id="A2") == "accepted"

    result = host.candidates().result

    assert result.outcome == "listed"
    assert host.events.effects[-1] is OperationEffect.NONE
    offered = {item.transaction_id for item in result.candidates}
    assert offered == {equal.transaction_id, equal_too.transaction_id}
    offered_rows = {item.transaction_id: item for item in result.candidates}
    sample = offered_rows[equal.transaction_id]
    assert (sample.booked_date, sample.currency, sample.counterparty, sample.description) == (
        date(YEAR, 2, 10),
        "EUR",
        "Mayorista SL",
        "Compra de existencias",
    )
    assert sample.taxable_base is not None
    assert Decimal(sample.taxable_base.decimal) == BASE

    refused_reasons = {
        row.raw.provider_transaction_id: host.claim(f"probe-{row.raw.provider_transaction_id}", row)
        for row in rows
        if row.transaction_id not in offered
    }
    assert refused_reasons == {
        "other-amount": "claimed_transaction_amount_mismatch",
        "foreign": "claimed_transaction_not_eur",
        "in-other-book": "claimed_transaction_double_claim",
        "in-asset-register": "claimed_transaction_double_claim",
    }
    assert [
        host.claim(f"accept-{item.transaction_id[:8]}", _row(rows, item.transaction_id)) for item in result.candidates
    ] == ["accepted"] * len(result.candidates)


def _row(rows: tuple[Transaction, ...], transaction_id: str) -> Transaction:
    return next(row for row in rows if row.transaction_id == transaction_id)


def test_the_transaction_a_purchase_already_claims_is_not_offered_again(
    secure_engine: TestRuntimeProfile, operation: PinnedAuthorityOperation
) -> None:
    claimed, spare = ledger_row_of("claimed"), ledger_row_of("spare")
    _seed_book(secure_engine, claimed, spare)
    host = _Host(secure_engine, operation)
    assert host.claim("claim-1", claimed) == "accepted"

    offered = {item.transaction_id for item in host.candidates().result.candidates}

    assert offered == {spare.transaction_id}


def test_a_book_with_no_matching_transaction_lists_none(
    secure_engine: TestRuntimeProfile, operation: PinnedAuthorityOperation
) -> None:
    _seed_book(secure_engine, ledger_row_of("other-amount", base=BASE + Decimal("1.00")))

    result = _Host(secure_engine, operation).candidates().result

    assert (result.outcome, result.candidates, result.refusal) == ("listed", (), None)


@pytest.mark.parametrize(
    ("movement_id", "actividad_id", "code", "reason"),
    [
        ("NO-SUCH", "A1", INVENTORY_SERVICE_INPUT_REFUSAL_CODE, "movement_not_found"),
        ("SELL-1", "A1", INVENTORY_SERVICE_INPUT_REFUSAL_CODE, "ledger_row_not_purchase"),
        (_PURCHASE, "NO-BOOK", INVENTORY_NOT_FOUND_REFUSAL_CODE, "activity_not_found"),
    ],
)
def test_a_movement_that_cannot_claim_or_an_unknown_book_is_refused_with_served_words(
    secure_engine: TestRuntimeProfile,
    operation: PinnedAuthorityOperation,
    movement_id: str,
    actividad_id: str,
    code: str,
    reason: str,
) -> None:
    svc = _seed_book(secure_engine, ledger_row_of("row"))
    svc.movement_add(
        bucket_id=secure_engine.bucket_id,
        actividad_id="A1",
        year=YEAR,
        movement=InventoryMovementCommand(
            movement_id="SELL-1", movement_date=date(YEAR, 3, 1), kind=MovementKind.COGS, quantity=Decimal(1)
        ),
    )
    host = _Host(secure_engine, operation)

    result = host.candidates(movement_id=movement_id, actividad_id=actividad_id).result

    assert result.outcome == "refused"
    assert result.candidates == ()
    assert result.refusal is not None
    assert (result.refusal.code, result.refusal.reason) == (code, reason)
    words = result.refusal.refusal_words
    assert words is not None
    assert words != ""
    assert "%{" not in words
    assert host.events.effects == [OperationEffect.NONE]
