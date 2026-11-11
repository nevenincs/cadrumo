"""Shared contracts, registry builders and journal fixtures for the projection service tests."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

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
from cadrumo.application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
)
from cadrumo.application.operations.interactions import (
    OperationInteractionRequest,
    OperationPendingInteraction,
    OperationResponseIntent,
)
from cadrumo.application.operations.models import (
    OperationFailureErrorCode,
    OperationIdentity,
    OperationRequest,
    OperationTerminalReceipt,
)
from cadrumo.application.operations.observation import OperationObservationService
from cadrumo.application.operations.operation_definition import OperationDefinition, OperationExecutorFactory
from cadrumo.application.operations.owner import OperationExecutorContext
from cadrumo.application.operations.persistence.events import (
    OperationInteractionEvent,
    OperationPhaseEvent,
    OperationTerminalEvent,
)
from cadrumo.application.operations.persistence.journal import OperationPersistedSnapshot
from cadrumo.application.operations.persistence.leases import (
    OperationOwnerLease,
    operation_conflict_scope_reference,
)
from cadrumo.application.operations.registry import (
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationRegistry,
    OperationSchemaBindingV1,
    operation_public_schema_reference,
)
from cadrumo.application.operations.subject_reference import OperationSubjectReferenceV1
from cadrumo.core.models import STRICT_FROZEN_CONFIG
from cadrumo.core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
    OperationLifecycle,
    OperationTerminalCondition,
)

from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope

_YEAR = filing_year_envelope().horizon

NOW = datetime(_YEAR, 8, 24, 12, tzinfo=UTC)


OPERATION_ID = "1" * 64


INTERACTION_ID = "2" * 64


TOKEN = "3" * 64


PROPOSAL = "4" * 64


DEFINITION_ID = "operations.projection.test"


REFUSAL_CODE = "REFUSED_OPERATION_SUBJECT_BUSY"


REFUSAL_SENTINEL = "PRIVATE-REFUSAL-DETAIL-SENTINEL"


class ProjectionRequest(BaseModel):
    model_config = STRICT_FROZEN_CONFIG
    subject_code: str


class ProjectionResult(BaseModel):
    model_config = STRICT_FROZEN_CONFIG
    result_code: str


class PublicProjectionResult(BaseModel):
    model_config = STRICT_FROZEN_CONFIG
    result_code: str


class PrivateRefusalDetail(BaseModel):
    model_config = STRICT_FROZEN_CONFIG
    detail_code: str
    private_sentinel: str


class PublicRefusalDetail(BaseModel):
    model_config = STRICT_FROZEN_CONFIG
    detail_code: str


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


def project_result(result: BaseModel, receipt: OperationTerminalReceipt) -> BaseModel:
    del receipt
    return PublicProjectionResult(result_code=ProjectionResult.model_validate(result).result_code)


def project_refusal_detail(result: BaseModel, receipt: OperationTerminalReceipt) -> BaseModel:
    """Release only the declared detail code for its exact refused terminal."""
    if (
        type(result) is not PrivateRefusalDetail
        or receipt.condition is not OperationTerminalCondition.REFUSED
        or receipt.refusal_ref != REFUSAL_CODE
    ):
        raise TypeError("refusal detail does not match its registered refused terminal")
    return PublicRefusalDetail(detail_code=result.detail_code)


def unsafe_result_projection(result: BaseModel, receipt: OperationTerminalReceipt) -> BaseModel:
    del result, receipt
    return SafeReviewProjection(summary_code="wrong-model")


def _refresh_target(receipt: OperationTerminalReceipt) -> BaseModel:
    del receipt
    return WorkspaceRefreshTarget(workspace_coordinate="profile:active")


def unsafe_review_projection(operand: BaseModel, interaction: OperationInteractionRequest) -> BaseModel:
    del operand, interaction
    return WorkspaceRefreshTarget(workspace_coordinate="wrong-model")


def unsafe_refresh_target(receipt: OperationTerminalReceipt) -> BaseModel:
    del receipt
    return SafeReviewProjection(summary_code="wrong-model")


def projection_services_registry(
    *,
    close_policy: OperationClosePolicy = OperationClosePolicy.DETACH_ALLOWED,
    review_projector: Callable[[BaseModel, OperationInteractionRequest], BaseModel] = _project_review,
    result_projector: Callable[[BaseModel, OperationTerminalReceipt], BaseModel] | None = None,
    result_schema_type: type[BaseModel] = ProjectionResult,
    result_type: type[BaseModel] = ProjectionResult,
    refusal_detail_codes: frozenset[OperationFailureErrorCode] = frozenset(),
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
        definition_id=DEFINITION_ID,
        request_type=ProjectionRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=result_type,
        executor_factory=OperationExecutorFactory(
            request_type=ProjectionRequest,
            executor_type=ProjectionExecutor,
            build=_build_executor,
        ),
        phase_codes=("projection.running",),
        interaction_kinds=frozenset({OperationInteractionKind.REVIEW}),
        capabilities=capabilities,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        refusal_detail_codes=refusal_detail_codes,
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
            model_type=result_schema_type,
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
        result_projector=result_projector,
        workspace_refresh_adapter=refresh_adapter if include_refresh else None,
    )
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,))


def projection_services_lease() -> OperationOwnerLease:
    return OperationOwnerLease(
        operation_id=OPERATION_ID,
        scope_ref=operation_conflict_scope_reference(definition_id=DEFINITION_ID, subject_ref="profile:active"),
        owner_id="5" * 64,
        token="6" * 64,
        acquired_at=NOW,
        expires_at=NOW + timedelta(hours=1),
    )


def projection_services_pending(
    registry: OperationRegistry, *, proposal: str = PROPOSAL
) -> OperationPendingInteraction:
    contract = registry.lookup_public_contract(DEFINITION_ID)
    assert contract.interaction_response_schema is not None
    request = OperationInteractionRequest(
        interaction_id=INTERACTION_ID,
        identity=OperationIdentity(
            operation_id=OPERATION_ID,
            definition_id=DEFINITION_ID,
            subject_ref="profile:active",
        ),
        revision=0,
        kind=OperationInteractionKind.REVIEW,
        presentation_code="projection.review.ready",
        response_schema_ref=operation_public_schema_reference(contract.interaction_response_schema),
        continuation_digest="7" * 64,
        expires_at=NOW + timedelta(minutes=30),
    )
    return OperationPendingInteraction.bind(
        request=request,
        response_token=TOKEN,
        reviewed_proposal_digest=proposal,
        baseline_digest="9" * 64,
        proposed_effect_digest="a" * 64,
    )


def waiting_snapshot(registry: OperationRegistry, pending: OperationPendingInteraction) -> OperationPersistedSnapshot:
    identity = pending.request.identity
    event = OperationInteractionEvent(
        identity=identity,
        revision=0,
        sequence=1,
        timestamp=NOW,
        code="operation.interaction.pending",
        interaction_id=pending.request.interaction_id,
    )
    return OperationPersistedSnapshot(
        identity=identity,
        definition_contract_digest=registry.lookup_public_contract(DEFINITION_ID).definition_contract_digest,
        request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
        request_reference="8" * 64,
        revision=0,
        lifecycle=OperationLifecycle.WAITING_FOR_INTERACTION,
        started_at=NOW,
        updated_at=NOW,
        execution_deadline=NOW + timedelta(hours=1),
        cleanup_deadline=None,
        cancellation_requested_at=None,
        cancellation_acknowledged_at=None,
        cancellation_deferred=False,
        event_cursor=1,
        events=(event,),
        pending_interaction=pending,
    )


def running_snapshot(registry: OperationRegistry) -> OperationPersistedSnapshot:
    identity = OperationIdentity(
        operation_id=OPERATION_ID,
        definition_id=DEFINITION_ID,
        subject_ref="profile:active",
    )
    event = OperationPhaseEvent(
        identity=identity,
        revision=0,
        sequence=1,
        timestamp=NOW,
        code="projection.running",
        phase_code="projection.running",
    )
    return OperationPersistedSnapshot(
        identity=identity,
        definition_contract_digest=registry.lookup_public_contract(DEFINITION_ID).definition_contract_digest,
        request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
        request_reference="8" * 64,
        revision=0,
        lifecycle=OperationLifecycle.RUNNING,
        phase_code="projection.running",
        started_at=NOW,
        updated_at=NOW,
        execution_deadline=NOW + timedelta(hours=1),
        cleanup_deadline=None,
        cancellation_requested_at=None,
        cancellation_acknowledged_at=None,
        cancellation_deferred=False,
        event_cursor=1,
        events=(event,),
    )


def terminal_snapshot(
    registry: OperationRegistry,
    *,
    result_ref: str = "result:projection-complete",
    condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
    effect: OperationEffect = OperationEffect.UPDATED,
    failure_error_code: str | None = None,
) -> OperationPersistedSnapshot:
    running = running_snapshot(registry)
    receipt = OperationTerminalReceipt(
        identity=running.identity,
        revision=1,
        condition=condition,
        effect=effect,
        settled_at=NOW + timedelta(minutes=1),
        result_ref=result_ref,
        failure_error_code=failure_error_code,
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
                "terminal_condition": condition,
                "effect": effect,
                "updated_at": receipt.settled_at,
                "event_cursor": 2,
                "events": (event,),
                "terminal_receipt": receipt,
            }
        ).model_dump()
    )


def refused_snapshot(
    registry: OperationRegistry,
    *,
    detail_ref: str,
    effect: OperationEffect = OperationEffect.UNKNOWN,
) -> OperationPersistedSnapshot:
    """Build one durable refused receipt with a separate encrypted-detail reference."""
    running = running_snapshot(registry)
    receipt = OperationTerminalReceipt(
        identity=running.identity,
        revision=1,
        condition=OperationTerminalCondition.REFUSED,
        effect=effect,
        settled_at=NOW + timedelta(minutes=1),
        refusal_ref=REFUSAL_CODE,
        refusal_detail_ref=detail_ref,
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
                "terminal_condition": OperationTerminalCondition.REFUSED,
                "effect": effect,
                "updated_at": receipt.settled_at,
                "event_cursor": 2,
                "events": (event,),
                "terminal_receipt": receipt,
            }
        ).model_dump()
    )


def observe_refused_operation(
    repository: OperationJournalRepository,
    registry: OperationRegistry,
    *,
    expected_effect: OperationEffect,
) -> OperationObservationSuccessV1:
    """Re-read the durable public lifecycle independently of result projection."""
    observed = asyncio.run(
        OperationObservationService(reader=repository, registry=registry).observe(
            OperationObservationRequestV1(operation_id=OPERATION_ID, after_cursor=0, page_limit=32)
        )
    )
    assert isinstance(observed, OperationObservationSuccessV1)
    assert observed.projection.lifecycle is OperationLifecycle.TERMINAL
    assert observed.projection.terminal_condition is OperationTerminalCondition.REFUSED
    assert observed.projection.refusal_ref == REFUSAL_CODE
    assert observed.projection.effect is expected_effect
    assert observed.projection.result_ref is None
    return observed


def write(root: Path, repository: OperationJournalRepository, snapshot: OperationPersistedSnapshot) -> None:
    lease = projection_services_lease()
    observed = asyncio.run(OperationLeaseFilesystemRepository(storage_root=root).acquire(lease, observed_at=NOW))
    assert observed.current == lease
    asyncio.run(repository.create(snapshot, lease=lease))
