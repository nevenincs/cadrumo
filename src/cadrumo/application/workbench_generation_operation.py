"""Human-only registered read of one immutable workbench generation."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import cache
from uuid import UUID

from pydantic import BaseModel

from ..core.async_cleanup import await_cancellation_complete
from ..core.external_constants import OutputLanguage
from ..core.hashing import canonical_json_bytes
from ..core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    profile_operation_subject,
)
from ..core.time.clock import now
from .operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from .operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from .operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID, OperationResultProjectionSuccessV1
from .operations.models import CredentialFreeOperationRequest, OperationRequest
from .operations.owner import OperationExecutorContext
from .operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionContractV1,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from .runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES
from .user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    OperationAccessPolicy,
    OperationAccessRequest,
)
from .user_profile.access_errors import ProfileAccessRefusedError
from .workbench_generation import WorkbenchGenerationV1
from .workbench_generation_projection import WorkbenchGenerationOperationProjection, project_workbench_generation

WORKBENCH_GENERATION_OPERATION_DEFINITION_ID = "workbench.generation"
_PHASE = WORKBENCH_GENERATION_OPERATION_DEFINITION_ID + ".execute"


class WorkbenchGenerationOperationRequest(CredentialFreeOperationRequest):
    """Exact profile and output language; no session or custody material."""

    profile_id: UUID
    output_language: OutputLanguage


type WorkbenchGenerationReader = Callable[
    [OperationExecutorContext, WorkbenchGenerationOperationRequest], Awaitable[WorkbenchGenerationV1]
]


class WorkbenchGenerationExecutor:
    """Capture one generation under the canonical operation owner."""

    def __init__(self, reader: WorkbenchGenerationReader | None) -> None:
        """Retain only the composed reader capability."""
        self.reader = reader

    async def execute(
        self,
        request: OperationRequest[WorkbenchGenerationOperationRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Own the read, encrypted result and NONE effect through cancellation."""
        if (
            request.definition_id != WORKBENCH_GENERATION_OPERATION_DEFINITION_ID
            or request.subject_ref != profile_operation_subject(str(request.payload.profile_id))
            or context.identity.subject_ref != request.subject_ref
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        reader = self.reader
        if reader is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        await context.events.phase(_PHASE)

        async def capture() -> str:
            generation = await reader(context, request.payload)
            if type(generation) is not WorkbenchGenerationV1:
                raise TypeError("workbench reader returned an invalid generation")
            projection = project_workbench_generation(request.payload.profile_id, generation)
            _require_pageable_result(projection)
            result_ref = await context.operands.put(projection, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return result_ref

        return await await_cancellation_complete(capture(), task_name="workbench-generation-capture")


@cache
def _result_contract() -> OperationPublicDefinitionContractV1:
    definition = build_workbench_generation_operation_definition()
    return build_workbench_generation_operation_registration(definition).contract


def _require_pageable_result(projection: WorkbenchGenerationOperationProjection) -> None:
    """Reject a result that the canonical paged release cannot return."""
    contract = _result_contract()
    if contract.result_schema is None:
        raise TypeError("workbench result schema is unavailable")
    document = OperationResultProjectionSuccessV1[WorkbenchGenerationOperationProjection](
        result_schema=contract.result_schema,
        definition_contract_digest=contract.definition_contract_digest,
        projection=projection,
    ).model_dump(mode="json", serialize_as_any=True)
    if len(canonical_json_bytes(document)) > PROJECTION_DOCUMENT_MAX_BYTES:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)


def build_workbench_generation_operation_definition(
    reader: WorkbenchGenerationReader | None = None,
) -> OperationDefinition:
    """Enroll one recorded, read-only generation with a real composed reader."""
    return OperationDefinition(
        definition_id=WORKBENCH_GENERATION_OPERATION_DEFINITION_ID,
        request_type=WorkbenchGenerationOperationRequest,
        result_type=WorkbenchGenerationOperationProjection,
        executor_factory=OperationExecutorFactory(
            request_type=WorkbenchGenerationOperationRequest,
            executor_type=WorkbenchGenerationExecutor,
            build=lambda: WorkbenchGenerationExecutor(reader),
        ),
        phase_codes=(_PHASE,),
        interaction_kinds=frozenset(),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
            sensitive_input=OperationSensitiveInputPolicy.NONE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
    )


def build_workbench_generation_operation_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Expose the exact request and bound generation through canonical schemas."""
    if definition.definition_id != WORKBENCH_GENERATION_OPERATION_DEFINITION_ID:
        raise ValueError("wrong workbench generation definition")
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request",
            schema_version=1,
            model_type=WorkbenchGenerationOperationRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=WorkbenchGenerationOperationProjection,
        ),
        access_resolver=resolve_workbench_generation_access,
    )


def resolve_workbench_generation_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require live human CLI/TUI authority for both profile and tax values."""
    payload = request.payload
    if type(payload) is not WorkbenchGenerationOperationRequest:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if (
        request.definition_id != WORKBENCH_GENERATION_OPERATION_DEFINITION_ID
        or payload.profile_id != context.profile_id
        or request.subject_ref != profile_operation_subject(str(payload.profile_id))
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    disclosures = frozenset[DisclosurePermission]()
    if context.action in {AccessAction.OBSERVE, AccessAction.CANCEL, AccessAction.DETACH}:
        disclosures = frozenset(
            (
                DisclosurePermission(
                    destination_id=context.destination_id,
                    projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                    category=DisclosureCategory.OPERATION_METADATA,
                ),
            )
        )
    elif context.action is AccessAction.RESULT and context.contract.result_schema is not None:
        disclosures = frozenset(
            DisclosurePermission(
                destination_id=context.destination_id,
                projection_id=context.contract.result_schema.schema_id,
                category=category,
            )
            for category in (DisclosureCategory.PROFILE_VALUES, DisclosureCategory.TAX_VALUES)
        )
    return ResolvedOperationAccess(
        request=OperationAccessRequest(
            profile_id=payload.profile_id,
            definition_id=request.definition_id,
            action=context.action,
            frontend=context.frontend,
            periods=frozenset(),
            period_independent=True,
            destination_id=context.destination_id,
        ),
        policy=OperationAccessPolicy(
            definition_id=request.definition_id,
            definition_contract_digest=context.contract.definition_contract_digest,
            actions=frozenset(
                {
                    AccessAction.SUBMIT,
                    AccessAction.START,
                    AccessAction.RESUME,
                    AccessAction.COMMIT,
                    AccessAction.CANCEL,
                    AccessAction.DETACH,
                    AccessAction.OBSERVE,
                    AccessAction.RESULT,
                }
            ),
            disclosures=disclosures,
            periods=frozenset(),
            allow_period_independent=True,
            backend=Availability.AVAILABLE,
            published_authority=context.published_authority,
            provider=Availability.NOT_REQUIRED,
            transaction_authority_required=False,
            requires_human=True,
        ),
    )
