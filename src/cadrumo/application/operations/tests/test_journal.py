"""Direct contract tests for operation journal ports and lease facts."""

from __future__ import annotations

import inspect
import json
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from cadrumo.application.operations.capabilities import OperationRequestStoragePolicy
from cadrumo.application.operations.models import (
    OperationId,
    OperationIdentity,
    OperationRequest,
    OperationTerminalReceipt,
)
from cadrumo.application.operations.persistence.events import (
    OperationPhaseEvent,
    OperationProgressEvent,
    OperationTerminalEvent,
)
from cadrumo.application.operations.persistence.journal import (
    OperationEventStream,
    OperationJournal,
    OperationLeaseRepository,
    OperationObservationMaterialization,
    OperationObservationReader,
    OperationPersistedSnapshot,
    OperationProgressFoldCheckpoint,
    OperationProgressFoldInput,
    OperationSecureReferenceStore,
)
from cadrumo.application.operations.persistence.leases import (
    OperationConflictScopeReference,
    OperationLeaseDisposition,
    OperationLeaseObservation,
    OperationLeaseObservationDisposition,
    OperationLeaseResult,
    OperationOwnerLease,
    operation_conflict_scope_reference,
)
from cadrumo.application.operations.persistence.replay import (
    OperationReplayLimit,
    OperationReplayPage,
    OperationReplayStatus,
)

from ....core import OperationEffect, OperationLifecycle, OperationTerminalCondition
from ..models import OperationSnapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SCOPE_REF = operation_conflict_scope_reference(definition_id="test.operation", subject_ref="subject")
_DEFINITION_CONTRACT_DIGEST = "c" * 64


class Operand(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    value: str


def _snapshot() -> OperationSnapshot[Operand]:
    observed = datetime(2026, 8, 13, 20, tzinfo=UTC)
    identity = OperationIdentity(operation_id="a" * 64, definition_id="test.operation", subject_ref="subject")
    return OperationSnapshot[Operand](
        identity=identity,
        request=OperationRequest[Operand](
            definition_id=identity.definition_id,
            subject_ref=identity.subject_ref,
            payload=Operand(value="operand"),
        ),
        revision=0,
        lifecycle=OperationLifecycle.RUNNING,
        updated_at=observed,
    )


def _persisted_snapshot() -> OperationPersistedSnapshot:
    runtime = _snapshot()
    event = OperationPhaseEvent(
        identity=runtime.identity,
        revision=runtime.revision,
        sequence=1,
        timestamp=runtime.updated_at,
        code="phase.started",
        phase_code="phase.started",
    )
    return OperationPersistedSnapshot(
        identity=runtime.identity,
        definition_contract_digest=_DEFINITION_CONTRACT_DIGEST,
        request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
        request_reference="d" * 64,
        revision=runtime.revision,
        lifecycle=runtime.lifecycle,
        effect=runtime.effect,
        phase_code=event.phase_code,
        started_at=runtime.updated_at,
        updated_at=runtime.updated_at,
        execution_deadline=None,
        cleanup_deadline=None,
        cancellation_requested_at=None,
        cancellation_acknowledged_at=None,
        cancellation_deferred=False,
        event_cursor=event.sequence,
        events=(event,),
    )


def _terminal_persisted_snapshot() -> OperationPersistedSnapshot:
    observed = datetime(2026, 8, 13, 20, 5, tzinfo=UTC)
    identity = OperationIdentity(operation_id="a" * 64, definition_id="test.operation", subject_ref="subject")
    receipt = OperationTerminalReceipt(
        identity=identity,
        revision=4,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.UPDATED,
        settled_at=observed,
        result_ref="result:complete",
    )
    event = OperationTerminalEvent(
        identity=identity,
        revision=receipt.revision,
        sequence=8,
        timestamp=observed,
        code="operation.terminal",
        receipt=receipt,
    )
    return OperationPersistedSnapshot(
        identity=identity,
        definition_contract_digest=_DEFINITION_CONTRACT_DIGEST,
        request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
        request_reference="d" * 64,
        revision=receipt.revision,
        lifecycle=OperationLifecycle.TERMINAL,
        terminal_condition=receipt.condition,
        effect=receipt.effect,
        started_at=datetime(2026, 8, 13, 20, tzinfo=UTC),
        updated_at=observed,
        execution_deadline=None,
        cleanup_deadline=None,
        cancellation_requested_at=None,
        cancellation_acknowledged_at=None,
        cancellation_deferred=False,
        event_cursor=event.sequence,
        terminal_receipt=receipt,
        events=(event,),
    )


def test_persisted_snapshot_is_versioned_and_excludes_the_runtime_request() -> None:
    runtime = _snapshot()
    persisted = _persisted_snapshot()

    restored = OperationPersistedSnapshot.model_validate_json(persisted.model_dump_json())

    assert restored == persisted
    assert runtime.request.payload == Operand(value="operand")
    assert "operand" not in persisted.model_dump_json()
    assert "payload" not in persisted.model_dump()
    with pytest.raises(ValidationError, match="frozen_instance"):
        restored.revision = 1
    payload = persisted.model_dump()
    for schema_version in (1, 2, 3, 4, 5):
        payload = persisted.model_dump(mode="json")
        payload["schema_version"] = schema_version
        with pytest.raises(ValidationError):
            OperationPersistedSnapshot.model_validate_json(json.dumps(payload))
    missing_digest = persisted.model_dump(mode="json")
    del missing_digest["definition_contract_digest"]
    with pytest.raises(ValidationError):
        OperationPersistedSnapshot.model_validate(missing_digest)
    for safety_field in (
        "execution_deadline",
        "cleanup_deadline",
        "cancellation_requested_at",
        "cancellation_acknowledged_at",
        "cancellation_deferred",
    ):
        payload = persisted.model_dump(mode="json")
        del payload[safety_field]
        with pytest.raises(ValidationError, match="Field required"):
            OperationPersistedSnapshot.model_validate_json(json.dumps(payload))
    payload = persisted.model_dump()
    payload["request"] = runtime.request
    with pytest.raises(ValidationError):
        OperationPersistedSnapshot.model_validate(payload)


def test_persisted_snapshot_correlates_deadline_and_cooperative_cancellation_facts() -> None:
    """Deadline, request, acknowledgement, and cleanup facts remain ordered durable state."""
    persisted = _persisted_snapshot()
    requested_at = persisted.updated_at + timedelta(minutes=1)
    acknowledged_at = requested_at + timedelta(seconds=10)
    cleanup_deadline = requested_at + timedelta(minutes=1)
    payload = persisted.model_dump()
    payload.update(
        events=(),
        lifecycle=OperationLifecycle.SETTLING,
        updated_at=acknowledged_at,
        execution_deadline=requested_at,
        cleanup_deadline=cleanup_deadline,
        cancellation_requested_at=requested_at,
        cancellation_acknowledged_at=acknowledged_at,
        cancellation_deferred=False,
    )

    accepted = OperationPersistedSnapshot.model_validate(payload)

    assert accepted.execution_deadline == requested_at
    assert accepted.cleanup_deadline == cleanup_deadline
    assert accepted.cancellation_requested_at == requested_at
    assert accepted.cancellation_acknowledged_at == acknowledged_at
    for mutation, message in (
        ({"cleanup_deadline": requested_at}, "later cleanup deadline"),
        ({"cancellation_requested_at": None}, "cleanup deadline requires"),
        ({"cancellation_acknowledged_at": requested_at - timedelta(seconds=1)}, "must follow the request"),
        ({"lifecycle": OperationLifecycle.CANCELLATION_REQUESTED}, "requires settlement lifecycle"),
    ):
        changed = accepted.model_dump()
        changed.update(mutation)
        with pytest.raises(ValidationError, match=message):
            OperationPersistedSnapshot.model_validate(changed)


def test_persisted_snapshot_binds_event_identity_revision_sequence_and_cursor() -> None:
    persisted = _persisted_snapshot()
    first = persisted.events[0]
    second = first.model_copy(update={"sequence": 2})
    payload = persisted.model_dump()
    payload.update(events=(first, second), event_cursor=second.sequence)

    accepted = OperationPersistedSnapshot.model_validate(payload)

    assert accepted.events == (first, second)
    for mutation, message in (
        (
            {
                "events": (
                    first.model_copy(update={"identity": first.identity.model_copy(update={"operation_id": "9" * 64})}),
                    second,
                )
            },
            "event identity",
        ),
        ({"events": (first.model_copy(update={"revision": 1}), second)}, "event revision"),
        ({"events": (first, second.model_copy(update={"sequence": 3})), "event_cursor": 3}, "sequences"),
        ({"event_cursor": 1}, "event cursor"),
    ):
        changed = accepted.model_dump()
        changed.update(mutation)
        with pytest.raises(ValidationError, match=message):
            OperationPersistedSnapshot.model_validate(changed)


def test_persisted_snapshot_binds_event_derived_phase_and_timeline() -> None:
    persisted = _persisted_snapshot()
    first = persisted.events[0]
    assert isinstance(first, OperationPhaseEvent)
    second = first.model_copy(
        update={
            "sequence": 2,
            "timestamp": first.timestamp + timedelta(minutes=1),
            "code": "phase.running",
            "phase_code": "phase.running",
        }
    )
    payload = persisted.model_dump()
    payload.update(
        events=(first, second),
        phase_code=second.phase_code,
        updated_at=second.timestamp,
        event_cursor=second.sequence,
    )

    accepted = OperationPersistedSnapshot.model_validate(payload)
    assert accepted.phase_code == second.phase_code
    assert accepted.updated_at == second.timestamp

    empty_payload = persisted.model_dump()
    empty_payload.update(
        events=(), phase_code=None, event_cursor=0, updated_at=persisted.updated_at + timedelta(minutes=1)
    )
    empty = OperationPersistedSnapshot.model_validate(empty_payload)
    assert empty.events == ()
    assert empty.phase_code is None

    reversed_second = second.model_copy(update={"timestamp": first.timestamp - timedelta(minutes=1)})
    for mutation, message in (
        ({"phase_code": first.phase_code}, "latest journal phase event"),
        ({"updated_at": accepted.updated_at + timedelta(seconds=1)}, "final journal event timestamp"),
        ({"updated_at": persisted.started_at - timedelta(microseconds=1)}, "update before it starts"),
        (
            {
                "started_at": reversed_second.timestamp - timedelta(minutes=1),
                "updated_at": reversed_second.timestamp,
                "events": (first, reversed_second),
            },
            "timestamps must be nondecreasing",
        ),
    ):
        changed = accepted.model_dump()
        changed.update(mutation)
        with pytest.raises(ValidationError, match=message):
            OperationPersistedSnapshot.model_validate(changed)

    empty_payload["phase_code"] = first.phase_code
    event_free_successor = OperationPersistedSnapshot.model_validate(empty_payload)
    assert event_free_successor.phase_code == first.phase_code
    assert event_free_successor.event_cursor == 0


def test_persisted_terminal_snapshot_binds_exact_terminal_event_and_receipt() -> None:
    persisted = _terminal_persisted_snapshot()
    event = persisted.events[0]
    assert isinstance(event, OperationTerminalEvent)

    assert event.receipt == persisted.terminal_receipt
    assert persisted.phase_code is None
    alternate_receipt = persisted.terminal_receipt.model_copy(update={"result_ref": "result:other"})
    for mutation, message in (
        ({"events": ()}, "one terminal event"),
        (
            {"events": (event.model_copy(update={"receipt": alternate_receipt}),)},
            "terminal journal event receipt",
        ),
        ({"terminal_receipt": alternate_receipt}, "terminal journal event receipt"),
    ):
        changed = persisted.model_dump()
        changed.update(mutation)
        with pytest.raises(ValidationError, match=message):
            OperationPersistedSnapshot.model_validate(changed)

    after_terminal = OperationPhaseEvent(
        identity=event.identity,
        revision=event.revision,
        sequence=event.sequence + 1,
        timestamp=event.timestamp,
        code="phase.after-terminal",
        phase_code="phase.after-terminal",
    )
    changed = persisted.model_dump()
    changed.update(
        events=(event, after_terminal),
        phase_code=after_terminal.phase_code,
        event_cursor=after_terminal.sequence,
    )
    with pytest.raises(ValidationError, match="one final terminal event"):
        OperationPersistedSnapshot.model_validate(changed)


def test_public_port_signatures_pin_explicit_lease_evidence_inputs() -> None:
    assert tuple(inspect.signature(OperationJournal.resolve_idempotency).parameters) == ("self", "claim")
    assert tuple(inspect.signature(OperationJournal.create).parameters) == ("self", "snapshot", "lease")
    assert inspect.signature(OperationJournal.create).parameters["lease"].kind is inspect.Parameter.KEYWORD_ONLY
    assert tuple(inspect.signature(OperationJournal.commit).parameters) == (
        "self",
        "snapshot",
        "expected_revision",
        "lease",
    )
    assert tuple(inspect.signature(OperationEventStream.read_after).parameters) == (
        "self",
        "operation_id",
        "cursor",
        "limit",
    )
    assert tuple(inspect.signature(OperationObservationReader.read_observation).parameters) == (
        "self",
        "operation_id",
        "after_cursor",
        "limit",
    )
    assert (
        inspect.signature(OperationObservationReader.read_observation).parameters["limit"].kind
        is inspect.Parameter.KEYWORD_ONLY
    )
    assert tuple(inspect.signature(OperationLeaseRepository.inspect).parameters) == (
        "self",
        "scope_ref",
        "operation_id",
        "observed_at",
    )
    assert tuple(inspect.signature(OperationLeaseRepository.acquire).parameters) == (
        "self",
        "candidate",
        "observed_at",
    )
    assert tuple(inspect.signature(OperationLeaseRepository.compare_and_swap).parameters) == (
        "self",
        "predecessor",
        "successor",
        "observed_at",
    )
    assert tuple(inspect.signature(OperationLeaseRepository.release).parameters) == (
        "self",
        "predecessor",
        "observed_at",
    )
    for method in (
        OperationLeaseRepository.inspect,
        OperationLeaseRepository.acquire,
        OperationLeaseRepository.compare_and_swap,
        OperationLeaseRepository.release,
    ):
        assert inspect.signature(method).parameters["observed_at"].kind is inspect.Parameter.KEYWORD_ONLY
    expected_annotations = {
        OperationLeaseRepository.inspect: {
            "scope_ref": OperationConflictScopeReference,
            "operation_id": OperationId,
            "observed_at": datetime,
            "return": OperationLeaseObservation,
        },
        OperationLeaseRepository.acquire: {
            "candidate": OperationOwnerLease,
            "observed_at": datetime,
            "return": OperationLeaseResult,
        },
        OperationLeaseRepository.compare_and_swap: {
            "predecessor": OperationOwnerLease,
            "successor": OperationOwnerLease,
            "observed_at": datetime,
            "return": OperationLeaseResult,
        },
        OperationLeaseRepository.release: {
            "predecessor": OperationOwnerLease,
            "observed_at": datetime,
            "return": OperationLeaseResult,
        },
    }
    for method, expected in expected_annotations.items():
        assert inspect.get_annotations(method, eval_str=True) == expected
    assert tuple(inspect.signature(OperationSecureReferenceStore.resolve).parameters) == (
        "self",
        "reference",
        "operand_type",
    )


def test_owner_lease_requires_a_positive_utc_window() -> None:
    acquired = datetime(2026, 8, 13, 20, tzinfo=UTC)
    with pytest.raises(ValidationError):
        OperationOwnerLease(
            operation_id="a" * 64,
            scope_ref=operation_conflict_scope_reference(definition_id="test.operation", subject_ref="subject"),
            owner_id="b" * 64,
            token="c" * 64,
            acquired_at=acquired,
            expires_at=acquired,
        )


def _owner_lease(
    *,
    operation_id: str = "a" * 64,
    owner_id: str = "b" * 64,
    token: str = "c" * 64,
    acquired_at: datetime = datetime(2026, 8, 13, 20, tzinfo=UTC),
    expires_at: datetime = datetime(2026, 8, 13, 20, 3, tzinfo=UTC),
) -> OperationOwnerLease:
    return OperationOwnerLease(
        operation_id=operation_id,
        scope_ref=operation_conflict_scope_reference(definition_id="test.operation", subject_ref="subject"),
        owner_id=owner_id,
        token=token,
        acquired_at=acquired_at,
        expires_at=expires_at,
    )


def test_lease_and_replay_results_are_fail_closed() -> None:
    observed = datetime(2026, 8, 13, 20, tzinfo=UTC)
    for disposition in OperationLeaseDisposition:
        with pytest.raises(ValidationError):
            OperationLeaseResult(
                scope_ref=_SCOPE_REF,
                operation_id="a" * 64,
                disposition=disposition,
                observed_at=observed,
            )
    for disposition in {
        OperationLeaseObservationDisposition.ACTIVE,
        OperationLeaseObservationDisposition.EXPIRED,
    }:
        with pytest.raises(ValidationError):
            OperationLeaseObservation(
                scope_ref=_SCOPE_REF,
                operation_id="a" * 64,
                disposition=disposition,
                observed_at=observed,
            )
    with pytest.raises(ValidationError, match="at least one event"):
        OperationReplayPage(status=OperationReplayStatus.PAGE, requested_cursor=0, events=(), next_cursor=0)
    with pytest.raises(ValidationError):
        OperationReplayPage(status=OperationReplayStatus.CAUGHT_UP, requested_cursor=0, events=(), next_cursor=-1)
    with pytest.raises(ValidationError):
        TypeAdapter(OperationReplayLimit).validate_python(0)
    with pytest.raises(ValidationError):
        TypeAdapter(OperationReplayLimit).validate_python(1_001)


def test_lease_observation_binds_target_state_and_deterministic_evidence() -> None:
    observed = datetime(2026, 8, 13, 20, 2, tzinfo=UTC)
    active = _owner_lease(expires_at=datetime(2026, 8, 13, 20, 3, tzinfo=UTC))
    expired = _owner_lease(expires_at=datetime(2026, 8, 13, 20, 1, tzinfo=UTC))

    absent = OperationLeaseObservation(
        scope_ref=_SCOPE_REF,
        operation_id="a" * 64,
        disposition=OperationLeaseObservationDisposition.ABSENT,
        observed_at=observed,
    )
    active_observation = OperationLeaseObservation(
        scope_ref=_SCOPE_REF,
        operation_id="a" * 64,
        disposition=OperationLeaseObservationDisposition.ACTIVE,
        observed_at=observed,
        current=active,
    )
    expired_observation = OperationLeaseObservation(
        scope_ref=_SCOPE_REF,
        operation_id="a" * 64,
        disposition=OperationLeaseObservationDisposition.EXPIRED,
        observed_at=observed,
        current=expired,
    )

    assert absent.current is None
    assert active_observation.current == active
    assert expired_observation.current == expired
    assert (
        active_observation.evidence_ref
        == OperationLeaseObservation.model_validate(active_observation.model_dump()).evidence_ref
    )
    assert active_observation.evidence_ref != expired_observation.evidence_ref

    for mutation, message in (
        ({"current": active}, "absent lease observation forbids"),
        ({"disposition": OperationLeaseObservationDisposition.ACTIVE, "current": expired}, "requires an unexpired"),
        ({"disposition": OperationLeaseObservationDisposition.EXPIRED, "current": active}, "requires an expired"),
        (
            {
                "disposition": OperationLeaseObservationDisposition.ACTIVE,
                "current": active.model_copy(update={"scope_ref": "9" * 64}),
            },
            "does not match the conflict scope",
        ),
    ):
        payload = absent.model_dump()
        payload.update(mutation)
        payload.pop("evidence_ref")
        with pytest.raises(ValidationError, match=message):
            OperationLeaseObservation.model_validate(payload)


def test_lease_transition_contracts_bind_exact_predecessors_and_derived_evidence() -> None:
    acquired_at = datetime(2026, 8, 13, 20, tzinfo=UTC)
    observed = datetime(2026, 8, 13, 20, 2, tzinfo=UTC)
    predecessor = _owner_lease(acquired_at=acquired_at, expires_at=datetime(2026, 8, 13, 20, 3, tzinfo=UTC))
    renewed = _owner_lease(acquired_at=acquired_at, expires_at=datetime(2026, 8, 13, 20, 4, tzinfo=UTC))
    expired_predecessor = _owner_lease(acquired_at=acquired_at, expires_at=datetime(2026, 8, 13, 20, 1, tzinfo=UTC))
    takeover = _owner_lease(
        owner_id="e" * 64,
        token="f" * 64,
        acquired_at=observed,
        expires_at=datetime(2026, 8, 13, 20, 3, tzinfo=UTC),
    )
    acquired = _owner_lease(
        acquired_at=observed,
        expires_at=datetime(2026, 8, 13, 20, 3, tzinfo=UTC),
    )

    results = (
        OperationLeaseResult(
            scope_ref=_SCOPE_REF,
            operation_id="a" * 64,
            disposition=OperationLeaseDisposition.ACQUIRED,
            observed_at=observed,
            current=acquired,
        ),
        OperationLeaseResult(
            scope_ref=_SCOPE_REF,
            operation_id="a" * 64,
            disposition=OperationLeaseDisposition.RENEWED,
            observed_at=observed,
            predecessor=predecessor,
            current=renewed,
        ),
        OperationLeaseResult(
            scope_ref=_SCOPE_REF,
            operation_id="a" * 64,
            disposition=OperationLeaseDisposition.CONFLICT,
            observed_at=observed,
            current=predecessor,
        ),
        OperationLeaseResult(
            scope_ref=_SCOPE_REF,
            operation_id="a" * 64,
            disposition=OperationLeaseDisposition.EXPIRED,
            observed_at=observed,
            predecessor=expired_predecessor,
        ),
        OperationLeaseResult(
            scope_ref=_SCOPE_REF,
            operation_id="a" * 64,
            disposition=OperationLeaseDisposition.TAKEN_OVER,
            observed_at=observed,
            predecessor=expired_predecessor,
            current=takeover,
        ),
        OperationLeaseResult(
            scope_ref=_SCOPE_REF,
            operation_id="a" * 64,
            disposition=OperationLeaseDisposition.RELEASED,
            observed_at=observed,
            predecessor=predecessor,
        ),
        OperationLeaseResult(
            scope_ref=_SCOPE_REF,
            operation_id="a" * 64,
            disposition=OperationLeaseDisposition.OWNER_LOST,
            observed_at=observed,
            predecessor=predecessor,
        ),
    )

    assert len({result.evidence_ref for result in results}) == len(results)
    assert all(OperationLeaseResult.model_validate(result.model_dump()) == result for result in results)
    tampered = results[0].model_dump()
    tampered["evidence_ref"] = "d" * 64
    with pytest.raises(ValidationError, match="does not match the canonical transition payload"):
        OperationLeaseResult.model_validate(tampered)


def test_replay_page_binds_ordered_events_to_next_cursor() -> None:
    snapshot = _snapshot()
    first = OperationPhaseEvent(
        identity=snapshot.identity,
        revision=0,
        sequence=1,
        timestamp=snapshot.updated_at,
        code="phase.started",
        phase_code="phase.started",
    )
    second = first.model_copy(update={"sequence": 2})
    assert (
        OperationReplayPage(
            status=OperationReplayStatus.PAGE, requested_cursor=0, events=(first, second), next_cursor=2
        ).next_cursor
        == 2
    )
    with pytest.raises(ValidationError, match="contiguous"):
        OperationReplayPage(
            status=OperationReplayStatus.PAGE, requested_cursor=0, events=(second, first), next_cursor=1
        )
    with pytest.raises(ValidationError, match="final event sequence"):
        OperationReplayPage(
            status=OperationReplayStatus.PAGE, requested_cursor=0, events=(first, second), next_cursor=1
        )


def test_observation_materialization_binds_snapshot_replay_and_progress_to_one_anchor() -> None:
    initial = _persisted_snapshot()
    progress = OperationProgressEvent(
        identity=initial.identity,
        revision=initial.revision,
        sequence=2,
        timestamp=initial.updated_at,
        code="progress.updated",
        completed=3,
        total=7,
        unit_code="items",
    )
    snapshot = initial.model_copy(update={"event_cursor": 2, "events": (initial.events[0], progress)})
    materialization = OperationObservationMaterialization(
        snapshot=snapshot,
        anchor_cursor=2,
        replay=OperationReplayPage(
            status=OperationReplayStatus.PAGE,
            requested_cursor=0,
            events=(initial.events[0], progress),
            next_cursor=2,
        ),
        progress_fold=OperationProgressFoldInput(events=(initial.events[0], progress)),
    )

    assert materialization.snapshot.definition_contract_digest == _DEFINITION_CONTRACT_DIGEST
    assert materialization.progress_fold.events[-1] == progress
    assert OperationObservationMaterialization.model_validate_json(materialization.model_dump_json()) == materialization


def test_observation_materialization_accepts_checkpoint_suffix_and_refuses_cross_anchor_state() -> None:
    initial = _persisted_snapshot()
    progress = OperationProgressEvent(
        identity=initial.identity,
        revision=initial.revision,
        sequence=2,
        timestamp=initial.updated_at,
        code="progress.updated",
        completed=1,
        total=2,
    )
    snapshot = initial.model_copy(update={"event_cursor": 2, "events": (initial.events[0], progress)})
    checkpoint = OperationProgressFoldCheckpoint(
        identity=snapshot.identity,
        through_cursor=1,
        phase_code="phase.started",
    )
    materialization = OperationObservationMaterialization(
        snapshot=snapshot,
        anchor_cursor=2,
        replay=OperationReplayPage(
            status=OperationReplayStatus.CAUGHT_UP,
            requested_cursor=2,
            events=(),
            next_cursor=2,
        ),
        progress_fold=OperationProgressFoldInput(checkpoint=checkpoint, events=(progress,)),
    )
    assert materialization.progress_fold.checkpoint == checkpoint

    for mutation, message in (
        ({"anchor_cursor": 1}, "snapshot cursor"),
        (
            {
                "replay": OperationReplayPage(
                    status=OperationReplayStatus.EXPIRED,
                    requested_cursor=0,
                    events=(),
                    next_cursor=3,
                    restart_cursor=3,
                )
            },
            "cannot exceed its anchor",
        ),
        ({"progress_fold": OperationProgressFoldInput(checkpoint=checkpoint, events=())}, "cover every event"),
        (
            {
                "replay": OperationReplayPage(
                    status=OperationReplayStatus.CAUGHT_UP,
                    requested_cursor=0,
                    events=(),
                    next_cursor=0,
                )
            },
            "must reach its authoritative anchor",
        ),
        (
            {
                "replay": OperationReplayPage(
                    status=OperationReplayStatus.COMPACTED,
                    requested_cursor=0,
                    events=(),
                    next_cursor=1,
                    restart_cursor=1,
                ),
                "progress_fold": OperationProgressFoldInput(events=(initial.events[0], progress)),
            },
            "exact progress checkpoint",
        ),
    ):
        with pytest.raises(ValidationError, match=message):
            OperationObservationMaterialization.model_validate({**materialization.model_dump(), **mutation})


def test_lease_transition_correlations_refuse_planted_identity_and_time_mutations() -> None:
    observed = datetime(2026, 8, 13, 20, 2, tzinfo=UTC)
    predecessor = OperationOwnerLease(
        operation_id="a" * 64,
        scope_ref=operation_conflict_scope_reference(definition_id="test.operation", subject_ref="subject"),
        owner_id="b" * 64,
        token="c" * 64,
        acquired_at=datetime(2026, 8, 13, 20, tzinfo=UTC),
        expires_at=datetime(2026, 8, 13, 20, 1, tzinfo=UTC),
    )
    current = OperationOwnerLease(
        operation_id="a" * 64,
        scope_ref=operation_conflict_scope_reference(definition_id="test.operation", subject_ref="subject"),
        owner_id="e" * 64,
        token="f" * 64,
        acquired_at=observed,
        expires_at=datetime(2026, 8, 13, 20, 3, tzinfo=UTC),
    )
    accepted = OperationLeaseResult(
        scope_ref=_SCOPE_REF,
        operation_id="a" * 64,
        disposition=OperationLeaseDisposition.TAKEN_OVER,
        observed_at=observed,
        predecessor=predecessor,
        current=current,
    )
    assert accepted.current == current
    for mutation, message in (
        ({"current": current.model_copy(update={"operation_id": "9" * 64})}, "successor must match"),
        ({"current": current.model_copy(update={"owner_id": predecessor.owner_id})}, "new owner and token"),
        ({"current": current.model_copy(update={"token": predecessor.token})}, "new owner and token"),
        (
            {"predecessor": predecessor.model_copy(update={"expires_at": current.expires_at})},
            "expired predecessor",
        ),
    ):
        with pytest.raises(ValidationError, match=message):
            OperationLeaseResult.model_validate(
                {
                    "scope_ref": _SCOPE_REF,
                    "operation_id": "a" * 64,
                    "disposition": OperationLeaseDisposition.TAKEN_OVER,
                    "observed_at": observed,
                    "predecessor": mutation.get("predecessor", predecessor),
                    "current": mutation.get("current", current),
                }
            )


def test_replay_statuses_bind_requested_cursor_and_restart_boundary() -> None:
    caught_up = OperationReplayPage(
        status=OperationReplayStatus.CAUGHT_UP, requested_cursor=8, events=(), next_cursor=8
    )
    assert caught_up.next_cursor == caught_up.requested_cursor
    for status in (OperationReplayStatus.EXPIRED, OperationReplayStatus.COMPACTED):
        page = OperationReplayPage(status=status, requested_cursor=2, events=(), next_cursor=7, restart_cursor=7)
        assert page.restart_cursor == 7
        with pytest.raises(ValidationError, match="advance beyond"):
            OperationReplayPage(
                status=status,
                requested_cursor=100,
                events=(),
                next_cursor=7,
                restart_cursor=7,
            )
    with pytest.raises(ValidationError, match="preserve the requested cursor"):
        OperationReplayPage(status=OperationReplayStatus.CAUGHT_UP, requested_cursor=8, events=(), next_cursor=9)
    with pytest.raises(ValidationError, match="contiguous"):
        snapshot = _snapshot()
        stale = OperationPhaseEvent(
            identity=snapshot.identity,
            revision=0,
            sequence=1,
            timestamp=snapshot.updated_at,
            code="phase.started",
            phase_code="phase.started",
        )
        OperationReplayPage(status=OperationReplayStatus.PAGE, requested_cursor=1, events=(stale,), next_cursor=1)
