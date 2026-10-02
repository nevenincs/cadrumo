"""Encrypted canonical fixtures for registered ledger lifecycle operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from ...application.ledger.actions_common import build_manual_ledger_result
from ...application.ledger.actions_lifecycle import archive_manual_transaction
from ...application.ledger.actions_manual import create_manual_transaction, ledger_transaction_result_payload
from ...application.ledger.lifecycle_mutation_operation import (
    LEDGER_ARCHIVE_OPERATION_DEFINITION_ID,
    LEDGER_EXCLUDE_OPERATION_DEFINITION_ID,
    LEDGER_RESTORE_OPERATION_DEFINITION_ID,
    LEDGER_STASH_OPERATION_DEFINITION_ID,
    LedgerLifecycleMutationProjection,
    LedgerLifecycleMutationRequest,
    LedgerLifecycleOperationId,
)
from ...application.ledger.models import ManualLedgerTransactionCommand
from ...application.ledger.transaction_projection import LedgerTransactionProjection
from ...core.operations import OperationEffect
from ...domain.buckets.event import BucketEventHistoryCatalogue, BucketEventObjectType, BucketEventType
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.transactions.enums import TransactionDirection, TransactionLifecycleState
from ...domain.transactions.models import Transaction
from ..ledger_action_composition import compose_ledger_action_ports

_SEED_AT = datetime(2026, 5, 8, 10, 15, tzinfo=UTC)
_ACTOR = "registered-lifecycle-conformance"
_REASON = "registered lifecycle operation conformance"

_ACTION: dict[LedgerLifecycleOperationId, Literal["archive", "stash", "restore", "exclude"]] = {
    LEDGER_ARCHIVE_OPERATION_DEFINITION_ID: "archive",
    LEDGER_STASH_OPERATION_DEFINITION_ID: "stash",
    LEDGER_RESTORE_OPERATION_DEFINITION_ID: "restore",
    LEDGER_EXCLUDE_OPERATION_DEFINITION_ID: "exclude",
}
_EVENT_TYPE: dict[LedgerLifecycleOperationId, BucketEventType] = {
    LEDGER_ARCHIVE_OPERATION_DEFINITION_ID: BucketEventType.LEDGER_TRANSACTION_ARCHIVED,
    LEDGER_STASH_OPERATION_DEFINITION_ID: BucketEventType.LEDGER_TRANSACTION_STASHED,
    LEDGER_RESTORE_OPERATION_DEFINITION_ID: BucketEventType.LEDGER_TRANSACTION_RESTORED,
    LEDGER_EXCLUDE_OPERATION_DEFINITION_ID: BucketEventType.LEDGER_TRANSACTION_REVIEWED_EXCLUDED,
}
_TARGET_STATE: dict[LedgerLifecycleOperationId, TransactionLifecycleState] = {
    LEDGER_ARCHIVE_OPERATION_DEFINITION_ID: TransactionLifecycleState.ARCHIVED,
    LEDGER_STASH_OPERATION_DEFINITION_ID: TransactionLifecycleState.STASHED,
    LEDGER_RESTORE_OPERATION_DEFINITION_ID: TransactionLifecycleState.ACTIVE,
    LEDGER_EXCLUDE_OPERATION_DEFINITION_ID: TransactionLifecycleState.ACTIVE,
}


@dataclass(frozen=True, slots=True)
class LedgerLifecycleOperationConformanceCase:
    """One operation request and its exact encrypted before-state."""

    action: Literal["archive", "stash", "restore", "exclude"]
    definition_id: LedgerLifecycleOperationId
    request: LedgerLifecycleMutationRequest
    expected_effect: OperationEffect
    profile_id: UUID
    transaction_id: str
    transaction_before: Transaction
    history_before: BucketEventHistoryCatalogue
    operation: PinnedAuthorityOperation


def prepare_ledger_lifecycle_operation_conformance_case(
    definition_id: LedgerLifecycleOperationId,
    profile_id: UUID,
    *,
    operation: PinnedAuthorityOperation,
) -> LedgerLifecycleOperationConformanceCase:
    """Persist a canonical transaction and prepare the requested transition."""
    if definition_id not in _ACTION:
        raise ValueError(f"unsupported ledger lifecycle operation definition: {definition_id}")

    bucket_id = str(profile_id)
    ports = compose_ledger_action_ports(bucket_id=bucket_id, operation=operation)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=bucket_id,
            booked_date=_SEED_AT.date(),
            amount=Decimal("123.45"),
            direction=TransactionDirection.OUTGOING,
            description="Registered lifecycle operation conformance row",
            actor=_ACTOR,
            idempotency_key=f"lifecycle-conformance-{profile_id}-{definition_id}",
        ),
        ports=ports,
        occurred_at=_SEED_AT,
    )
    transaction_id = created.ref.transaction_id
    action = _ACTION[definition_id]
    if action == "restore":
        archive_manual_transaction(
            bucket_id=bucket_id,
            transaction_id=transaction_id,
            actor="conformance-seed",
            reason="prepare registered restore",
            source_command="aeat app ledger archive",
            ports=ports,
            occurred_at=_SEED_AT + timedelta(minutes=1),
        )

    transaction_before = ports.transaction_repository.load().get(transaction_id)
    if transaction_before is None:
        raise RuntimeError("canonical lifecycle conformance transaction disappeared during setup")
    expected_before = TransactionLifecycleState.ARCHIVED if action == "restore" else TransactionLifecycleState.ACTIVE
    if transaction_before.lifecycle_state is not expected_before:
        raise RuntimeError("canonical lifecycle conformance seed has the wrong starting state")
    history_before = ports.bucket_event_repository.load()
    request = LedgerLifecycleMutationRequest(
        profile_id=profile_id,
        transaction_id=transaction_id,
        actor="operator",
        reason=_REASON,
    )
    return LedgerLifecycleOperationConformanceCase(
        action=action,
        definition_id=definition_id,
        request=request,
        expected_effect=OperationEffect.UPDATED,
        profile_id=profile_id,
        transaction_id=transaction_id,
        transaction_before=transaction_before,
        history_before=history_before,
        operation=operation,
    )


def assert_ledger_lifecycle_operation_conformance_result(
    case: LedgerLifecycleOperationConformanceCase,
    projection: BaseModel,
    *,
    operation_run_id: str,
) -> None:
    """Compare the complete projection, encrypted row, and appended event."""
    assert len(operation_run_id) == 64
    assert all(character in "0123456789abcdef" for character in operation_run_id)
    assert isinstance(projection, LedgerLifecycleMutationProjection)
    assert projection.profile_id == case.profile_id
    assert projection.operation_id == case.definition_id
    assert projection.bucket_event_ids and len(projection.bucket_event_ids) == 1

    bucket_id = str(case.profile_id)
    ports = compose_ledger_action_ports(bucket_id=bucket_id, operation=case.operation)
    transaction = ports.transaction_repository.load().get(case.transaction_id)
    assert transaction is not None
    assert transaction.transaction_id == case.transaction_id
    assert transaction.lifecycle_state is _TARGET_STATE[case.definition_id]
    if case.action == "exclude":
        assert transaction.business_classification.value == "REVIEWED_EXCLUDED"
        assert transaction.business_pct is None
    else:
        assert transaction.business_classification == case.transaction_before.business_classification
        assert transaction.business_pct == case.transaction_before.business_pct

    history_after = ports.bucket_event_repository.load()
    assert all(history_after.events.get(event_id) == event for event_id, event in case.history_before.events.items())
    new_events = tuple(
        event for event_id, event in history_after.events.items() if event_id not in case.history_before.events
    )
    assert len(new_events) == 1
    event = new_events[0]
    assert event.bucket_id == bucket_id
    assert event.event_type is _EVENT_TYPE[case.definition_id]
    assert event.object_type is BucketEventObjectType.LEDGER_TRANSACTION
    assert event.object_id == case.transaction_id
    assert event.actor == "operator"
    assert event.payload_version == 1
    if case.action == "exclude":
        expected_payload = {
            "business_classification": "REVIEWED_EXCLUDED",
            "previous_classification": case.transaction_before.business_classification.value,
            "reason": _REASON,
            "source_command": f"aeat app ledger {case.action}",
        }
    else:
        expected_payload = {
            "lifecycle_state": _TARGET_STATE[case.definition_id].value,
            "previous_lifecycle_state": case.transaction_before.lifecycle_state.value,
            "reason": _REASON,
            "source_command": f"aeat app ledger {case.action}",
        }
    assert dict(event.payload) == expected_payload
    assert projection.bucket_event_ids == (event.event_id,)

    canonical = ledger_transaction_result_payload(
        build_manual_ledger_result(bucket_id, transaction, (event.event_id,)),
    )
    expected_projection = LedgerLifecycleMutationProjection(
        profile_id=case.profile_id,
        operation_id=case.definition_id,
        transaction=LedgerTransactionProjection.from_payload(canonical.transaction),
        review_status=canonical.review_status,
        bucket_event_ids=(event.event_id,),
    )
    assert projection == expected_projection


__all__ = [
    "LedgerLifecycleOperationConformanceCase",
    "assert_ledger_lifecycle_operation_conformance_result",
    "prepare_ledger_lifecycle_operation_conformance_case",
]
