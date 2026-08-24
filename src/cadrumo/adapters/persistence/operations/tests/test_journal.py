"""Real-filesystem contracts for the operation journal adapter."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from .....application.operations import (
    OperationApplyResponse,
    OperationConsumedInteraction,
    OperationIdempotencyClaim,
    OperationIdentity,
    OperationInteractionRequest,
    OperationLeaseDisposition,
    OperationOwnerLease,
    OperationPendingInteraction,
    OperationPersistedSnapshot,
    OperationPhaseEvent,
    OperationReplayStatus,
    OperationRequestStoragePolicy,
    OperationTerminalEvent,
    OperationTerminalReceipt,
    operation_conflict_scope_reference,
)
from .....core import (
    OperationEffect,
    OperationInteractionKind,
    OperationLifecycle,
    OperationTerminalCondition,
    scan_directory,
)
from ...storage import RepositoryError
from .._journal import OperationJournalRepository
from .._lease import OperationLeaseFilesystemRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_STARTED = datetime(2026, 8, 13, 20, tzinfo=UTC)


def _snapshot(*, revision: int, sequence: int) -> OperationPersistedSnapshot:
    identity = OperationIdentity(operation_id="a" * 64, definition_id="test.operation", subject_ref="subject")
    updated_at = _STARTED + timedelta(minutes=revision)
    event = OperationPhaseEvent(
        identity=identity,
        revision=revision,
        sequence=sequence,
        timestamp=updated_at,
        code=f"phase.{revision}",
        phase_code=f"phase.{revision}",
    )
    return OperationPersistedSnapshot(
        identity=identity,
        request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
        request_reference="d" * 64,
        revision=revision,
        lifecycle=OperationLifecycle.RUNNING,
        phase_code=event.phase_code,
        started_at=_STARTED,
        updated_at=updated_at,
        execution_deadline=None,
        cleanup_deadline=None,
        cancellation_requested_at=None,
        cancellation_acknowledged_at=None,
        event_cursor=sequence,
        events=(event,),
    )


def _lease(operation_id: str = "a" * 64) -> OperationOwnerLease:
    return OperationOwnerLease(
        operation_id=operation_id,
        scope_ref=operation_conflict_scope_reference(definition_id="test.operation", subject_ref="subject"),
        owner_id="b" * 64,
        token="c" * 64,
        acquired_at=_STARTED,
        expires_at=_STARTED + timedelta(hours=1),
    )


def _claim_lease(storage_root: Path, lease: OperationOwnerLease) -> None:
    """Acquire the exact durable owner used by one journal writer."""
    result = asyncio.run(
        OperationLeaseFilesystemRepository(storage_root=storage_root).acquire(lease, observed_at=lease.acquired_at)
    )
    assert result.disposition is OperationLeaseDisposition.ACQUIRED


def _commit_history(storage_root: Path) -> tuple[OperationJournalRepository, tuple[OperationPersistedSnapshot, ...]]:
    """Write three real revision transitions with a retained event per revision."""
    repository = OperationJournalRepository(storage_root=storage_root)
    snapshots = tuple(_snapshot(revision=revision, sequence=revision + 1) for revision in range(3))
    _claim_lease(storage_root, _lease())
    for expected_revision, snapshot in zip((0, 0, 1), snapshots, strict=True):
        asyncio.run(repository.commit(snapshot, expected_revision=expected_revision, lease=_lease()))
    return repository, snapshots


def _terminal_event() -> OperationTerminalEvent:
    """Build a valid early terminal event used only to corrupt stored history."""
    identity = OperationIdentity(operation_id="a" * 64, definition_id="test.operation", subject_ref="subject")
    receipt = OperationTerminalReceipt(
        identity=identity,
        revision=0,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
        settled_at=_STARTED,
        result_ref="result:complete",
    )
    return OperationTerminalEvent(
        identity=identity,
        revision=0,
        sequence=1,
        timestamp=_STARTED,
        code="operation.terminal",
        receipt=receipt,
    )


def _consumed_interaction() -> OperationConsumedInteraction:
    """Build a complete current-schema continuation through its production binder."""
    identity = OperationIdentity(operation_id="a" * 64, definition_id="test.operation", subject_ref="subject")
    pending = OperationPendingInteraction.bind(
        request=OperationInteractionRequest(
            interaction_id="e" * 64,
            identity=identity,
            revision=3,
            kind=OperationInteractionKind.REVIEW,
            presentation_code="operation.review.ready",
            response_schema_ref="schema:operation-review",
            continuation_digest="1" * 64,
        ),
        response_token="2" * 64,
        reviewed_proposal_digest="3" * 64,
        baseline_digest="4" * 64,
        proposed_effect_digest="5" * 64,
    )
    return pending.consume(
        OperationApplyResponse(
            interaction_id=pending.request.interaction_id,
            operation_id=identity.operation_id,
            revision=pending.request.revision,
            response_token="2" * 64,
            continuation_digest=pending.request.continuation_digest,
            reviewed_proposal_digest=pending.reviewed_proposal_digest,
            actor_ref="operator:persistence-test",
            responded_at=_STARTED + timedelta(minutes=3),
            baseline_digest="4" * 64,
            proposed_effect_digest="5" * 64,
        )
    )


def test_operation_journal_commits_cas_transitions_and_refuses_mutations(tmp_path: Path) -> None:
    """The on-disk record advances once and all rejected writes leave it intact."""
    repository = OperationJournalRepository(storage_root=tmp_path)
    initial = _snapshot(revision=0, sequence=1)
    _claim_lease(tmp_path, _lease())
    asyncio.run(repository.commit(initial, expected_revision=0, lease=_lease()))
    path = tmp_path / "operation-journals" / f"{initial.operation_id}.json"
    original_bytes = path.read_bytes()

    with pytest.raises(RepositoryError, match="successor revision"):
        asyncio.run(repository.commit(initial, expected_revision=0, lease=_lease()))
    assert path.read_bytes() == original_bytes

    with pytest.raises(RepositoryError, match="stale"):
        asyncio.run(repository.commit(_snapshot(revision=1, sequence=2), expected_revision=1, lease=_lease()))
    assert path.read_bytes() == original_bytes

    with pytest.raises(RepositoryError, match="lease"):
        asyncio.run(repository.commit(_snapshot(revision=1, sequence=2), expected_revision=0, lease=_lease("e" * 64)))
    assert path.read_bytes() == original_bytes

    future_lease = _lease().model_copy(
        update={
            "acquired_at": _STARTED + timedelta(minutes=2),
            "expires_at": _STARTED + timedelta(minutes=4),
        }
    )
    lease_repository = OperationLeaseFilesystemRepository(storage_root=tmp_path)
    released = asyncio.run(lease_repository.release(_lease(), observed_at=_STARTED + timedelta(seconds=1)))
    assert released.disposition is OperationLeaseDisposition.RELEASED
    _claim_lease(tmp_path, future_lease)
    with pytest.raises(RepositoryError, match="not yet active"):
        asyncio.run(repository.commit(_snapshot(revision=1, sequence=2), expected_revision=0, lease=future_lease))
    assert path.read_bytes() == original_bytes

    released = asyncio.run(lease_repository.release(future_lease, observed_at=_STARTED + timedelta(minutes=2)))
    assert released.disposition is OperationLeaseDisposition.RELEASED
    _claim_lease(tmp_path, _lease())

    with pytest.raises(RepositoryError, match="cursor"):
        asyncio.run(repository.commit(_snapshot(revision=1, sequence=3), expected_revision=0, lease=_lease()))
    assert path.read_bytes() == original_bytes

    successor = _snapshot(revision=1, sequence=2)
    asyncio.run(repository.commit(successor, expected_revision=0, lease=_lease()))
    reloaded = OperationJournalRepository(storage_root=tmp_path)
    assert asyncio.run(reloaded.load(initial.operation_id)) == successor
    raw = path.read_text(encoding="utf-8")
    assert '"history"' in raw
    assert '"sequence": 1' in raw
    assert '"sequence": 2' in raw
    assert "operand" not in raw


def test_operation_journal_requires_coherent_initial_history(tmp_path: Path) -> None:
    """Creation permits cursor zero without events or an event history starting at one."""
    repository = OperationJournalRepository(storage_root=tmp_path)
    identity = OperationIdentity(operation_id="a" * 64, definition_id="test.operation", subject_ref="subject")
    empty = OperationPersistedSnapshot(
        identity=identity,
        request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
        request_reference="d" * 64,
        revision=0,
        lifecycle=OperationLifecycle.RUNNING,
        started_at=_STARTED,
        updated_at=_STARTED,
        execution_deadline=None,
        cleanup_deadline=None,
        cancellation_requested_at=None,
        cancellation_acknowledged_at=None,
    )
    _claim_lease(tmp_path, _lease())
    asyncio.run(repository.commit(empty, expected_revision=0, lease=_lease()))
    assert (
        asyncio.run(repository.read_after(identity.operation_id, 0, limit=1)).status is OperationReplayStatus.CAUGHT_UP
    )

    malformed_root = tmp_path / "malformed"
    malformed = OperationJournalRepository(storage_root=malformed_root)
    _claim_lease(malformed_root, _lease())
    with pytest.raises(RepositoryError, match="begin at sequence one"):
        asyncio.run(malformed.commit(_snapshot(revision=0, sequence=2), expected_revision=0, lease=_lease()))


def test_operation_journal_creates_and_resolves_idempotency_only_from_a_complete_snapshot(tmp_path: Path) -> None:
    """A real retry claim is visible only as part of its durable initial journal."""
    repository = OperationJournalRepository(storage_root=tmp_path)
    initial = _snapshot(revision=0, sequence=1)
    claim = OperationIdempotencyClaim.bind(
        identity=initial.identity,
        idempotency_key="retry-once",
        request_reference=initial.request_reference,
    )
    idempotent_initial = initial.model_copy(update={"idempotency_claim": claim})
    _claim_lease(tmp_path, _lease())

    assert asyncio.run(repository.create(idempotent_initial, lease=_lease())) == initial.operation_id
    assert (
        asyncio.run(OperationJournalRepository(storage_root=tmp_path).resolve_idempotency(claim))
        == initial.operation_id
    )
    assert scan_directory(tmp_path / "operation-journals", pattern="claim-*.json") == ()

    conflicting_request = OperationIdempotencyClaim.bind(
        identity=initial.identity,
        idempotency_key="retry-once",
        request_reference="e" * 64,
    )
    with pytest.raises(RepositoryError, match="bound to a different request"):
        asyncio.run(repository.resolve_idempotency(conflicting_request))


def test_operation_journal_replays_full_history_by_exclusive_bounded_cursor(tmp_path: Path) -> None:
    """Retained history supports unknown, page, and caught-up replay without expiry claims."""
    repository, snapshots = _commit_history(tmp_path)
    operation_id = snapshots[-1].operation_id

    unknown = asyncio.run(repository.read_after("e" * 64, 0, limit=2))
    assert unknown.status is OperationReplayStatus.UNKNOWN_OPERATION
    assert unknown.events == ()
    assert unknown.next_cursor == 0

    first_page = asyncio.run(repository.read_after(operation_id, 0, limit=2))
    assert first_page.status is OperationReplayStatus.PAGE
    assert tuple(event.sequence for event in first_page.events) == (1, 2)
    assert first_page.next_cursor == 2
    assert asyncio.run(repository.read_after(operation_id, 0, limit=2)) == first_page

    second_page = asyncio.run(repository.read_after(operation_id, first_page.next_cursor, limit=1))
    assert second_page.status is OperationReplayStatus.PAGE
    assert tuple(event.sequence for event in second_page.events) == (3,)
    assert second_page.next_cursor == 3

    caught_up = asyncio.run(repository.read_after(operation_id, second_page.next_cursor, limit=2))
    assert caught_up.status is OperationReplayStatus.CAUGHT_UP
    assert caught_up.events == ()
    assert caught_up.next_cursor == second_page.next_cursor


@pytest.mark.parametrize(
    "field",
    ("intent", "response_digest", "consumed_at", "checkpoint", "continuation_proof_digest"),
)
def test_operation_journal_refuses_rewriting_full_consumed_interaction_evidence(tmp_path: Path, field: str) -> None:
    """A real CAS keeps every consumed response fact immutable, not only its ID."""
    repository, snapshots = _commit_history(tmp_path)
    accepted_consumption = _consumed_interaction()
    accepted = _snapshot(revision=3, sequence=4).model_copy(update={"consumed_interactions": (accepted_consumption,)})
    asyncio.run(repository.commit(accepted, expected_revision=snapshots[-1].revision, lease=_lease()))

    changed_values = {
        "intent": "reject",
        "response_digest": "9" * 64,
        "consumed_at": _STARTED + timedelta(minutes=4),
        "checkpoint": accepted_consumption.checkpoint.model_copy(update={"reviewed_proposal_digest": "8" * 64}),
        "continuation_proof_digest": "7" * 64,
    }
    changed_value = changed_values[field]
    planted = accepted_consumption.model_copy(update={field: changed_value})
    tampered = _snapshot(revision=4, sequence=5).model_copy(update={"consumed_interactions": (planted,)})
    path = tmp_path / "operation-journals" / f"{accepted.operation_id}.json"
    stable_bytes = path.read_bytes()

    with pytest.raises(RepositoryError, match="cannot rewrite consumed interaction history"):
        asyncio.run(repository.commit(tampered, expected_revision=accepted.revision, lease=_lease()))
    assert path.read_bytes() == stable_bytes


def test_operation_journal_refuses_intent_only_tamper_during_strict_hydration(tmp_path: Path) -> None:
    """A changed durable intent cannot reach dispatch with its original continuation proof."""
    repository, snapshots = _commit_history(tmp_path)
    consumed = _consumed_interaction()
    accepted = _snapshot(revision=3, sequence=4).model_copy(update={"consumed_interactions": (consumed,)})
    asyncio.run(repository.commit(accepted, expected_revision=snapshots[-1].revision, lease=_lease()))
    path = tmp_path / "operation-journals" / f"{accepted.operation_id}.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["snapshot"]["consumed_interactions"][0]["intent"] = "reject"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(RepositoryError, match="invalid operation journal"):
        asyncio.run(repository.load(accepted.operation_id))


@pytest.mark.parametrize(
    "corruption",
    ("identity", "sequence", "timestamp", "revision", "terminal", "snapshot_tail"),
)
def test_operation_journal_refuses_raw_history_corruption(tmp_path: Path, corruption: str) -> None:
    """A load rejects every cross-revision history invariant broken on disk."""
    repository, snapshots = _commit_history(tmp_path)
    path = tmp_path / "operation-journals" / f"{snapshots[-1].operation_id}.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    history = document["history"]
    assert isinstance(history, list)

    match corruption:
        case "identity":
            history[-1]["identity"]["subject_ref"] = "other-subject"
        case "sequence":
            history[0]["sequence"] = 2
        case "timestamp":
            history[0]["timestamp"] = "2026-08-13T20:03:00Z"
        case "revision":
            history[1]["revision"] = 3
        case "terminal":
            history[0] = _terminal_event().model_dump(mode="json")
        case "snapshot_tail":
            history[-1]["code"] = "phase.altered"
        case _:
            raise AssertionError(f"unexpected corruption case: {corruption}")
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(RepositoryError, match="invalid operation journal"):
        asyncio.run(repository.load(snapshots[-1].operation_id))
