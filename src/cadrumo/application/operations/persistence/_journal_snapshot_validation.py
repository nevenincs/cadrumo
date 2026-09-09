"""Private validators for durable operation journal snapshots and event batches."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from ....core.operations import (
    LIFECYCLES_BEFORE_ANY_CANCELLATION_REQUEST,
    LIFECYCLES_BEFORE_EXECUTOR_ENTRY,
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
)
from ....core.time.utc import validate_utc_aware
from ..capabilities import OperationRequestStoragePolicy
from ..secret_submission import OperationSecretRequirement

if TYPE_CHECKING:
    from .journal import OperationPersistedSnapshot


def validate_request_storage(snapshot: OperationPersistedSnapshot) -> None:
    journal_request = snapshot.credential_free_request_json
    if snapshot.request_storage is OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL:
        if journal_request is None or not journal_request:
            raise ValueError("credential-free request storage requires an inline canonical request")
    elif journal_request is not None:
        raise ValueError("secure-reference request storage forbids an inline journal request")


def validate_secret_state(snapshot: OperationPersistedSnapshot) -> None:
    requirement = snapshot.secret_requirement
    entered_at = snapshot.executor_entered_at
    validate_executor_entry(snapshot, entered_at)
    if requirement is None:
        return
    validate_secret_requirement(snapshot, requirement, entered_at)


def validate_executor_entry(snapshot: OperationPersistedSnapshot, entered_at: datetime | None) -> None:
    """Keep executor entry inside the operation timeline and lifecycle."""
    if entered_at is not None:
        validate_utc_aware(entered_at)
        if entered_at < snapshot.started_at or entered_at > snapshot.updated_at:
            raise ValueError("executor entry must fall within the persisted operation timeline")
        if snapshot.lifecycle in LIFECYCLES_BEFORE_EXECUTOR_ENTRY:
            raise ValueError("created or queued operation cannot record executor entry")


def validate_secret_requirement(
    snapshot: OperationPersistedSnapshot,
    requirement: OperationSecretRequirement,
    entered_at: datetime | None,
) -> None:
    """Keep an ephemeral secret requirement bound to its operation."""
    if requirement.identity != snapshot.identity:
        raise ValueError("ephemeral secret requirement does not match operation identity")
    if requirement.revision != 0:
        raise ValueError("ephemeral secret requirement must bind the initial operation revision")
    if requirement.expires_at <= snapshot.started_at:
        raise ValueError("ephemeral secret requirement must expire after operation creation")
    if (
        snapshot.lifecycle is OperationLifecycle.TERMINAL
        and entered_at is None
        and snapshot.effect is not OperationEffect.NONE
    ):
        raise ValueError("pre-entry ephemeral secret settlement must retain none effect")


def validate_deadline_and_cancellation_state(snapshot: OperationPersistedSnapshot) -> None:
    """Keep durable deadline and cooperative-stop facts ordered and correlated."""
    execution_deadline = snapshot.execution_deadline
    cleanup_deadline = snapshot.cleanup_deadline
    requested_at = snapshot.cancellation_requested_at
    acknowledged_at = snapshot.cancellation_acknowledged_at
    validate_deferred_cancellation(snapshot, acknowledged_at)
    validate_safety_timestamps(execution_deadline, cleanup_deadline, requested_at, acknowledged_at)
    validate_execution_deadline(snapshot.started_at, execution_deadline)
    if requested_at is None:
        validate_unrequested_cancellation(cleanup_deadline, acknowledged_at)
        return
    validate_requested_cancellation(snapshot, requested_at, cleanup_deadline, acknowledged_at)


def validate_deferred_cancellation(snapshot: OperationPersistedSnapshot, acknowledged_at: datetime | None) -> None:
    """Require deferred cancellation to retain an active executor handoff."""
    if not snapshot.cancellation_deferred:
        return
    if snapshot.executor_entered_at is None:
        raise ValueError("deferred cancellation requires executor entry")
    if snapshot.lifecycle is OperationLifecycle.TERMINAL:
        raise ValueError("terminal operation cannot defer cancellation")
    if acknowledged_at is not None:
        raise ValueError("acknowledged cancellation cannot remain deferred")


def validate_safety_timestamps(
    execution_deadline: datetime | None,
    cleanup_deadline: datetime | None,
    requested_at: datetime | None,
    acknowledged_at: datetime | None,
) -> None:
    """Require every optional deadline and cancellation timestamp to be UTC-aware."""
    for timestamp in (execution_deadline, cleanup_deadline, requested_at, acknowledged_at):
        if timestamp is not None:
            validate_utc_aware(timestamp)


def validate_execution_deadline(started_at: datetime, execution_deadline: datetime | None) -> None:
    """Require an execution deadline to follow operation creation."""
    if execution_deadline is not None and execution_deadline < started_at:
        raise ValueError("execution deadline cannot precede operation start")


def validate_unrequested_cancellation(cleanup_deadline: datetime | None, acknowledged_at: datetime | None) -> None:
    """Reject cleanup or acknowledgement facts without a cancellation request."""
    if cleanup_deadline is not None:
        raise ValueError("cleanup deadline requires a cancellation request")
    if acknowledged_at is not None:
        raise ValueError("cancellation acknowledgement requires a cancellation request")


def validate_requested_cancellation(
    snapshot: OperationPersistedSnapshot,
    requested_at: datetime,
    cleanup_deadline: datetime | None,
    acknowledged_at: datetime | None,
) -> None:
    """Keep requested cancellation facts ordered through settlement."""
    if requested_at < snapshot.started_at or requested_at > snapshot.updated_at:
        raise ValueError("cancellation request must fall within the persisted operation timeline")
    if cleanup_deadline is None or cleanup_deadline <= requested_at:
        raise ValueError("cancellation request requires a later cleanup deadline")
    if snapshot.lifecycle in LIFECYCLES_BEFORE_ANY_CANCELLATION_REQUEST:
        raise ValueError("cancellation request requires a cancellation or settlement lifecycle")
    validate_cancellation_acknowledgement(snapshot, requested_at, acknowledged_at)
    if snapshot.terminal_condition is OperationTerminalCondition.CANCELLED and acknowledged_at is None:
        raise ValueError("cancelled operation requires a durable cancellation acknowledgement")


def validate_cancellation_acknowledgement(
    snapshot: OperationPersistedSnapshot,
    requested_at: datetime,
    acknowledged_at: datetime | None,
) -> None:
    """Require an acknowledgement to follow a cancellation request."""
    if acknowledged_at is None:
        return
    if acknowledged_at < requested_at or acknowledged_at > snapshot.updated_at:
        raise ValueError("cancellation acknowledgement must follow the request within the operation timeline")
    if snapshot.lifecycle is OperationLifecycle.CANCELLATION_REQUESTED:
        raise ValueError("cancellation acknowledgement requires settlement lifecycle")


def validate_checkpoint_state(snapshot: OperationPersistedSnapshot) -> None:
    validate_idempotency_claim(snapshot)
    validate_pending_interaction(snapshot)
    validate_consumed_interactions(snapshot)


def validate_idempotency_claim(snapshot: OperationPersistedSnapshot) -> None:
    claim = snapshot.idempotency_claim
    if claim is None:
        return
    if claim.operation_id != snapshot.operation_id or claim.definition_id != snapshot.identity.definition_id:
        raise ValueError("idempotency claim does not match persisted operation identity")
    if claim.subject_ref != snapshot.identity.subject_ref or claim.request_reference != snapshot.request_reference:
        raise ValueError("idempotency claim does not match persisted request identity")


def validate_pending_interaction(snapshot: OperationPersistedSnapshot) -> None:
    pending = snapshot.pending_interaction
    if pending is None:
        return
    if snapshot.lifecycle is not OperationLifecycle.WAITING_FOR_INTERACTION:
        raise ValueError("pending interaction requires waiting-for-interaction lifecycle")
    if pending.request.identity != snapshot.identity or pending.request.revision != snapshot.revision:
        raise ValueError("pending interaction does not match persisted operation revision")


def validate_consumed_interactions(snapshot: OperationPersistedSnapshot) -> None:
    consumed_ids = tuple(item.interaction_id for item in snapshot.consumed_interactions)
    if len(set(consumed_ids)) != len(consumed_ids):
        raise ValueError("consumed interaction identities must be unique")
    pending = snapshot.pending_interaction
    if pending is not None and pending.request.interaction_id in consumed_ids:
        raise ValueError("pending interaction cannot already be consumed")
