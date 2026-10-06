"""Credential-free settlement after the host confirms native owner termination."""

from __future__ import annotations

from datetime import datetime

from ...core.hex import Hex64Str
from ...core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition
from ._supervisor_settlement import SupervisorSettlementMixin
from .models import OperationId, OperationReconciliationOutcome, OperationTerminalReceipt
from .persistence.events import OperationReconciliationEvent, OperationTerminalEvent
from .persistence.journal import OperationJournal, OperationLeaseRepository
from .persistence.leases import OperationLeaseObservationDisposition, operation_conflict_scope_reference
from .registry import OperationRegistry


async def settle_terminated_operation(
    *,
    operation_id: OperationId,
    terminated_owner_id: Hex64Str,
    journal: OperationJournal,
    leases: OperationLeaseRepository,
    registry: OperationRegistry,
    observed_at: datetime,
) -> bool:
    """Settle only the exact live lease belonging to a confirmed dead owner.

    The host must first fence admission and confirm native containment for this
    owner. The owner ID alone is not termination proof. Foreign and absent
    leases are untouched. Expired leases remain with ordinary reconciliation.
    No operand, profile key, lease renewal or executor is used here.
    """
    snapshot = await journal.load(operation_id)
    observation = await leases.inspect(
        operation_conflict_scope_reference(
            definition_id=snapshot.identity.definition_id, subject_ref=snapshot.identity.subject_ref
        ),
        operation_id,
        observed_at=observed_at,
    )
    lease = observation.current
    if lease is None or lease.owner_id != terminated_owner_id or lease.operation_id != operation_id:
        return False
    if observation.disposition is not OperationLeaseObservationDisposition.ACTIVE:
        raise ValueError("terminated operation lease expired before settlement")
    if snapshot.lifecycle is OperationLifecycle.TERMINAL:
        # A crash between terminal persistence and lease removal can leave the
        # exact dead owner's lease. Release compares the complete predecessor.
        result = await leases.release(lease, observed_at=observed_at)
        if result.current is not None:
            raise ValueError("terminated operation lease changed before release")
        return True
    definition = registry.lookup(snapshot.identity.definition_id)
    contract = registry.lookup_public_contract(snapshot.identity.definition_id)
    if contract.definition_contract_digest != snapshot.definition_contract_digest:
        raise ValueError("terminated operation definition contract changed")
    effect = OperationEffect.NONE if snapshot.executor_entered_at is None else OperationEffect.UNKNOWN
    if effect not in definition.capabilities.permitted_effects:
        raise ValueError("terminated operation effect is not declared")
    receipt = OperationTerminalReceipt(
        identity=snapshot.identity,
        revision=snapshot.revision + 1,
        condition=OperationTerminalCondition.INTERRUPTED,
        effect=effect,
        settled_at=observed_at,
    )
    events = (
        OperationReconciliationEvent(
            identity=snapshot.identity,
            revision=receipt.revision,
            sequence=snapshot.event_cursor + 1,
            timestamp=observed_at,
            code="operation.reconciliation",
            outcome=OperationReconciliationOutcome.ORPHANED,
            lease_evidence_ref=observation.evidence_ref,
        ),
        OperationTerminalEvent(
            identity=snapshot.identity,
            revision=receipt.revision,
            sequence=snapshot.event_cursor + 2,
            timestamp=observed_at,
            code="operation.terminal",
            receipt=receipt,
        ),
    )
    successor = SupervisorSettlementMixin._settlement_successor(snapshot, receipt, events)
    # Journal revision and complete lease are checked in one exclusion before
    # terminal persistence and release. A raced takeover cannot be deleted.
    await journal.commit_settlement(successor, expected_revision=snapshot.revision, lease=lease)
    return True
