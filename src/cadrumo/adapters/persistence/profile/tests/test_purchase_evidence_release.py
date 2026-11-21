"""Releasing a movement's linked purchase evidence, over real secure storage.

``detach`` clears the slot and leaves the evidence record in the profile;
``keep_as_document`` clears it and keeps the evidence's stored document on the
movement as an ordinary attachment. Each emits the existing detached event in the
same batch as the row. Every refusal is typed, names its next step, and leaves
every stored row and event exactly as it was.
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
from cadrumo.adapters.persistence.profile.purchase_invoice_evidence import LedgerEvidenceRepositoryAdapter
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.attachment import AttachmentStore
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.ledger.action_ports import LedgerActionPorts
from cadrumo.application.ledger.evidence import MediaKind, PurchaseInvoiceEvidence
from cadrumo.application.ledger.manual_update import attach_manual_transaction_evidence
from cadrumo.application.ledger.models import ManualLedgerTransactionCommand
from cadrumo.application.ledger.purchase_evidence_release import (
    PurchaseEvidenceDisposition,
    PurchaseEvidenceReleaseCause,
    PurchaseEvidenceReleaseNextStep,
    PurchaseEvidenceReleaseRefusedError,
    release_manual_transaction_purchase_evidence,
)
from cadrumo.application.ledger.purchase_evidence_release_operation import (
    LEDGER_PURCHASE_EVIDENCE_RELEASE_OPERATION_DEFINITION_ID,
    LEDGER_PURCHASE_EVIDENCE_RELEASE_REFUSAL_CODE,
    LedgerPurchaseEvidenceReleaseExecutionResult,
    LedgerPurchaseEvidenceReleaseExecutor,
    LedgerPurchaseEvidenceReleaseRequest,
)
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.owner import OperationExecutorContext
from cadrumo.application.operations.refusal_evidence import OperationRefusalEvidence
from cadrumo.core.operations import OperationEffect, profile_operation_subject
from cadrumo.domain.attachments.enums import AttachmentKind, AttachmentSource
from cadrumo.domain.attachments.service import (
    AttachmentBytesContent,
    AttachmentIngestionRequest,
    add_attachment,
    link_attachment_invoice,
)
from cadrumo.domain.buckets.event import BucketEventType
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue
from cadrumo.domain.transactions.enums import TransactionDirection
from cadrumo.domain.transactions.models import Transaction

from .....application.ledger.tests.manual_transaction_support import create_manual_transaction
from .classification_origin_support import synthetic_invoice
from .ledger_action_create_support import ledger_ports_for_test
from .ledger_action_persistence_support import persist_verified_revision_citing_transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "43434343-4343-4343-8343-434343434343"
_PROFILE = UUID(_BUCKET)
_AT = datetime(2025, 1, 21, 9, 0, tzinfo=UTC)
_PDF = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\nsynthetic-purchase-evidence\n%%EOF\n"


@dataclass(frozen=True, slots=True)
class _Profile:
    objects: SecureObjectRepository

    @contextmanager
    def ports(self) -> Generator[LedgerActionPorts]:
        """Fresh real ports, so each action reads the evidence records stored before it."""
        with ledger_ports_for_test(
            bucket_id=_BUCKET,
            objects=self.objects,
            transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET, objects=self.objects),
            bucket_event_repository=BucketEventHistoryRepository(objects=self.objects),
            invoice_repository=InvoiceCatalogueRepository(bucket_id=_BUCKET, objects=self.objects),
            attachment_store=AttachmentStore(objects=self.objects),
        ) as ports:
            yield ports

    def row(self, transaction_id: str) -> Transaction:
        stored = TransactionCatalogueRepository(bucket_id=_BUCKET, objects=self.objects).load().get(transaction_id)
        assert stored is not None
        return stored

    def stored(self) -> tuple[dict[str, Transaction], frozenset[str]]:
        transactions = TransactionCatalogueRepository(bucket_id=_BUCKET, objects=self.objects).load().transactions
        return dict(transactions), frozenset(BucketEventHistoryRepository(objects=self.objects).load().events)

    def evidence_ids(self) -> set[str]:
        return {
            record.evidence_id
            for record in LedgerEvidenceRepositoryAdapter(objects=self.objects).load(bucket_id=_BUCKET)
        }


@pytest.fixture
def profile(tmp_path: Path) -> Generator[_Profile]:
    with isolated_runtime_profile(tmp_path=tmp_path / "profile", bucket_id=_BUCKET) as runtime:
        yield _Profile(objects=runtime.repository)


def _store_evidence(profile: _Profile, *, evidence_id: str, marker: bytes) -> str:
    """Store synthetic evidence bytes and the record naming them; return the attachment id."""
    attachment = add_attachment(
        AttachmentStore(objects=profile.objects),
        content=AttachmentBytesContent(data=_PDF + marker),
        request=AttachmentIngestionRequest(
            kind=AttachmentKind.INVOICE_PDF,
            source=AttachmentSource.LOCAL_FILE,
            source_reference="synthetic-evidence",
            mime_type="application/pdf",
            captured_at=_AT,
            bucket_id=_BUCKET,
        ),
    )
    repository = LedgerEvidenceRepositoryAdapter(objects=profile.objects)
    record = PurchaseInvoiceEvidence(
        evidence_id=evidence_id,
        bucket_id=_BUCKET,
        source_path="synthetic/invoice.pdf",
        source_sha256=attachment.attachment_id,
        attachment_id=attachment.attachment_id,
        media_kind=MediaKind.PDF,
        created_at=_AT,
        updated_at=_AT,
    )
    repository.save(bucket_id=_BUCKET, records=(*repository.load(bucket_id=_BUCKET), record))
    return attachment.attachment_id


def _row_with_evidence(profile: _Profile, *, evidence_id: str | None, key: str) -> str:
    with profile.ports() as ports:
        created = create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=_BUCKET,
                booked_date=date(2025, 1, 21),
                amount=Decimal("121.00"),
                direction=TransactionDirection.OUTGOING,
                description=f"synthetic purchase {key}",
                idempotency_key=key,
            ),
            ports=ports,
        )
        transaction_id = created.ref.transaction_id
        if evidence_id is not None:
            attach_manual_transaction_evidence(
                bucket_id=_BUCKET,
                transaction_id=transaction_id,
                purchase_invoice_evidence_id=evidence_id,
                actor="synthetic-person",
                ports=ports,
            )
    return transaction_id


def _release(
    profile: _Profile,
    transaction_id: str,
    *,
    disposition: PurchaseEvidenceDisposition,
    expected_evidence_id: str,
    expected_modified_at: datetime | None = None,
):
    with profile.ports() as ports:
        return release_manual_transaction_purchase_evidence(
            bucket_id=_BUCKET,
            transaction_id=transaction_id,
            expected_purchase_invoice_evidence_id=expected_evidence_id,
            expected_modified_at=expected_modified_at or profile.row(transaction_id).modified_at,
            disposition=disposition,
            actor="synthetic-person",
            source_command="aeat app ledger evidence release",
            ports=ports,
        )


def _events_of(profile: _Profile, event_ids: tuple[str, ...]):
    events = BucketEventHistoryRepository(objects=profile.objects).load().events
    return [events[event_id] for event_id in event_ids]


def _refused(
    profile: _Profile,
    transaction_id: str,
    *,
    disposition: PurchaseEvidenceDisposition,
    expected_evidence_id: str,
    expected_modified_at: datetime | None = None,
) -> PurchaseEvidenceReleaseRefusedError:
    before = profile.stored()
    with pytest.raises(PurchaseEvidenceReleaseRefusedError) as refused:
        _release(
            profile,
            transaction_id,
            disposition=disposition,
            expected_evidence_id=expected_evidence_id,
            expected_modified_at=expected_modified_at,
        )
    assert profile.stored() == before
    return refused.value


def test_detach_clears_the_slot_keeps_the_evidence_and_journals_the_detachment(profile: _Profile) -> None:
    attachment_id = _store_evidence(profile, evidence_id="a1a1a1a1a1a1a1a1", marker=b"detach")
    row = _row_with_evidence(profile, evidence_id="a1a1a1a1a1a1a1a1", key="detach")

    result = _release(profile, row, disposition="detach", expected_evidence_id="a1a1a1a1a1a1a1a1")

    stored = profile.row(row)
    assert stored.purchase_invoice_evidence_id is None
    assert attachment_id not in stored.attachment_ids
    assert "a1a1a1a1a1a1a1a1" in profile.evidence_ids()
    detached = [
        event
        for event in _events_of(profile, result.bucket_event_ids)
        if event.event_type is BucketEventType.PURCHASE_INVOICE_EVIDENCE_DETACHED
    ]
    assert [event.object_id for event in detached] == ["a1a1a1a1a1a1a1a1"]


def test_keep_as_document_moves_the_document_to_the_movements_attachments(profile: _Profile) -> None:
    attachment_id = _store_evidence(profile, evidence_id="b2b2b2b2b2b2b2b2", marker=b"rekind")
    row = _row_with_evidence(profile, evidence_id="b2b2b2b2b2b2b2b2", key="rekind")

    result = _release(profile, row, disposition="keep_as_document", expected_evidence_id="b2b2b2b2b2b2b2b2")

    stored = profile.row(row)
    assert stored.purchase_invoice_evidence_id is None
    assert stored.attachment_ids == (attachment_id,)
    assert "b2b2b2b2b2b2b2b2" in profile.evidence_ids()
    kinds = {event.event_type for event in _events_of(profile, result.bucket_event_ids)}
    assert BucketEventType.PURCHASE_INVOICE_EVIDENCE_DETACHED in kinds
    assert BucketEventType.ATTACHMENT_LINKED in kinds


def test_a_movement_without_purchase_evidence_is_refused(profile: _Profile) -> None:
    row = _row_with_evidence(profile, evidence_id=None, key="bare")

    refusal = _refused(profile, row, disposition="detach", expected_evidence_id="c3c3c3c3c3c3c3c3")

    assert refusal.cause is PurchaseEvidenceReleaseCause.NO_LINKED_PURCHASE_EVIDENCE
    assert refusal.next_step is PurchaseEvidenceReleaseNextStep.REOPEN_TRANSACTION


def test_other_evidence_than_the_person_saw_is_refused(profile: _Profile) -> None:
    _store_evidence(profile, evidence_id="d4d4d4d4d4d4d4d4", marker=b"seen")
    row = _row_with_evidence(profile, evidence_id="d4d4d4d4d4d4d4d4", key="seen")

    refusal = _refused(profile, row, disposition="detach", expected_evidence_id="e5e5e5e5e5e5e5e5")

    assert refusal.cause is PurchaseEvidenceReleaseCause.NO_LINKED_PURCHASE_EVIDENCE


def test_a_movement_changed_since_it_was_opened_is_refused(profile: _Profile) -> None:
    _store_evidence(profile, evidence_id="f6f6f6f6f6f6f6f6", marker=b"stale")
    row = _row_with_evidence(profile, evidence_id="f6f6f6f6f6f6f6f6", key="stale")
    opened_at = profile.row(row).modified_at - timedelta(seconds=1)

    refusal = _refused(
        profile,
        row,
        disposition="detach",
        expected_evidence_id="f6f6f6f6f6f6f6f6",
        expected_modified_at=opened_at,
    )

    assert refusal.cause is PurchaseEvidenceReleaseCause.TRANSACTION_CHANGED
    assert refusal.next_step is PurchaseEvidenceReleaseNextStep.REOPEN_TRANSACTION


@pytest.mark.parametrize("disposition", ["detach", "keep_as_document"])
def test_a_movement_a_finalized_calculation_cites_is_refused_naming_the_revision(
    profile: _Profile, disposition: PurchaseEvidenceDisposition
) -> None:
    _store_evidence(profile, evidence_id="0a0a0a0a0a0a0a0a", marker=b"sealed")
    row = _row_with_evidence(profile, evidence_id="0a0a0a0a0a0a0a0a", key=f"sealed-{disposition}")
    with profile.ports() as ports:
        persist_verified_revision_citing_transaction(
            profile.objects, transaction_id=row, bucket_id=_BUCKET, operation=ports.operation
        )

    refusal = _refused(profile, row, disposition=disposition, expected_evidence_id="0a0a0a0a0a0a0a0a")

    assert refusal.cause is PurchaseEvidenceReleaseCause.FINALIZED_CALCULATION_REFERENCE
    assert refusal.next_step is PurchaseEvidenceReleaseNextStep.REOPEN_FINALIZED_CALCULATION
    assert len(refusal.blockers) == 1


def test_detaching_evidence_confirmed_into_an_invoice_the_movement_does_not_link_is_refused(
    profile: _Profile,
) -> None:
    attachment_id = _store_evidence(profile, evidence_id="1b1b1b1b1b1b1b1b", marker=b"confirmed")
    invoice = synthetic_invoice("SYNTHETIC-CONFIRMED-1")
    InvoiceCatalogueRepository(bucket_id=_BUCKET, objects=profile.objects).save(build_invoice_catalogue([invoice]))
    link_attachment_invoice(
        AttachmentStore(objects=profile.objects), attachment_id=attachment_id, invoice_id=invoice.invoice_id
    )
    row = _row_with_evidence(profile, evidence_id="1b1b1b1b1b1b1b1b", key="confirmed")

    refusal = _refused(profile, row, disposition="detach", expected_evidence_id="1b1b1b1b1b1b1b1b")

    assert refusal.cause is PurchaseEvidenceReleaseCause.EVIDENCE_CONFIRMED_INTO_INVOICE
    assert refusal.next_step is PurchaseEvidenceReleaseNextStep.LINK_MOVEMENT_TO_INVOICE
    assert refusal.invoice_ids == (invoice.invoice_id,)

    # Kept as an ordinary document it still leads to the invoice, so that is admitted.
    _release(profile, row, disposition="keep_as_document", expected_evidence_id="1b1b1b1b1b1b1b1b")
    assert profile.row(row).attachment_ids == (attachment_id,)


def test_a_catalogue_invoice_reference_has_no_document_to_keep_but_can_be_detached(profile: _Profile) -> None:
    invoice = synthetic_invoice("SYNTHETIC-REFERENCE-1")
    InvoiceCatalogueRepository(bucket_id=_BUCKET, objects=profile.objects).save(build_invoice_catalogue([invoice]))
    row = _row_with_evidence(profile, evidence_id=invoice.invoice_id, key="catalogue")

    refusal = _refused(profile, row, disposition="keep_as_document", expected_evidence_id=invoice.invoice_id)
    assert refusal.cause is PurchaseEvidenceReleaseCause.REFERENCE_HAS_NO_STORED_DOCUMENT
    assert refusal.next_step is PurchaseEvidenceReleaseNextStep.DETACH_INSTEAD

    _release(profile, row, disposition="detach", expected_evidence_id=invoice.invoice_id)
    assert profile.row(row).purchase_invoice_evidence_id is None


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
                assert phase == LEDGER_PURCHASE_EVIDENCE_RELEASE_OPERATION_DEFINITION_ID

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
                    definition_id=LEDGER_PURCHASE_EVIDENCE_RELEASE_OPERATION_DEFINITION_ID,
                    subject_ref=profile_operation_subject(_BUCKET),
                ),
                authority_operation=self._operation,
                cancellation=Cancellation(),
                events=Events(),
                operands=Operands(),
            ),
        )


async def _execute(
    profile: _Profile, transaction_id: str, *, expected_evidence_id: str, disposition: PurchaseEvidenceDisposition
) -> tuple[str | OperationRefusalEvidence, LedgerPurchaseEvidenceReleaseExecutionResult, _Recorder]:
    with profile.ports() as ports:

        def ports_factory(*, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerActionPorts:
            assert bucket_id == _BUCKET and operation is ports.operation
            return ports

        recorder = _Recorder(ports.operation)
        outcome = await LedgerPurchaseEvidenceReleaseExecutor(ports_factory).execute(
            OperationRequest[LedgerPurchaseEvidenceReleaseRequest](
                definition_id=LEDGER_PURCHASE_EVIDENCE_RELEASE_OPERATION_DEFINITION_ID,
                subject_ref=profile_operation_subject(_BUCKET),
                payload=LedgerPurchaseEvidenceReleaseRequest(
                    profile_id=_PROFILE,
                    transaction_id=transaction_id[:12],
                    expected_purchase_invoice_evidence_id=expected_evidence_id,
                    expected_modified_at=profile.row(transaction_id).modified_at.isoformat(),
                    disposition=disposition,
                ),
            ),
            recorder.context(),
        )
    (operand,) = recorder.operands
    assert isinstance(operand, LedgerPurchaseEvidenceReleaseExecutionResult)
    return outcome, operand, recorder


@pytest.mark.asyncio
async def test_the_registered_release_records_the_update_and_serves_the_released_row(profile: _Profile) -> None:
    attachment_id = _store_evidence(profile, evidence_id="2c2c2c2c2c2c2c2c", marker=b"operation")
    row = _row_with_evidence(profile, evidence_id="2c2c2c2c2c2c2c2c", key="operation")

    outcome, operand, recorder = await _execute(
        profile, row, expected_evidence_id="2c2c2c2c2c2c2c2c", disposition="keep_as_document"
    )

    assert outcome == "d" * 64
    assert recorder.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
    result = operand.result
    assert result.outcome == "updated"
    assert result.transaction is not None
    assert result.transaction.purchase_invoice_evidence_id is None
    assert result.transaction.attachment_ids == (attachment_id,)
    assert result.released_evidence_id == "2c2c2c2c2c2c2c2c"


@pytest.mark.asyncio
async def test_the_registered_release_returns_a_typed_refusal_with_no_effect(profile: _Profile) -> None:
    row = _row_with_evidence(profile, evidence_id=None, key="operation-refused")
    before = profile.stored()

    outcome, operand, recorder = await _execute(
        profile, row, expected_evidence_id="3d3d3d3d3d3d3d3d", disposition="detach"
    )

    assert isinstance(outcome, OperationRefusalEvidence)
    assert outcome.refusal_code == LEDGER_PURCHASE_EVIDENCE_RELEASE_REFUSAL_CODE
    assert recorder.effects == [OperationEffect.UNKNOWN, OperationEffect.NONE]
    refusal = operand.result.refusal
    assert refusal is not None
    assert refusal.cause is PurchaseEvidenceReleaseCause.NO_LINKED_PURCHASE_EVIDENCE
    assert refusal.next_step is PurchaseEvidenceReleaseNextStep.REOPEN_TRANSACTION
    assert profile.stored() == before
