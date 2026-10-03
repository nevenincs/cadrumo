"""Encrypted canonical fixtures for registered ledger-attachment operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from ...adapters.persistence.profile.tests.remove_draft_revision_support import seed_revision_citing_transaction
from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from ...application.ledger.actions_common import blocking_modelo_references, build_manual_ledger_result
from ...application.ledger.actions_manual import (
    attach_manual_transaction_evidence,
    create_manual_transaction,
    ledger_transaction_result_payload,
)
from ...application.ledger.attachment_mutation_operation import (
    LEDGER_ATTACH_OPERATION_DEFINITION_ID,
    LEDGER_DETACH_OPERATION_DEFINITION_ID,
    LedgerAttachmentOperationId,
    LedgerAttachmentProjection,
    LedgerAttachmentStaleRevisionProjection,
    LedgerAttachRequest,
    LedgerDetachRequest,
)
from ...application.ledger.models import ManualLedgerTransactionCommand
from ...application.ledger.transaction_projection import LedgerTransactionProjection
from ...core.decimal.formatting import format_decimal
from ...core.operations import OperationEffect
from ...domain.attachments.enums import AttachmentKind, AttachmentSource
from ...domain.attachments.models import Attachment
from ...domain.attachments.service import AttachmentBytesContent, AttachmentIngestionRequest, add_attachment
from ...domain.buckets.event import BucketEventHistoryCatalogue, BucketEventObjectType, BucketEventType
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.modelos.calculation_revision import CalculationRevisionState
from ...domain.transactions.enums import TransactionDirection
from ...domain.transactions.models import Transaction
from ..ledger_action_composition import compose_ledger_action_ports

_ATTACHMENT_BYTES = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
_SEED_AT = datetime(2026, 5, 8, 10, 15, tzinfo=UTC)
_ACTOR = "operation-conformance"
_CONTENT_TYPE = "application/pdf"


@dataclass(frozen=True, slots=True)
class LedgerAttachmentOperationConformanceCase:
    """One request and the exact encrypted before-state for an operation."""

    action: Literal["attach", "detach"]
    definition_id: LedgerAttachmentOperationId
    request: BaseModel
    expected_effect: OperationEffect
    profile_id: UUID
    transaction_id: str
    attachment_id: str
    finalized_revision_id: str
    transaction_before: Transaction
    attachment_before: Attachment
    history_before: BucketEventHistoryCatalogue
    operation: PinnedAuthorityOperation


def prepare_ledger_attachment_operation_conformance_case(
    definition_id: LedgerAttachmentOperationId,
    profile_id: UUID,
    *,
    operation: PinnedAuthorityOperation,
) -> LedgerAttachmentOperationConformanceCase:
    """Seed a canonical encrypted transaction, attachment, and sealed revision."""
    if definition_id not in {
        LEDGER_ATTACH_OPERATION_DEFINITION_ID,
        LEDGER_DETACH_OPERATION_DEFINITION_ID,
    }:
        raise ValueError(f"unsupported ledger attachment operation definition: {definition_id}")

    bucket_id = str(profile_id)
    ports = compose_ledger_action_ports(bucket_id=bucket_id, operation=operation)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=bucket_id,
            booked_date=_SEED_AT.date(),
            amount=Decimal("123.45"),
            direction=TransactionDirection.OUTGOING,
            description="Registered attachment operation conformance row",
            actor=_ACTOR,
            idempotency_key=f"attachment-conformance-{profile_id}",
        ),
        ports=ports,
        occurred_at=_SEED_AT,
    )
    transaction_id = created.ref.transaction_id
    attachment = add_attachment(
        ports.attachment_store,
        content=AttachmentBytesContent(data=_ATTACHMENT_BYTES),
        request=AttachmentIngestionRequest(
            kind=AttachmentKind.INVOICE_PDF,
            source=AttachmentSource.INLINE,
            source_reference=f"attachment-conformance:{profile_id}",
            mime_type=_CONTENT_TYPE,
            captured_at=_SEED_AT,
            bucket_id=bucket_id,
            captured_by=_ACTOR,
            source_command="registered attachment operation conformance seed",
        ),
    )
    finalized_revision_id = seed_revision_citing_transaction(
        secure_object_repository_for_active_bucket(),
        transaction_id=transaction_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        period_code="1T",
        bucket_id=bucket_id,
        operation=operation,
    )

    if definition_id == LEDGER_ATTACH_OPERATION_DEFINITION_ID:
        action: Literal["attach", "detach"] = "attach"
        request: BaseModel = LedgerAttachRequest(
            profile_id=profile_id,
            transaction_id=transaction_id,
            attachment_ids=(attachment.attachment_id,),
            actor="operator",
        )
    else:
        action = "detach"
        attach_manual_transaction_evidence(
            bucket_id=bucket_id,
            transaction_id=transaction_id,
            attachment_ids=(attachment.attachment_id,),
            actor="conformance-seed",
            source_command="aeat app ledger attach",
            ports=ports,
            occurred_at=_SEED_AT,
        )
        request = LedgerDetachRequest(
            profile_id=profile_id,
            transaction_id=transaction_id,
            attachment_ids=(attachment.attachment_id,),
            actor="operator",
        )

    transaction_before = ports.transaction_repository.load().get(transaction_id)
    if transaction_before is None:
        raise RuntimeError("canonical attachment conformance transaction disappeared during setup")
    attachment_before = ports.attachment_store.load_manifest(attachment.attachment_id)
    history_before = ports.bucket_event_repository.load()
    if action == "attach" and transaction_before.attachment_ids:
        raise RuntimeError("attachment conformance attach seed is already linked")
    if action == "detach" and transaction_before.attachment_ids != (attachment.attachment_id,):
        raise RuntimeError("attachment conformance detach seed lacks its canonical transaction link")

    return LedgerAttachmentOperationConformanceCase(
        action=action,
        definition_id=definition_id,
        request=request,
        expected_effect=OperationEffect.UPDATED,
        profile_id=profile_id,
        transaction_id=transaction_id,
        attachment_id=attachment.attachment_id,
        finalized_revision_id=finalized_revision_id,
        transaction_before=transaction_before,
        attachment_before=attachment_before,
        history_before=history_before,
        operation=operation,
    )


def assert_ledger_attachment_operation_conformance_result(
    case: LedgerAttachmentOperationConformanceCase,
    projection: BaseModel,
    *,
    operation_run_id: str,
) -> None:
    """Compare the complete public result, append-only events, and encrypted links."""
    assert len(operation_run_id) == 64
    assert all(character in "0123456789abcdef" for character in operation_run_id)
    assert isinstance(projection, LedgerAttachmentProjection)
    assert projection.profile_id == case.profile_id
    assert projection.operation_id == case.definition_id

    bucket_id = str(case.profile_id)
    ports = compose_ledger_action_ports(bucket_id=bucket_id, operation=case.operation)
    transaction = ports.transaction_repository.load().get(case.transaction_id)
    assert transaction is not None
    assert transaction.transaction_id == case.transaction_id
    expected_transaction_attachments = (case.attachment_id,) if case.action == "attach" else ()
    assert transaction.attachment_ids == expected_transaction_attachments

    history_after = ports.bucket_event_repository.load()
    assert all(history_after.events.get(event_id) == event for event_id, event in case.history_before.events.items())
    new_events = tuple(
        event for event_id, event in history_after.events.items() if event_id not in case.history_before.events
    )
    assert len(new_events) == 1
    event = new_events[0]
    expected_event_type = (
        BucketEventType.ATTACHMENT_LINKED if case.action == "attach" else BucketEventType.ATTACHMENT_REMOVED
    )
    linked = case.action == "attach"
    assert event.bucket_id == bucket_id
    assert event.event_type is expected_event_type
    assert event.object_type is BucketEventObjectType.ATTACHMENT
    assert event.object_id == case.attachment_id
    assert event.actor == "operator"
    assert event.payload_version == 1
    assert dict(event.payload) == {
        "amount": format_decimal(case.transaction_before.raw.amount),
        "currency": case.transaction_before.raw.currency,
        "direction": case.transaction_before.direction.value,
        "linked": "true" if linked else "false",
        "mutation_kind": "attachment_linked" if linked else "attachment_removed",
        "previous_transaction_id": case.transaction_id,
        "source_command": "aeat app ledger attach" if linked else "aeat app ledger detach",
        "transaction_id": case.transaction_id,
    }
    event_ids = (event.event_id,)
    assert projection.bucket_event_ids == event_ids

    attachment = ports.attachment_store.load_manifest(case.attachment_id)
    if case.action == "attach":
        assert attachment.linked_transaction_ids == (case.transaction_id,)
        assert attachment.linked_transaction_ids != case.attachment_before.linked_transaction_ids
    else:
        # Detach removes only the transaction-side pointer. The append-only
        # manifest preserves its historical back-reference and secure bytes.
        assert attachment == case.attachment_before
        assert ports.attachment_store.read_bytes(case.attachment_id) == _ATTACHMENT_BYTES

    blockers = blocking_modelo_references(
        bucket_id=bucket_id,
        transaction_ids=(case.transaction_id,),
        work_unit_repository=ports.work_unit_repository,
        calculation_repository=ports.calculation_repository,
    )
    assert tuple(blocker.calculation_revision_id for blocker in blockers) == (case.finalized_revision_id,)
    stale_projection = tuple(LedgerAttachmentStaleRevisionProjection.from_blocker(blocker) for blocker in blockers)
    assert projection.stale_finalized_revisions == stale_projection

    canonical_payload = ledger_transaction_result_payload(
        build_manual_ledger_result(
            bucket_id,
            transaction,
            event_ids,
            stale_finalized_revisions=blockers,
        ),
    )
    expected_projection = LedgerAttachmentProjection(
        profile_id=case.profile_id,
        operation_id=case.definition_id,
        transaction=LedgerTransactionProjection.from_payload(canonical_payload.transaction),
        review_status=canonical_payload.review_status,
        bucket_event_ids=event_ids,
        stale_finalized_revisions=stale_projection,
    )
    assert projection == expected_projection


__all__ = [
    "LedgerAttachmentOperationConformanceCase",
    "assert_ledger_attachment_operation_conformance_result",
    "prepare_ledger_attachment_operation_conformance_case",
]
