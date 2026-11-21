"""Removing a movement's invoice link, over real secure storage.

The unlink clears both sides of the link and records an unlinked event in the
same batch, leaving the link's own event in the history. Every refusal is typed,
names its next step, and leaves every stored row, invoice and event exactly as
it was. The invoice payment partition the IVA calculation and the ledger
readiness share reads the removal: the movement no longer pays the invoice.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.invoice_iva_source import (
    partition_invoice_payments,
    with_movement_side_links,
)
from cadrumo.application.ledger.action_ports import LedgerActionPorts
from cadrumo.application.ledger.actions_manual import link_manual_transaction_invoice
from cadrumo.application.ledger.invoice_unlink import (
    InvoiceUnlinkCause,
    InvoiceUnlinkNextStep,
    InvoiceUnlinkRefusedError,
    InvoiceUnlinkResult,
    unlink_manual_transaction_invoice,
)
from cadrumo.application.ledger.models import ManualLedgerTransactionCommand
from cadrumo.application.ledger.unlink_operation import (
    LEDGER_UNLINK_OPERATION_DEFINITION_ID,
    LEDGER_UNLINK_REFUSAL_CODE,
    LedgerUnlinkExecutionResult,
    LedgerUnlinkExecutor,
    LedgerUnlinkRequest,
)
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.owner import OperationExecutorContext
from cadrumo.application.operations.refusal_evidence import OperationRefusalEvidence
from cadrumo.core.operations import OperationEffect, profile_operation_subject
from cadrumo.domain.buckets.event import BucketEvent, BucketEventObjectType, BucketEventType
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.invoices.models import Invoice
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue
from cadrumo.domain.transactions.enums import TransactionDirection
from cadrumo.domain.transactions.models import Transaction

from .....application.ledger.tests.manual_transaction_support import create_manual_transaction
from .classification_origin_support import BUCKET_ID, synthetic_invoice
from .ledger_action_create_support import ledger_ports_for_test
from .ledger_action_persistence_support import persist_verified_revision_citing_transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = BUCKET_ID
_PROFILE = UUID(_BUCKET)
_LINKED_AT = datetime(2025, 1, 22, 9, 0, tzinfo=UTC)
_UNLINKED_AT = datetime(2025, 1, 23, 9, 0, tzinfo=UTC)

type _Stored = tuple[dict[str, Transaction], dict[str, Invoice], frozenset[str]]


@dataclass(frozen=True, slots=True)
class _Profile:
    objects: SecureObjectRepository

    @contextmanager
    def ports(self) -> Generator[LedgerActionPorts]:
        with ledger_ports_for_test(
            bucket_id=_BUCKET,
            objects=self.objects,
            transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET, objects=self.objects),
            bucket_event_repository=BucketEventHistoryRepository(objects=self.objects),
            invoice_repository=InvoiceCatalogueRepository(bucket_id=_BUCKET, objects=self.objects),
        ) as ports:
            yield ports

    def row(self, transaction_id: str) -> Transaction:
        stored = TransactionCatalogueRepository(bucket_id=_BUCKET, objects=self.objects).load().get(transaction_id)
        assert stored is not None
        return stored

    def invoice(self, invoice_id: str) -> Invoice:
        stored = InvoiceCatalogueRepository(bucket_id=_BUCKET, objects=self.objects).load().get(invoice_id)
        assert stored is not None
        return stored

    def events(self) -> dict[str, BucketEvent]:
        return dict(BucketEventHistoryRepository(objects=self.objects).load().events)

    def stored(self) -> _Stored:
        transactions = TransactionCatalogueRepository(bucket_id=_BUCKET, objects=self.objects).load().transactions
        invoices = InvoiceCatalogueRepository(bucket_id=_BUCKET, objects=self.objects).load().invoices
        return dict(transactions), dict(invoices), frozenset(self.events())


@pytest.fixture
def profile(tmp_path: Path) -> Generator[_Profile]:
    with isolated_runtime_profile(tmp_path=tmp_path / "profile", bucket_id=_BUCKET) as runtime:
        yield _Profile(objects=runtime.repository)


def _seed_invoice(profile: _Profile, number: str) -> Invoice:
    repository = InvoiceCatalogueRepository(bucket_id=_BUCKET, objects=profile.objects)
    invoice = synthetic_invoice(number)
    repository.save(build_invoice_catalogue([*repository.load().invoices.values(), invoice]))
    return invoice


def _movement(profile: _Profile, key: str) -> str:
    with profile.ports() as ports:
        created = create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=_BUCKET,
                booked_date=date(2025, 1, 21),
                amount=Decimal("121.00"),
                direction=TransactionDirection.OUTGOING,
                description=f"synthetic supplier payment {key}",
                idempotency_key=key,
            ),
            ports=ports,
        )
    return created.ref.transaction_id


def _linked(profile: _Profile, key: str, *, number: str | None = None) -> tuple[str, Invoice]:
    invoice = _seed_invoice(profile, number or f"SYNTHETIC-{key.upper()}")
    transaction_id = _movement(profile, key)
    with profile.ports() as ports:
        link_manual_transaction_invoice(
            bucket_id=_BUCKET,
            transaction_id=transaction_id,
            invoice_id=invoice.invoice_id,
            actor="synthetic-person",
            ports=ports,
            occurred_at=_LINKED_AT,
        )
    return transaction_id, invoice


def _unlink(
    profile: _Profile,
    transaction_id: str,
    invoice_id: str,
    *,
    expected_modified_at: datetime | None = None,
    expected_links: tuple[str, ...] | None = None,
) -> InvoiceUnlinkResult:
    with profile.ports() as ports:
        return unlink_manual_transaction_invoice(
            bucket_id=_BUCKET,
            transaction_id=transaction_id,
            invoice_id=invoice_id,
            expected_modified_at=expected_modified_at or profile.row(transaction_id).modified_at,
            expected_invoice_linked_transaction_ids=(
                profile.invoice(invoice_id).linked_transaction_ids if expected_links is None else expected_links
            ),
            actor="synthetic-person",
            source_command="aeat app ledger unlink",
            ports=ports,
            occurred_at=_UNLINKED_AT,
        )


def _refused(
    profile: _Profile,
    transaction_id: str,
    invoice_id: str,
    *,
    expected_modified_at: datetime | None = None,
    expected_links: tuple[str, ...] | None = None,
) -> InvoiceUnlinkRefusedError:
    before = profile.stored()
    with pytest.raises(InvoiceUnlinkRefusedError) as refused:
        _unlink(
            profile,
            transaction_id,
            invoice_id,
            expected_modified_at=expected_modified_at,
            expected_links=expected_links,
        )
    assert profile.stored() == before
    return refused.value


def _events_of_type(profile: _Profile, event_type: BucketEventType) -> list[BucketEvent]:
    return [event for event in profile.events().values() if event.event_type is event_type]


def test_unlink_clears_both_sides_and_records_the_removal_beside_the_link(profile: _Profile) -> None:
    transaction_id, invoice = _linked(profile, "both-sides")
    assert profile.row(transaction_id).invoice_id == invoice.invoice_id
    assert profile.invoice(invoice.invoice_id).linked_transaction_ids == (transaction_id,)
    (link_event,) = _events_of_type(profile, BucketEventType.LEDGER_TRANSACTION_INVOICE_LINKED)

    result = _unlink(profile, transaction_id, invoice.invoice_id)

    assert profile.row(transaction_id).invoice_id is None
    assert profile.invoice(invoice.invoice_id).linked_transaction_ids == ()
    assert result.transaction.invoice_id is None
    assert result.invoice.linked_transaction_ids == ()
    (unlink_event,) = _events_of_type(profile, BucketEventType.LEDGER_TRANSACTION_INVOICE_UNLINKED)
    assert result.bucket_event_ids == (unlink_event.event_id,)
    assert unlink_event.object_type is BucketEventObjectType.LEDGER_TRANSACTION
    assert unlink_event.object_id == transaction_id
    assert unlink_event.actor == "synthetic-person"
    assert unlink_event.payload["invoice_id"] == invoice.invoice_id
    assert unlink_event.payload["mutation_kind"] == "invoice_unlinkage"
    assert unlink_event.occurred_at == _UNLINKED_AT
    # The history is appended to: the link's own event is still there.
    assert _events_of_type(profile, BucketEventType.LEDGER_TRANSACTION_INVOICE_LINKED) == [link_event]


def test_unlink_keeps_the_invoices_other_links(profile: _Profile) -> None:
    first, invoice = _linked(profile, "first-payment")
    second = _movement(profile, "second-payment")
    with profile.ports() as ports:
        link_manual_transaction_invoice(
            bucket_id=_BUCKET, transaction_id=second, invoice_id=invoice.invoice_id, ports=ports
        )

    result = _unlink(profile, first, invoice.invoice_id)

    assert profile.invoice(invoice.invoice_id).linked_transaction_ids == (second,)
    assert profile.row(second).invoice_id == invoice.invoice_id
    assert result.invoice.linked_transaction_ids == (second,)


def test_a_removed_link_can_be_linked_again(profile: _Profile) -> None:
    transaction_id, invoice = _linked(profile, "relink")
    _unlink(profile, transaction_id, invoice.invoice_id)

    with profile.ports() as ports:
        link_manual_transaction_invoice(
            bucket_id=_BUCKET, transaction_id=transaction_id, invoice_id=invoice.invoice_id, ports=ports
        )

    assert profile.row(transaction_id).invoice_id == invoice.invoice_id
    assert profile.invoice(invoice.invoice_id).linked_transaction_ids == (transaction_id,)


def test_a_repeated_unlink_finds_no_link_and_changes_nothing(profile: _Profile) -> None:
    transaction_id, invoice = _linked(profile, "repeat")
    _unlink(profile, transaction_id, invoice.invoice_id)

    refusal = _refused(profile, transaction_id, invoice.invoice_id)

    assert refusal.cause is InvoiceUnlinkCause.LINK_NOT_FOUND
    assert refusal.next_step is InvoiceUnlinkNextStep.REOPEN_TRANSACTION
    assert len(_events_of_type(profile, BucketEventType.LEDGER_TRANSACTION_INVOICE_UNLINKED)) == 1


def test_a_movement_linked_to_another_invoice_is_refused(profile: _Profile) -> None:
    transaction_id, _invoice = _linked(profile, "other-invoice")
    unrelated = _seed_invoice(profile, "SYNTHETIC-UNRELATED")

    refusal = _refused(profile, transaction_id, unrelated.invoice_id)

    assert refusal.cause is InvoiceUnlinkCause.LINK_NOT_FOUND


def test_an_unknown_invoice_is_refused(profile: _Profile) -> None:
    transaction_id, _invoice = _linked(profile, "unknown-invoice")

    refusal = _refused(profile, transaction_id, "f" * 64, expected_links=())

    assert refusal.cause is InvoiceUnlinkCause.LINK_NOT_FOUND


def test_a_movement_changed_since_it_was_opened_is_refused(profile: _Profile) -> None:
    transaction_id, invoice = _linked(profile, "stale-movement")
    opened_at = profile.row(transaction_id).modified_at - timedelta(seconds=1)

    refusal = _refused(profile, transaction_id, invoice.invoice_id, expected_modified_at=opened_at)

    assert refusal.cause is InvoiceUnlinkCause.TRANSACTION_CHANGED
    assert refusal.next_step is InvoiceUnlinkNextStep.REOPEN_TRANSACTION


def test_an_invoice_whose_links_changed_since_it_was_opened_is_refused(profile: _Profile) -> None:
    transaction_id, invoice = _linked(profile, "stale-invoice")
    seen = profile.invoice(invoice.invoice_id).linked_transaction_ids
    other = _movement(profile, "stale-invoice-other")
    with profile.ports() as ports:
        link_manual_transaction_invoice(
            bucket_id=_BUCKET, transaction_id=other, invoice_id=invoice.invoice_id, ports=ports
        )

    refusal = _refused(profile, transaction_id, invoice.invoice_id, expected_links=seen)

    assert refusal.cause is InvoiceUnlinkCause.INVOICE_CHANGED
    assert refusal.next_step is InvoiceUnlinkNextStep.REOPEN_INVOICE


def test_a_link_a_finalized_calculation_sealed_is_refused_naming_the_revision(profile: _Profile) -> None:
    transaction_id, invoice = _linked(profile, "sealed")
    with profile.ports() as ports:
        persist_verified_revision_citing_transaction(
            profile.objects, transaction_id=transaction_id, bucket_id=_BUCKET, operation=ports.operation
        )

    refusal = _refused(profile, transaction_id, invoice.invoice_id)

    assert refusal.cause is InvoiceUnlinkCause.FINALIZED_CALCULATION_REFERENCE
    assert refusal.next_step is InvoiceUnlinkNextStep.REOPEN_FINALIZED_CALCULATION
    assert len(refusal.blockers) == 1
    assert profile.row(transaction_id).invoice_id == invoice.invoice_id


def test_a_link_held_only_by_the_movement_is_removed(profile: _Profile) -> None:
    transaction_id, invoice = _linked(profile, "movement-side")
    invoices = InvoiceCatalogueRepository(bucket_id=_BUCKET, objects=profile.objects)
    stored = invoices.load()
    one_sided = stored.invoices[invoice.invoice_id].model_copy(update={"linked_transaction_ids": ()})
    invoices.save(build_invoice_catalogue([one_sided]))

    _unlink(profile, transaction_id, invoice.invoice_id, expected_links=())

    assert profile.row(transaction_id).invoice_id is None
    assert profile.invoice(invoice.invoice_id).linked_transaction_ids == ()


def _paid_transaction_ids(profile: _Profile) -> frozenset[str]:
    """The movements the IVA invoice side counts as paying an invoice, as calculation reads them."""
    window = TransactionCatalogueRepository(bucket_id=_BUCKET, objects=profile.objects).load()
    stored = InvoiceCatalogueRepository(bucket_id=_BUCKET, objects=profile.objects).load()
    invoices = with_movement_side_links(tuple(stored.invoices.values()), window=window)
    with profile.ports() as ports:
        return partition_invoice_payments(
            invoices, bucket_id=_BUCKET, linked_movements=window, operation=ports.operation
        ).paid_transaction_ids


def test_after_unlink_the_movement_no_longer_pays_the_invoice(profile: _Profile) -> None:
    transaction_id, invoice = _linked(profile, "derived")
    assert transaction_id in _paid_transaction_ids(profile)

    _unlink(profile, transaction_id, invoice.invoice_id)

    assert transaction_id not in _paid_transaction_ids(profile)


class _Recorder:
    """The operation host's executor surface, recording effects and keeping each operand."""

    def __init__(self, operation: PinnedAuthorityOperation) -> None:
        self.effects: list[OperationEffect] = []
        self.operands: list[BaseModel] = []
        self._operation = operation

    def context(self) -> OperationExecutorContext:
        recorder = self

        class Cancellation:
            @asynccontextmanager
            async def irreversible_section(self):
                yield

        class Events:
            async def phase(self, phase: str) -> None:
                assert phase == LEDGER_UNLINK_OPERATION_DEFINITION_ID

            async def effect(self, effect: OperationEffect) -> None:
                recorder.effects.append(effect)

        class Operands:
            async def put(self, operand: BaseModel, *, written_at: datetime) -> str:
                assert written_at.tzinfo is not None
                recorder.operands.append(operand)
                return "d" * 64

        return cast(
            OperationExecutorContext,
            SimpleNamespace(
                identity=SimpleNamespace(
                    definition_id=LEDGER_UNLINK_OPERATION_DEFINITION_ID,
                    subject_ref=profile_operation_subject(_BUCKET),
                ),
                authority_operation=self._operation,
                cancellation=Cancellation(),
                events=Events(),
                operands=Operands(),
            ),
        )


async def _execute(
    profile: _Profile, transaction_id: str, invoice_id: str, *, invoice_selector: str | None = None
) -> tuple[str | OperationRefusalEvidence, LedgerUnlinkExecutionResult, _Recorder]:
    with profile.ports() as ports:

        def ports_factory(*, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerActionPorts:
            assert bucket_id == _BUCKET and operation is ports.operation
            return ports

        recorder = _Recorder(ports.operation)
        stored_invoice = InvoiceCatalogueRepository(bucket_id=_BUCKET, objects=profile.objects).load().get(invoice_id)
        outcome = await LedgerUnlinkExecutor(ports_factory).execute(
            OperationRequest[LedgerUnlinkRequest](
                definition_id=LEDGER_UNLINK_OPERATION_DEFINITION_ID,
                subject_ref=profile_operation_subject(_BUCKET),
                payload=LedgerUnlinkRequest(
                    profile_id=_PROFILE,
                    transaction_id=transaction_id[:12],
                    invoice_id=invoice_selector or invoice_id,
                    expected_modified_at=profile.row(transaction_id).modified_at.isoformat(),
                    expected_invoice_linked_transaction_ids=(
                        () if stored_invoice is None else stored_invoice.linked_transaction_ids
                    ),
                    actor="synthetic-person",
                ),
            ),
            recorder.context(),
        )
    (operand,) = recorder.operands
    assert isinstance(operand, LedgerUnlinkExecutionResult)
    return outcome, operand, recorder


@pytest.mark.asyncio
async def test_the_registered_unlink_records_the_update_and_serves_the_unlinked_row(profile: _Profile) -> None:
    transaction_id, invoice = _linked(profile, "operation")

    outcome, operand, recorder = await _execute(
        profile, transaction_id, invoice.invoice_id, invoice_selector=invoice.invoice_id[:10]
    )

    result = operand.result
    assert outcome == "d" * 64
    assert recorder.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
    assert result.outcome == "unlinked"
    assert result.invoice_id == invoice.invoice_id
    assert result.actor == "synthetic-person"
    assert result.transaction is not None
    assert result.transaction.transaction_id == transaction_id
    assert result.transaction.invoice_id is None
    assert result.invoice_linked_transaction_ids == ()
    (unlink_event,) = _events_of_type(profile, BucketEventType.LEDGER_TRANSACTION_INVOICE_UNLINKED)
    assert result.bucket_event_ids == (unlink_event.event_id,)


@pytest.mark.asyncio
async def test_the_registered_unlink_returns_a_typed_refusal_with_no_effect(profile: _Profile) -> None:
    transaction_id, invoice = _linked(profile, "operation-sealed")
    with profile.ports() as ports:
        persist_verified_revision_citing_transaction(
            profile.objects, transaction_id=transaction_id, bucket_id=_BUCKET, operation=ports.operation
        )
    before = profile.stored()

    outcome, operand, recorder = await _execute(profile, transaction_id, invoice.invoice_id)

    assert isinstance(outcome, OperationRefusalEvidence)
    assert outcome.refusal_code == LEDGER_UNLINK_REFUSAL_CODE
    assert recorder.effects == [OperationEffect.UNKNOWN, OperationEffect.NONE]
    refusal = operand.result.refusal
    assert refusal is not None
    assert refusal.cause is InvoiceUnlinkCause.FINALIZED_CALCULATION_REFERENCE
    assert refusal.next_step is InvoiceUnlinkNextStep.REOPEN_FINALIZED_CALCULATION
    assert len(refusal.finalized_revisions) == 1
    assert profile.stored() == before


@pytest.mark.asyncio
async def test_the_registered_unlink_refuses_an_unknown_invoice_before_any_write(profile: _Profile) -> None:
    transaction_id, _invoice = _linked(profile, "operation-unknown")
    before = profile.stored()

    outcome, operand, recorder = await _execute(profile, transaction_id, "f" * 64)

    assert isinstance(outcome, OperationRefusalEvidence)
    assert recorder.effects == [OperationEffect.NONE]
    refusal = operand.result.refusal
    assert refusal is not None
    assert refusal.cause is InvoiceUnlinkCause.LINK_NOT_FOUND
    assert profile.stored() == before
