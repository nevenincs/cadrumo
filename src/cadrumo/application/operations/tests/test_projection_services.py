"""Real-adapter tests for safe projection and public operation controls."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import BaseModel

from ....adapters.persistence.operations import (
    OperationJournalRepository,
    OperationLeaseFilesystemRepository,
    operation_secure_reference_repository,
)
from ....core import (
    STRICT_FROZEN_CONFIG,
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
    OperationLifecycle,
    OperationTerminalCondition,
)
from ....tests.secure_sql import isolated_runtime_profile
from .. import (
    OperationBaselinePolicy,
    OperationCancellationRefusalCode,
    OperationCancellationRequestV1,
    OperationCancellationService,
    OperationCancellationSuccessV1,
    OperationCapabilities,
    OperationConflictScope,
    OperationDefinition,
    OperationDetachRequestV1,
    OperationDetachService,
    OperationDetachSuccessV1,
    OperationExecutorContext,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationIdentity,
    OperationOwnedResource,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationRegistry,
    OperationReplayPolicy,
    OperationRequest,
    OperationRequestStoragePolicy,
    OperationResponseControlRequestV1,
    OperationResponseControlService,
    OperationResponseControlSuccessV1,
    OperationReviewProjectionReferenceV1,
    OperationReviewProjectionRefusalCode,
    OperationReviewProjectionRequestV1,
    OperationReviewProjectionService,
    OperationReviewProjectionSuccessV1,
    OperationReviewProjectionVersionHeader,
    OperationSchemaBindingV1,
    OperationSensitiveInputPolicy,
    OperationSupervisor,
    OperationTerminalReceipt,
    OperationWorkspaceRefreshTargetRefusalCode,
    OperationWorkspaceRefreshTargetRequestV1,
    OperationWorkspaceRefreshTargetService,
    OperationWorkspaceRefreshTargetSuccessV1,
    OperationWorkspaceRefreshTargetVersionHeader,
    operation_public_schema_reference,
)
from .._events import OperationInteractionEvent, OperationPhaseEvent, OperationTerminalEvent
from .._interactions import OperationInteractionRequest, OperationPendingInteraction, OperationResponseIntent
from .._journal import OperationPersistedSnapshot
from .._leases import OperationOwnerLease, operation_conflict_scope_reference
from .._projection_services import BoundOperationSecureResponseAuthority

_NOW = datetime(2026, 8, 24, 12, tzinfo=UTC)
_OPERATION_ID = "1" * 64
_INTERACTION_ID = "2" * 64
_TOKEN = "3" * 64
_PROPOSAL = "4" * 64
_DEFINITION_ID = "operations.projection.test"

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class ProjectionRequest(BaseModel):
    model_config = STRICT_FROZEN_CONFIG
    subject_code: str


class ProjectionResult(BaseModel):
    model_config = STRICT_FROZEN_CONFIG
    result_code: str


class ReviewedOperand(BaseModel):
    model_config = STRICT_FROZEN_CONFIG
    summary_code: str


class SafeReviewProjection(BaseModel):
    model_config = STRICT_FROZEN_CONFIG
    summary_code: str


class ReviewResponseSchema(BaseModel):
    model_config = STRICT_FROZEN_CONFIG
    intent: OperationResponseIntent


class WorkspaceRefreshTarget(BaseModel):
    model_config = STRICT_FROZEN_CONFIG
    workspace_coordinate: str


class ProjectionExecutor:
    async def execute(
        self,
        request: OperationRequest[ProjectionRequest],
        context: OperationExecutorContext,
    ) -> str | None:
        del context
        return request.subject_ref


def _build_executor() -> ProjectionExecutor:
    return ProjectionExecutor()


def _project_review(operand: BaseModel, interaction: OperationInteractionRequest) -> BaseModel:
    del interaction
    return SafeReviewProjection(summary_code=ReviewedOperand.model_validate(operand).summary_code)


def _refresh_target(receipt: OperationTerminalReceipt) -> BaseModel:
    del receipt
    return WorkspaceRefreshTarget(workspace_coordinate="profile:active")


def _unsafe_review_projection(operand: BaseModel, interaction: OperationInteractionRequest) -> BaseModel:
    del operand, interaction
    return WorkspaceRefreshTarget(workspace_coordinate="wrong-model")


def _unsafe_refresh_target(receipt: OperationTerminalReceipt) -> BaseModel:
    del receipt
    return SafeReviewProjection(summary_code="wrong-model")


def _registry(
    *,
    close_policy: OperationClosePolicy = OperationClosePolicy.DETACH_ALLOWED,
    review_projector: Callable[[BaseModel, OperationInteractionRequest], BaseModel] = _project_review,
    refresh_adapter: Callable[[OperationTerminalReceipt], BaseModel] = _refresh_target,
    include_refresh: bool = True,
) -> OperationRegistry:
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
        permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
        close_policy=close_policy,
    )
    definition = OperationDefinition(
        definition_id=_DEFINITION_ID,
        request_type=ProjectionRequest,
        result_type=ProjectionResult,
        executor_factory=OperationExecutorFactory(
            request_type=ProjectionRequest,
            executor_type=ProjectionExecutor,
            build=_build_executor,
        ),
        phase_codes=("projection.running",),
        interaction_kinds=frozenset({OperationInteractionKind.REVIEW}),
        capabilities=capabilities,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.TUI}),
    )
    registration = OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id="operations.projection.request",
            schema_version=1,
            model_type=ProjectionRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id="operations.projection.result",
            schema_version=1,
            model_type=ProjectionResult,
        ),
        review_projection_schema=OperationSchemaBindingV1.bind(
            schema_id="operations.projection.review",
            schema_version=1,
            model_type=SafeReviewProjection,
        ),
        interaction_response_schema=OperationSchemaBindingV1.bind(
            schema_id="operations.projection.response",
            schema_version=1,
            model_type=ReviewResponseSchema,
        ),
        workspace_refresh_target_schema=(
            OperationSchemaBindingV1.bind(
                schema_id="operations.projection.refresh",
                schema_version=1,
                model_type=WorkspaceRefreshTarget,
            )
            if include_refresh
            else None
        ),
        reviewed_operand_type=ReviewedOperand,
        review_projector=review_projector,
        workspace_refresh_adapter=refresh_adapter if include_refresh else None,
    )
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,))


def _lease() -> OperationOwnerLease:
    return OperationOwnerLease(
        operation_id=_OPERATION_ID,
        scope_ref=operation_conflict_scope_reference(definition_id=_DEFINITION_ID, subject_ref="profile:active"),
        owner_id="5" * 64,
        token="6" * 64,
        acquired_at=_NOW,
        expires_at=_NOW + timedelta(hours=1),
    )


def _pending(registry: OperationRegistry, *, proposal: str = _PROPOSAL) -> OperationPendingInteraction:
    contract = registry.lookup_public_contract(_DEFINITION_ID)
    assert contract.interaction_response_schema is not None
    request = OperationInteractionRequest(
        interaction_id=_INTERACTION_ID,
        identity=OperationIdentity(
            operation_id=_OPERATION_ID,
            definition_id=_DEFINITION_ID,
            subject_ref="profile:active",
        ),
        revision=0,
        kind=OperationInteractionKind.REVIEW,
        presentation_code="projection.review.ready",
        response_schema_ref=operation_public_schema_reference(contract.interaction_response_schema),
        continuation_digest="7" * 64,
        expires_at=_NOW + timedelta(minutes=30),
    )
    return OperationPendingInteraction.bind(
        request=request,
        response_token=_TOKEN,
        reviewed_proposal_digest=proposal,
    )


def _waiting_snapshot(registry: OperationRegistry, pending: OperationPendingInteraction) -> OperationPersistedSnapshot:
    identity = pending.request.identity
    event = OperationInteractionEvent(
        identity=identity,
        revision=0,
        sequence=1,
        timestamp=_NOW,
        code="operation.interaction.pending",
        interaction_id=pending.request.interaction_id,
    )
    return OperationPersistedSnapshot(
        identity=identity,
        definition_contract_digest=registry.lookup_public_contract(_DEFINITION_ID).definition_contract_digest,
        request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
        request_reference="8" * 64,
        revision=0,
        lifecycle=OperationLifecycle.WAITING_FOR_INTERACTION,
        started_at=_NOW,
        updated_at=_NOW,
        execution_deadline=_NOW + timedelta(hours=1),
        cleanup_deadline=None,
        cancellation_requested_at=None,
        cancellation_acknowledged_at=None,
        cancellation_deferred=False,
        event_cursor=1,
        events=(event,),
        pending_interaction=pending,
    )


def _running_snapshot(registry: OperationRegistry) -> OperationPersistedSnapshot:
    identity = OperationIdentity(
        operation_id=_OPERATION_ID,
        definition_id=_DEFINITION_ID,
        subject_ref="profile:active",
    )
    event = OperationPhaseEvent(
        identity=identity,
        revision=0,
        sequence=1,
        timestamp=_NOW,
        code="projection.running",
        phase_code="projection.running",
    )
    return OperationPersistedSnapshot(
        identity=identity,
        definition_contract_digest=registry.lookup_public_contract(_DEFINITION_ID).definition_contract_digest,
        request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
        request_reference="8" * 64,
        revision=0,
        lifecycle=OperationLifecycle.RUNNING,
        phase_code="projection.running",
        started_at=_NOW,
        updated_at=_NOW,
        execution_deadline=_NOW + timedelta(hours=1),
        cleanup_deadline=None,
        cancellation_requested_at=None,
        cancellation_acknowledged_at=None,
        cancellation_deferred=False,
        event_cursor=1,
        events=(event,),
    )


def _terminal_snapshot(registry: OperationRegistry) -> OperationPersistedSnapshot:
    running = _running_snapshot(registry)
    receipt = OperationTerminalReceipt(
        identity=running.identity,
        revision=1,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.UPDATED,
        settled_at=_NOW + timedelta(minutes=1),
        result_ref="result:projection-complete",
    )
    event = OperationTerminalEvent(
        identity=running.identity,
        revision=1,
        sequence=2,
        timestamp=receipt.settled_at,
        code="operation.terminal",
        receipt=receipt,
    )
    return OperationPersistedSnapshot.model_validate(
        running.model_copy(
            update={
                "revision": 1,
                "lifecycle": OperationLifecycle.TERMINAL,
                "terminal_condition": OperationTerminalCondition.SUCCEEDED,
                "effect": OperationEffect.UPDATED,
                "updated_at": receipt.settled_at,
                "event_cursor": 2,
                "events": (event,),
                "terminal_receipt": receipt,
            }
        ).model_dump()
    )


def _write(root: Path, repository: OperationJournalRepository, snapshot: OperationPersistedSnapshot) -> None:
    lease = _lease()
    observed = asyncio.run(OperationLeaseFilesystemRepository(storage_root=root).acquire(lease, observed_at=_NOW))
    assert observed.current == lease
    asyncio.run(repository.create(snapshot, lease=lease))


def test_review_resolution_uses_encrypted_operand_and_is_read_only(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        root = tmp_path / "durable"
        registry = _registry()
        operands = operation_secure_reference_repository(objects=profile.repository)
        proposal = asyncio.run(operands.put(ReviewedOperand(summary_code="safe.review"), written_at=_NOW))
        pending = _pending(registry, proposal=proposal)
        repository = OperationJournalRepository(storage_root=root)
        _write(root, repository, _waiting_snapshot(registry, pending))
        journal_path = root / "operation-journals" / f"{_OPERATION_ID}.json"
        before = journal_path.read_bytes()
        contract = registry.lookup_public_contract(_DEFINITION_ID)
        assert contract.review_projection_schema is not None
        request = OperationReviewProjectionRequestV1(
            reference=OperationReviewProjectionReferenceV1(
                operation_id=_OPERATION_ID,
                interaction_id=_INTERACTION_ID,
                revision=0,
                review_projection_schema=contract.review_projection_schema,
                definition_contract_digest=contract.definition_contract_digest,
                expires_at=pending.request.expires_at,
            )
        )
        service = OperationReviewProjectionService(
            reader=repository,
            registry=registry,
            operands=operands,
            clock=lambda: _NOW,
        )

        result = asyncio.run(service.resolve(request))
        stale = asyncio.run(
            service.resolve(
                request.model_copy(
                    update={"reference": request.reference.model_copy(update={"interaction_id": "9" * 64})}
                )
            )
        )
        expired = asyncio.run(
            OperationReviewProjectionService(
                reader=repository,
                registry=registry,
                operands=operands,
                clock=lambda: _NOW + timedelta(hours=1),
            ).resolve(request)
        )
        digest_mismatch = asyncio.run(
            service.resolve(
                request.model_copy(
                    update={"reference": request.reference.model_copy(update={"definition_contract_digest": "a" * 64})}
                )
            )
        )
        assert contract.result_schema is not None
        schema_mismatch = asyncio.run(
            service.resolve(
                request.model_copy(
                    update={
                        "reference": request.reference.model_copy(
                            update={"review_projection_schema": contract.result_schema}
                        )
                    }
                )
            )
        )
        unsafe_output = asyncio.run(
            OperationReviewProjectionService(
                reader=repository,
                registry=_registry(review_projector=_unsafe_review_projection),
                operands=operands,
                clock=lambda: _NOW,
            ).resolve(request)
        )

        assert isinstance(result, OperationReviewProjectionSuccessV1)
        assert result.projection == SafeReviewProjection(summary_code="safe.review")
        assert stale.code is OperationReviewProjectionRefusalCode.STALE_REVIEW_REFERENCE
        assert expired.code is OperationReviewProjectionRefusalCode.REVIEW_EXPIRED
        assert digest_mismatch.code is OperationReviewProjectionRefusalCode.DEFINITION_CONTRACT_MISMATCH
        assert schema_mismatch.code is OperationReviewProjectionRefusalCode.REVIEW_SCHEMA_MISMATCH
        assert unsafe_output.code is OperationReviewProjectionRefusalCode.REVIEW_PROJECTION_UNAVAILABLE
        assert journal_path.read_bytes() == before
        assert _TOKEN.encode() not in before and proposal.encode() in before
        assert "result_ref" not in type(request).model_fields


def test_refresh_target_resolves_only_authoritative_successful_terminal_receipt(tmp_path: Path) -> None:
    root = tmp_path / "durable"
    registry = _registry()
    repository = OperationJournalRepository(storage_root=root)
    terminal = _terminal_snapshot(registry)
    _write(root, repository, _running_snapshot(registry))
    asyncio.run(repository.commit(terminal, expected_revision=0, lease=_lease()))
    contract = registry.lookup_public_contract(_DEFINITION_ID)
    assert contract.workspace_refresh_target_schema is not None
    request = OperationWorkspaceRefreshTargetRequestV1(
        operation_id=_OPERATION_ID,
        terminal_revision=terminal.revision,
        definition_contract_digest=contract.definition_contract_digest,
        target_schema=contract.workspace_refresh_target_schema,
    )
    service = OperationWorkspaceRefreshTargetService(
        reader=OperationJournalRepository(storage_root=root),
        registry=registry,
    )

    result = asyncio.run(service.resolve(request))
    stale = asyncio.run(service.resolve(request.model_copy(update={"terminal_revision": terminal.revision + 1})))
    digest_mismatch = asyncio.run(service.resolve(request.model_copy(update={"definition_contract_digest": "a" * 64})))
    schema_mismatch = asyncio.run(
        service.resolve(request.model_copy(update={"target_schema": contract.request_schema}))
    )
    unsafe_output = asyncio.run(
        OperationWorkspaceRefreshTargetService(
            reader=repository,
            registry=_registry(refresh_adapter=_unsafe_refresh_target),
        ).resolve(request)
    )

    assert isinstance(result, OperationWorkspaceRefreshTargetSuccessV1)
    assert result.target == WorkspaceRefreshTarget(workspace_coordinate="profile:active")
    assert stale.code is OperationWorkspaceRefreshTargetRefusalCode.UNSAFE_REFRESH_TARGET
    assert digest_mismatch.code is OperationWorkspaceRefreshTargetRefusalCode.DEFINITION_CONTRACT_MISMATCH
    assert schema_mismatch.code is OperationWorkspaceRefreshTargetRefusalCode.REFRESH_SCHEMA_MISMATCH
    assert unsafe_output.code is OperationWorkspaceRefreshTargetRefusalCode.UNSAFE_REFRESH_TARGET
    assert "result_ref" not in type(request).model_fields


def test_projection_services_close_version_unknown_pending_terminal_and_adapter_refusals(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        registry = _registry()
        running_root = tmp_path / "running"
        running_repository = OperationJournalRepository(storage_root=running_root)
        _write(running_root, running_repository, _running_snapshot(registry))
        operands = operation_secure_reference_repository(objects=profile.repository)
        review_service = OperationReviewProjectionService(
            reader=running_repository,
            registry=registry,
            operands=operands,
            clock=lambda: _NOW,
        )
        contract = registry.lookup_public_contract(_DEFINITION_ID)
        assert contract.review_projection_schema is not None
        not_pending = asyncio.run(
            review_service.resolve(
                OperationReviewProjectionRequestV1(
                    reference=OperationReviewProjectionReferenceV1(
                        operation_id=_OPERATION_ID,
                        interaction_id=_INTERACTION_ID,
                        revision=0,
                        review_projection_schema=contract.review_projection_schema,
                        definition_contract_digest=contract.definition_contract_digest,
                        expires_at=None,
                    )
                )
            )
        )
        unknown = asyncio.run(
            review_service.resolve(
                OperationReviewProjectionRequestV1(
                    reference=OperationReviewProjectionReferenceV1(
                        operation_id="9" * 64,
                        interaction_id=_INTERACTION_ID,
                        revision=0,
                        review_projection_schema=contract.review_projection_schema,
                        definition_contract_digest=contract.definition_contract_digest,
                        expires_at=None,
                    )
                )
            )
        )
        unsupported = asyncio.run(
            review_service.resolve(OperationReviewProjectionVersionHeader(review_projection_version=2))
        )

        assert not_pending.code is OperationReviewProjectionRefusalCode.REVIEW_NOT_PENDING
        assert unknown.code is OperationReviewProjectionRefusalCode.UNKNOWN_OPERATION
        assert unsupported.code is OperationReviewProjectionRefusalCode.UNSUPPORTED_VERSION

        assert contract.workspace_refresh_target_schema is not None
        refresh_request = OperationWorkspaceRefreshTargetRequestV1(
            operation_id=_OPERATION_ID,
            terminal_revision=0,
            definition_contract_digest=contract.definition_contract_digest,
            target_schema=contract.workspace_refresh_target_schema,
        )
        refresh_service = OperationWorkspaceRefreshTargetService(reader=running_repository, registry=registry)
        not_terminal = asyncio.run(refresh_service.resolve(refresh_request))
        refresh_unsupported = asyncio.run(
            refresh_service.resolve(OperationWorkspaceRefreshTargetVersionHeader(refresh_target_version=2))
        )

        no_adapter_registry = _registry(include_refresh=False)
        no_adapter_root = tmp_path / "no-adapter"
        no_adapter_repository = OperationJournalRepository(storage_root=no_adapter_root)
        no_adapter_terminal = _terminal_snapshot(no_adapter_registry)
        _write(no_adapter_root, no_adapter_repository, _running_snapshot(no_adapter_registry))
        asyncio.run(no_adapter_repository.commit(no_adapter_terminal, expected_revision=0, lease=_lease()))
        no_adapter_contract = no_adapter_registry.lookup_public_contract(_DEFINITION_ID)
        assert no_adapter_contract.result_schema is not None
        unavailable = asyncio.run(
            OperationWorkspaceRefreshTargetService(
                reader=OperationJournalRepository(storage_root=no_adapter_root),
                registry=no_adapter_registry,
            ).resolve(
                OperationWorkspaceRefreshTargetRequestV1(
                    operation_id=_OPERATION_ID,
                    terminal_revision=1,
                    definition_contract_digest=no_adapter_contract.definition_contract_digest,
                    target_schema=no_adapter_contract.result_schema,
                )
            )
        )

        assert not_terminal.code is OperationWorkspaceRefreshTargetRefusalCode.OPERATION_NOT_TERMINAL
        assert refresh_unsupported.code is OperationWorkspaceRefreshTargetRefusalCode.UNSUPPORTED_VERSION
        assert unavailable.code is OperationWorkspaceRefreshTargetRefusalCode.REFRESH_ADAPTER_UNAVAILABLE


def test_response_control_requires_separately_bound_runtime_bearer(tmp_path: Path) -> None:
    root = tmp_path / "durable"
    registry = _registry()
    pending = _pending(registry)
    repository = OperationJournalRepository(storage_root=root)
    _write(root, repository, _waiting_snapshot(registry, pending))
    authority = BoundOperationSecureResponseAuthority.bind(
        operation_id=_OPERATION_ID,
        interaction_id=_INTERACTION_ID,
        revision=0,
        reviewed_proposal_digest=_PROPOSAL,
        actor_ref="operator:reviewer",
        expires_at=pending.request.expires_at,
        intents=frozenset({OperationResponseIntent.APPLY, OperationResponseIntent.REJECT}),
        response_token=_TOKEN,
        clock=lambda: _NOW,
    )
    request = OperationResponseControlRequestV1(
        operation_id=_OPERATION_ID,
        interaction_id=_INTERACTION_ID,
        revision=0,
        actor_ref="operator:reviewer",
    )
    service = OperationResponseControlService(reader=repository, registry=registry, authority=authority)

    result = asyncio.run(service.inspect(request))
    authority.close()
    closed = asyncio.run(service.inspect(request))

    assert isinstance(result, OperationResponseControlSuccessV1)
    assert result.available and result.permitted_intents == frozenset(OperationResponseIntent)
    assert closed.outcome == "refused"
    assert all(value == 0 for value in authority._token)
    assert _TOKEN not in result.model_dump_json()


def test_cancellation_and_detach_delegate_to_real_supervisor_ports(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        root = tmp_path / "durable"
        registry = _registry()
        repository = OperationJournalRepository(storage_root=root)
        leases = OperationLeaseFilesystemRepository(storage_root=root)
        _write(root, repository, _running_snapshot(registry))
        supervisor = OperationSupervisor(
            registry=registry,
            journal=repository,
            event_stream=repository,
            leases=leases,
            operands=operation_secure_reference_repository(objects=profile.repository),
            owner_id="5" * 64,
            lease_token_factory=lambda: "6" * 64,
            clock=lambda: _NOW,
            lease_duration=timedelta(hours=1),
            cleanup_timeout=timedelta(minutes=5),
        )
        detach = asyncio.run(
            OperationDetachService(reader=repository, registry=registry, supervisor=supervisor).detach(
                OperationDetachRequestV1(operation_id=_OPERATION_ID, expected_revision=0)
            )
        )
        cancelled = asyncio.run(
            OperationCancellationService(reader=repository, registry=registry, supervisor=supervisor).request(
                OperationCancellationRequestV1(operation_id=_OPERATION_ID, expected_revision=0)
            )
        )
        stale = asyncio.run(
            OperationCancellationService(reader=repository, registry=registry, supervisor=supervisor).request(
                OperationCancellationRequestV1(operation_id=_OPERATION_ID, expected_revision=0)
            )
        )
        journal_path = root / "operation-journals" / f"{_OPERATION_ID}.json"
        settled_bytes = journal_path.read_bytes()
        with pytest.raises(ValueError, match="expected revision is stale"):
            asyncio.run(supervisor.request_cancel(_OPERATION_ID, expected_revision=0))

        assert isinstance(detach, OperationDetachSuccessV1)
        assert isinstance(cancelled, OperationCancellationSuccessV1)
        assert stale.code is OperationCancellationRefusalCode.STALE_OPERATION_REVISION
        assert journal_path.read_bytes() == settled_bytes
