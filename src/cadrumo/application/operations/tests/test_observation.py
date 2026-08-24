"""Real-adapter tests for the canonical public operation observation service."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path

import pytest
from pydantic import BaseModel

from ....adapters.persistence.operations import OperationJournalRepository, OperationLeaseFilesystemRepository
from ....core import (
    STRICT_FROZEN_CONFIG,
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationLifecycle,
)
from .. import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationDefinition,
    OperationExecutorContext,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationIdentity,
    OperationObservationMaterialization,
    OperationObservationRefusalCode,
    OperationObservationRefusalV1,
    OperationObservationRequestV1,
    OperationObservationService,
    OperationObservationSuccessV1,
    OperationObservationVersionHeader,
    OperationOwnedResource,
    OperationOwnerLease,
    OperationPersistedSnapshot,
    OperationPhaseEvent,
    OperationProgressEvent,
    OperationProgressFoldCheckpoint,
    OperationProgressFoldInput,
    OperationPublicDefinitionRegistrationV1,
    OperationPublicProgressEventV1,
    OperationReconciliationPolicy,
    OperationRegistry,
    OperationReplayPage,
    OperationReplayPolicy,
    OperationReplayStatus,
    OperationRequest,
    OperationRequestStoragePolicy,
    OperationSchemaBindingV1,
    OperationSensitiveInputPolicy,
    operation_conflict_scope_reference,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_STARTED = datetime(2026, 8, 24, 9, tzinfo=UTC)
_OPERATION_ID = "a" * 64
_DEFINITION_ID = "operations.observation.test"


class ObservationRequest(BaseModel):
    model_config = STRICT_FROZEN_CONFIG
    subject_code: str


class ObservationExecutor:
    async def execute(
        self,
        request: OperationRequest[ObservationRequest],
        context: OperationExecutorContext,
    ) -> str | None:
        del context
        return request.subject_ref


def _build_executor() -> ObservationExecutor:
    return ObservationExecutor()


def _registry() -> OperationRegistry:
    capabilities = OperationCapabilities(
        durability=OperationDurability.RECORDED,
        cancellation=OperationCancellation.COOPERATIVE,
        deadline=OperationDeadline.COOPERATIVE,
        replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
        baseline=OperationBaselinePolicy.REQUEST_BOUND,
        request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
        sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
        conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
        owned_resources=frozenset({OperationOwnedResource.ASYNC_TASK}),
        permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN}),
        close_policy=OperationClosePolicy.REQUEST_CANCEL,
    )
    definition = OperationDefinition(
        definition_id=_DEFINITION_ID,
        request_type=ObservationRequest,
        result_type=None,
        executor_factory=OperationExecutorFactory(
            request_type=ObservationRequest,
            executor_type=ObservationExecutor,
            build=_build_executor,
        ),
        phase_codes=("observation.phase.one", "observation.phase.two"),
        interaction_kinds=frozenset(),
        capabilities=capabilities,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.TUI}),
    )
    registration = OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id="operations.observation.request",
            schema_version=1,
            model_type=ObservationRequest,
        ),
    )
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,))


def _lease() -> OperationOwnerLease:
    return OperationOwnerLease(
        operation_id=_OPERATION_ID,
        scope_ref=operation_conflict_scope_reference(definition_id=_DEFINITION_ID, subject_ref="profile:active"),
        owner_id="b" * 64,
        token="c" * 64,
        acquired_at=_STARTED,
        expires_at=_STARTED + timedelta(hours=1),
    )


def _snapshot(
    registry: OperationRegistry,
    *,
    revision: int,
    event: OperationPhaseEvent | OperationProgressEvent,
    phase_code: str,
) -> OperationPersistedSnapshot:
    return OperationPersistedSnapshot(
        identity=event.identity,
        definition_contract_digest=registry.lookup_public_contract(_DEFINITION_ID).definition_contract_digest,
        request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
        request_reference="d" * 64,
        revision=revision,
        lifecycle=OperationLifecycle.RUNNING,
        phase_code=phase_code,
        started_at=_STARTED,
        updated_at=event.timestamp,
        execution_deadline=_STARTED + timedelta(minutes=50),
        cleanup_deadline=None,
        cancellation_requested_at=None,
        cancellation_acknowledged_at=None,
        event_cursor=event.sequence,
        events=(event,),
    )


def _write_history(
    root: Path,
) -> tuple[OperationJournalRepository, OperationRegistry, tuple[OperationPersistedSnapshot, ...]]:
    registry = _registry()
    identity = OperationIdentity(
        operation_id=_OPERATION_ID,
        definition_id=_DEFINITION_ID,
        subject_ref="profile:active",
    )
    events = (
        OperationPhaseEvent(
            identity=identity,
            revision=0,
            sequence=1,
            timestamp=_STARTED,
            code="observation.phase.one",
            phase_code="observation.phase.one",
        ),
        OperationProgressEvent(
            identity=identity,
            revision=1,
            sequence=2,
            timestamp=_STARTED + timedelta(minutes=1),
            code="observation.progress.one",
            completed=2,
            total=4,
            unit_code="observation.items",
        ),
        OperationPhaseEvent(
            identity=identity,
            revision=2,
            sequence=3,
            timestamp=_STARTED + timedelta(minutes=2),
            code="observation.phase.two",
            phase_code="observation.phase.two",
        ),
        OperationProgressEvent(
            identity=identity,
            revision=3,
            sequence=4,
            timestamp=_STARTED + timedelta(minutes=3),
            code="observation.progress.two",
            completed=1,
            total=3,
            unit_code="observation.items",
        ),
    )
    phase_codes = (
        "observation.phase.one",
        "observation.phase.one",
        "observation.phase.two",
        "observation.phase.two",
    )
    snapshots = tuple(
        _snapshot(registry, revision=revision, event=event, phase_code=phase_codes[revision])
        for revision, event in enumerate(events)
    )
    lease = _lease()
    lease_result = asyncio.run(
        OperationLeaseFilesystemRepository(storage_root=root).acquire(lease, observed_at=lease.acquired_at)
    )
    assert lease_result.current == lease
    repository = OperationJournalRepository(storage_root=root)
    asyncio.run(repository.create(snapshots[0], lease=lease))
    for predecessor, successor in pairwise(snapshots):
        asyncio.run(repository.commit(successor, expected_revision=predecessor.revision, lease=lease))
    return repository, registry, snapshots


def test_observation_projects_one_anchor_and_reconnects_without_mutation(tmp_path: Path) -> None:
    repository, registry, snapshots = _write_history(tmp_path)
    service = OperationObservationService(reader=repository, registry=registry)
    journal_path = tmp_path / "operation-journals" / f"{_OPERATION_ID}.json"
    stable_bytes = journal_path.read_bytes()

    first = asyncio.run(
        service.observe(OperationObservationRequestV1(operation_id=_OPERATION_ID, after_cursor=0, page_limit=2))
    )
    assert isinstance(first, OperationObservationSuccessV1)
    assert first.projection.revision == snapshots[-1].revision
    assert first.projection.anchor_cursor == snapshots[-1].event_cursor
    assert first.projection.lifecycle is OperationLifecycle.RUNNING
    assert first.projection.terminal_condition is None
    assert first.projection.effect is OperationEffect.NONE
    assert first.projection.progress is not None
    assert first.projection.progress.completed == 1
    assert first.projection.progress.total == 3
    assert first.projection.progress.phase_code == "observation.phase.two"
    assert tuple(event.sequence for event in first.event_page.events) == (1, 2)
    assert isinstance(first.event_page.events[-1], OperationPublicProgressEventV1)

    reconnect = asyncio.run(
        service.observe(
            OperationObservationRequestV1(
                operation_id=_OPERATION_ID,
                after_cursor=first.event_page.next_cursor,
                page_limit=2,
            )
        )
    )
    assert isinstance(reconnect, OperationObservationSuccessV1)
    assert reconnect.projection == first.projection
    assert tuple(event.sequence for event in reconnect.event_page.events) == (3, 4)
    caught_up = asyncio.run(
        service.observe(OperationObservationRequestV1(operation_id=_OPERATION_ID, after_cursor=4, page_limit=2))
    )
    assert isinstance(caught_up, OperationObservationSuccessV1)
    assert caught_up.event_page.status is OperationReplayStatus.CAUGHT_UP
    assert caught_up.event_page.events == ()
    assert journal_path.read_bytes() == stable_bytes


def test_observation_returns_closed_safe_refusals(tmp_path: Path) -> None:
    repository, registry, snapshots = _write_history(tmp_path)
    service = OperationObservationService(reader=repository, registry=registry)

    cases = (
        (
            OperationObservationVersionHeader(observation_version=2),
            OperationObservationRefusalCode.UNSUPPORTED_VERSION,
        ),
        (OperationObservationVersionHeader(observation_version=1), OperationObservationRefusalCode.INVALID_CURSOR),
        (
            OperationObservationRequestV1(operation_id="e" * 64, after_cursor=0, page_limit=1),
            OperationObservationRefusalCode.UNKNOWN_OPERATION,
        ),
        (
            OperationObservationRequestV1(
                operation_id=_OPERATION_ID,
                after_cursor=snapshots[-1].event_cursor + 1,
                page_limit=1,
            ),
            OperationObservationRefusalCode.CURSOR_AHEAD,
        ),
    )
    for request, expected_code in cases:
        result = asyncio.run(service.observe(request))
        assert isinstance(result, OperationObservationRefusalV1)
        assert result.code is expected_code
        assert result.diagnostic_ref is None

    changed_contract = registry.public_registrations[0].contract.model_copy(
        update={"definition_contract_digest": "f" * 64}
    )
    drifted_registry = registry.model_copy(
        update={
            "public_registrations": (
                registry.public_registrations[0].model_copy(update={"contract": changed_contract}),
            )
        }
    )
    mismatch = asyncio.run(
        OperationObservationService(reader=repository, registry=drifted_registry).observe(
            OperationObservationRequestV1(operation_id=_OPERATION_ID, after_cursor=0, page_limit=1)
        )
    )
    assert isinstance(mismatch, OperationObservationRefusalV1)
    assert mismatch.code is OperationObservationRefusalCode.DEFINITION_CONTRACT_MISMATCH


@pytest.mark.parametrize("status", (OperationReplayStatus.EXPIRED, OperationReplayStatus.COMPACTED))
def test_observation_resynchronization_replaces_progress_from_authoritative_checkpoint(
    tmp_path: Path,
    status: OperationReplayStatus,
) -> None:
    repository, registry, snapshots = _write_history(tmp_path)
    current = snapshots[-1]
    history = asyncio.run(repository.read_observation(_OPERATION_ID, 0, limit=4)).progress_fold.events
    progress_at_two = history[1]
    assert isinstance(progress_at_two, OperationProgressEvent)
    materialization = OperationObservationMaterialization(
        snapshot=current,
        anchor_cursor=4,
        replay=OperationReplayPage(
            status=status,
            requested_cursor=0,
            events=(),
            next_cursor=2,
            restart_cursor=2,
        ),
        progress_fold=OperationProgressFoldInput(
            checkpoint=OperationProgressFoldCheckpoint(
                identity=current.identity,
                through_cursor=2,
                phase_code="observation.phase.one",
                progress_event=progress_at_two,
            ),
            events=history[2:],
        ),
    )

    result = OperationObservationService(reader=repository, registry=registry)._project(materialization)

    assert result.event_page.status is status
    assert result.event_page.events == ()
    assert result.event_page.next_cursor == 2
    assert result.projection.progress is not None
    assert result.projection.progress.completed == 1
    assert result.projection.progress.phase_code == "observation.phase.two"
