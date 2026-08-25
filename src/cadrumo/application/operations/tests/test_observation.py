"""Real-adapter tests for the canonical public operation observation service."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path

import pytest
from pydantic import BaseModel

from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from cadrumo.application.operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationOwnedResource,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from cadrumo.application.operations.frontend_contracts import (
    OperationObservationRefusalCode,
    OperationObservationRefusalV1,
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationObservationVersionHeader,
    OperationPublicProgressEventV1,
    OperationReviewAvailableInteractionV1,
    OperationUnsupportedInteractionV1,
)
from cadrumo.application.operations.models import (
    OperationIdentity,
    OperationReconciliationOutcome,
    OperationRequest,
    OperationTerminalReceipt,
)
from cadrumo.application.operations.observation import OperationObservationService
from cadrumo.application.operations.persistence.events import (
    OperationDiagnosticEvent,
    OperationEffectEvent,
    OperationInteractionEvent,
    OperationLogRecord,
    OperationNoticeEvent,
    OperationPhaseEvent,
    OperationProgressEvent,
    OperationReconciliationEvent,
    OperationTerminalEvent,
)
from cadrumo.application.operations.persistence.journal import (
    OperationObservationMaterialization,
    OperationPersistedSnapshot,
    OperationProgressFoldCheckpoint,
    OperationProgressFoldInput,
)
from cadrumo.application.operations.persistence.leases import (
    OperationOwnerLease,
    operation_conflict_scope_reference,
)
from cadrumo.application.operations.persistence.replay import (
    OperationReplayPage,
    OperationReplayStatus,
)
from cadrumo.application.operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationRegistry,
    OperationSchemaBindingV1,
    operation_public_schema_reference,
)
from cadrumo.core.operations import OperationInteractionKind

from ....core import (
    STRICT_FROZEN_CONFIG,
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationEventKind,
    OperationLifecycle,
    OperationTerminalCondition,
)
from ..events import OperationLogSeverity
from ..interactions import OperationInteractionRequest, OperationPendingInteraction
from ..owner import OperationExecutorContext

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


class ReviewProjection(BaseModel):
    model_config = STRICT_FROZEN_CONFIG
    summary_code: str


class ReviewOperand(BaseModel):
    model_config = STRICT_FROZEN_CONFIG
    proposal_code: str


class ReviewResponse(BaseModel):
    model_config = STRICT_FROZEN_CONFIG
    intent_code: str


def _review_projector(operand: BaseModel, interaction: OperationInteractionRequest) -> BaseModel:
    del operand, interaction
    return ReviewProjection(summary_code="observation.review")


def _capabilities() -> OperationCapabilities:
    return OperationCapabilities(
        durability=OperationDurability.RECORDED,
        cancellation=OperationCancellation.COOPERATIVE,
        deadline=OperationDeadline.COOPERATIVE,
        replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
        baseline=OperationBaselinePolicy.REQUEST_BOUND,
        request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
        sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
        conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
        owned_resources=frozenset({OperationOwnedResource.ASYNC_TASK}),
        permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
        close_policy=OperationClosePolicy.REQUEST_CANCEL,
    )


def _registry() -> OperationRegistry:
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
        capabilities=_capabilities(),
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


def _review_registry(
    *, interaction_kind: OperationInteractionKind = OperationInteractionKind.REVIEW
) -> OperationRegistry:
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
        interaction_kinds=frozenset({interaction_kind}),
        capabilities=_capabilities(),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.TUI}),
    )
    request_schema = OperationSchemaBindingV1.bind(
        schema_id="operations.observation.request",
        schema_version=1,
        model_type=ObservationRequest,
    )
    if interaction_kind is not OperationInteractionKind.REVIEW:
        registration = OperationPublicDefinitionRegistrationV1.compose(
            definition=definition,
            request_schema=request_schema,
        )
    else:
        registration = OperationPublicDefinitionRegistrationV1.compose(
            definition=definition,
            request_schema=request_schema,
            review_projection_schema=OperationSchemaBindingV1.bind(
                schema_id="operations.observation.review",
                schema_version=1,
                model_type=ReviewProjection,
            ),
            interaction_response_schema=OperationSchemaBindingV1.bind(
                schema_id="operations.observation.response",
                schema_version=1,
                model_type=ReviewResponse,
            ),
            reviewed_operand_type=ReviewOperand,
            review_projector=_review_projector,
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
        cancellation_deferred=False,
        event_cursor=event.sequence,
        events=(event,),
    )


def _write_history(
    root: Path,
    *,
    registry: OperationRegistry | None = None,
) -> tuple[OperationJournalRepository, OperationRegistry, tuple[OperationPersistedSnapshot, ...]]:
    registry = registry or _registry()
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


def _commit_pending(
    repository: OperationJournalRepository,
    registry: OperationRegistry,
    current: OperationPersistedSnapshot,
    *,
    kind: OperationInteractionKind,
    response_schema_ref: str,
) -> OperationPersistedSnapshot:
    interaction = OperationInteractionRequest(
        interaction_id="e" * 64,
        identity=current.identity,
        revision=current.revision + 1,
        kind=kind,
        presentation_code="observation.review.ready",
        response_schema_ref=response_schema_ref,
        continuation_digest="1" * 64,
        expires_at=_STARTED + timedelta(minutes=40),
    )
    pending = OperationPendingInteraction.bind(
        request=interaction,
        response_token="2" * 64,
        reviewed_proposal_digest="3" * 64,
    )
    event = OperationInteractionEvent(
        identity=current.identity,
        revision=current.revision + 1,
        sequence=current.event_cursor + 1,
        timestamp=_STARTED + timedelta(minutes=4),
        code="operation.interaction.pending",
        interaction_id=interaction.interaction_id,
    )
    waiting = OperationPersistedSnapshot.model_validate(
        current.model_copy(
            update={
                "revision": current.revision + 1,
                "lifecycle": OperationLifecycle.WAITING_FOR_INTERACTION,
                "updated_at": event.timestamp,
                "event_cursor": event.sequence,
                "events": (event,),
                "pending_interaction": pending,
            }
        ).model_dump()
    )
    asyncio.run(repository.commit(waiting, expected_revision=current.revision, lease=_lease()))
    assert (
        waiting.definition_contract_digest == registry.lookup_public_contract(_DEFINITION_ID).definition_contract_digest
    )
    return waiting


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

    journal_path = tmp_path / "operation-journals" / f"{_OPERATION_ID}.json"
    journal_path.write_text("{not-json", encoding="utf-8")
    unavailable = asyncio.run(
        service.observe(OperationObservationRequestV1(operation_id=_OPERATION_ID, after_cursor=0, page_limit=1))
    )
    assert isinstance(unavailable, OperationObservationRefusalV1)
    assert unavailable.code is OperationObservationRefusalCode.OBSERVATION_UNAVAILABLE


def test_observation_projects_only_registered_interaction_contracts(tmp_path: Path) -> None:
    review_registry = _review_registry()
    repository, _, snapshots = _write_history(tmp_path / "review", registry=review_registry)
    response_schema = review_registry.lookup_public_contract(_DEFINITION_ID).interaction_response_schema
    assert response_schema is not None
    waiting = _commit_pending(
        repository,
        review_registry,
        snapshots[-1],
        kind=OperationInteractionKind.REVIEW,
        response_schema_ref=operation_public_schema_reference(response_schema),
    )
    observed = asyncio.run(
        OperationObservationService(reader=repository, registry=review_registry).observe(
            OperationObservationRequestV1(
                operation_id=_OPERATION_ID,
                after_cursor=waiting.event_cursor,
                page_limit=1,
            )
        )
    )
    assert isinstance(observed, OperationObservationSuccessV1)
    assert isinstance(observed.projection.pending_interaction, OperationReviewAvailableInteractionV1)
    safe_json = observed.model_dump_json()
    assert "22222222" not in safe_json
    assert "33333333" not in safe_json
    assert "continuation_digest" not in safe_json

    mismatch_repository, _, mismatch_snapshots = _write_history(
        tmp_path / "mismatch",
        registry=review_registry,
    )
    _commit_pending(
        mismatch_repository,
        review_registry,
        mismatch_snapshots[-1],
        kind=OperationInteractionKind.REVIEW,
        response_schema_ref="schema:operations.observation.wrong.v1",
    )
    mismatch = asyncio.run(
        OperationObservationService(reader=mismatch_repository, registry=review_registry).observe(
            OperationObservationRequestV1(operation_id=_OPERATION_ID, after_cursor=0, page_limit=10)
        )
    )
    assert isinstance(mismatch, OperationObservationRefusalV1)
    assert mismatch.code is OperationObservationRefusalCode.DEFINITION_CONTRACT_MISMATCH

    input_registry = _review_registry(interaction_kind=OperationInteractionKind.INPUT)
    input_repository, _, input_snapshots = _write_history(tmp_path / "input", registry=input_registry)
    _commit_pending(
        input_repository,
        input_registry,
        input_snapshots[-1],
        kind=OperationInteractionKind.INPUT,
        response_schema_ref="schema:operations.observation.input.v1",
    )
    unsupported = asyncio.run(
        OperationObservationService(reader=input_repository, registry=input_registry).observe(
            OperationObservationRequestV1(operation_id=_OPERATION_ID, after_cursor=0, page_limit=10)
        )
    )
    assert isinstance(unsupported, OperationObservationSuccessV1)
    assert isinstance(unsupported.projection.pending_interaction, OperationUnsupportedInteractionV1)


def test_observation_projects_every_safe_event_and_terminal_axis_independently(tmp_path: Path) -> None:
    repository, registry, snapshots = _write_history(tmp_path)
    current = snapshots[-1]
    timestamp = _STARTED + timedelta(minutes=4)
    events = (
        OperationLogRecord(
            identity=current.identity,
            revision=current.revision + 1,
            sequence=5,
            timestamp=timestamp,
            code="observation.log",
            severity=OperationLogSeverity.INFO,
            diagnostic_ref=None,
        ),
        OperationEffectEvent(
            identity=current.identity,
            revision=current.revision + 1,
            sequence=6,
            timestamp=timestamp,
            code="observation.effect",
            effect=OperationEffect.UPDATED,
        ),
        OperationNoticeEvent(
            identity=current.identity,
            revision=current.revision + 1,
            sequence=7,
            timestamp=timestamp,
            code="observation.notice",
            notice_code="observation.notice",
        ),
        OperationReconciliationEvent(
            identity=current.identity,
            revision=current.revision + 1,
            sequence=8,
            timestamp=timestamp,
            code="observation.reconciliation",
            outcome=OperationReconciliationOutcome.RECOVERED,
            lease_evidence_ref="4" * 64,
        ),
        OperationDiagnosticEvent(
            identity=current.identity,
            revision=current.revision + 1,
            sequence=9,
            timestamp=timestamp,
            code="observation.diagnostic",
            diagnostic_ref=f"sha256:{'5' * 12}",
        ),
        OperationInteractionEvent(
            identity=current.identity,
            revision=current.revision + 1,
            sequence=10,
            timestamp=timestamp,
            code="observation.interaction",
            interaction_id="6" * 64,
        ),
    )
    enriched = OperationPersistedSnapshot.model_validate(
        current.model_copy(
            update={
                "revision": current.revision + 1,
                "updated_at": timestamp,
                "effect": OperationEffect.UPDATED,
                "event_cursor": 10,
                "events": events,
            }
        ).model_dump()
    )
    asyncio.run(repository.commit(enriched, expected_revision=current.revision, lease=_lease()))
    page = asyncio.run(
        OperationObservationService(reader=repository, registry=registry).observe(
            OperationObservationRequestV1(operation_id=_OPERATION_ID, after_cursor=4, page_limit=10)
        )
    )
    assert isinstance(page, OperationObservationSuccessV1)
    assert tuple(event.kind for event in page.event_page.events) == (
        OperationEventKind.LOG,
        OperationEventKind.EFFECT,
        OperationEventKind.NOTICE,
        OperationEventKind.RECONCILIATION,
        OperationEventKind.DIAGNOSTIC,
        OperationEventKind.INTERACTION,
    )

    settled_at = _STARTED + timedelta(minutes=5)
    receipt = OperationTerminalReceipt(
        identity=current.identity,
        revision=enriched.revision + 1,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.UPDATED,
        settled_at=settled_at,
        result_ref="result:observation-complete",
    )
    terminal_event = OperationTerminalEvent(
        identity=current.identity,
        revision=receipt.revision,
        sequence=11,
        timestamp=settled_at,
        code="operation.terminal",
        receipt=receipt,
    )
    terminal = OperationPersistedSnapshot.model_validate(
        enriched.model_copy(
            update={
                "revision": receipt.revision,
                "lifecycle": OperationLifecycle.TERMINAL,
                "terminal_condition": receipt.condition,
                "updated_at": settled_at,
                "event_cursor": 11,
                "events": (terminal_event,),
                "terminal_receipt": receipt,
            }
        ).model_dump()
    )
    asyncio.run(repository.commit(terminal, expected_revision=enriched.revision, lease=_lease()))
    result = asyncio.run(
        OperationObservationService(reader=repository, registry=registry).observe(
            OperationObservationRequestV1(operation_id=_OPERATION_ID, after_cursor=10, page_limit=1)
        )
    )
    assert isinstance(result, OperationObservationSuccessV1)
    assert result.projection.lifecycle is OperationLifecycle.TERMINAL
    assert result.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert result.projection.effect is OperationEffect.UPDATED
    assert result.projection.result_ref == receipt.result_ref
    assert result.event_page.events[0].kind is OperationEventKind.TERMINAL


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
