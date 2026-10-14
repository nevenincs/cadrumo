"""Two synthetic operations, one ephemeral and one recorded, that differ only in durability."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel

from cadrumo.application.operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from cadrumo.application.operations.models import CredentialFreeOperationRequest, OperationRequest
from cadrumo.application.operations.operation_definition import OperationDefinition, OperationExecutorFactory
from cadrumo.application.operations.owner import OperationExecutorContext
from cadrumo.application.operations.registry import (
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationRegistry,
    OperationSchemaBindingV1,
)
from cadrumo.application.operations.subject_reference import OperationSubjectReferenceV1
from cadrumo.core.models import STRICT_FROZEN_CONFIG
from cadrumo.core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
)

EPHEMERAL_DEFINITION_ID = "operation.synthetic.routed-read"
RECORDED_DEFINITION_ID = "operation.synthetic.routed-record"


class SyntheticRequest(CredentialFreeOperationRequest):
    """A request that names nothing private."""


class SyntheticResult(BaseModel):
    """What either operation returns."""

    model_config = STRICT_FROZEN_CONFIG
    definition_id: str


class _Executor:
    async def execute(
        self, request: OperationRequest[SyntheticRequest], context: OperationExecutorContext
    ) -> str | None:
        return await context.operands.put(
            SyntheticResult(definition_id=request.definition_id), written_at=datetime.now(UTC)
        )


def _definition(definition_id: str, *, ephemeral: bool) -> OperationDefinition:
    return OperationDefinition(
        definition_id=definition_id,
        request_type=SyntheticRequest,
        result_type=SyntheticResult,
        executor_factory=OperationExecutorFactory(
            request_type=SyntheticRequest, executor_type=_Executor, build=_Executor
        ),
        phase_codes=("operation.phase.synthetic",),
        interaction_kinds=frozenset(),
        capabilities=OperationCapabilities(
            durability=OperationDurability.EPHEMERAL if ephemeral else OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.NONE,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
            sensitive_input=OperationSensitiveInputPolicy.NONE,
            conflict_scope=OperationConflictScope.NONE if ephemeral else OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE})
            if ephemeral
            else frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        subject_reference=OperationSubjectReferenceV1.profile(),
    )


def synthetic_routed_registry() -> OperationRegistry:
    definitions = (
        _definition(EPHEMERAL_DEFINITION_ID, ephemeral=True),
        _definition(RECORDED_DEFINITION_ID, ephemeral=False),
    )
    registrations = tuple(
        OperationPublicDefinitionRegistrationV1.compose(
            definition=definition,
            request_schema=OperationSchemaBindingV1.bind(
                schema_id=f"{definition.definition_id}.request", schema_version=1, model_type=SyntheticRequest
            ),
            result_schema=OperationSchemaBindingV1.bind(
                schema_id=f"{definition.definition_id}.result", schema_version=1, model_type=SyntheticResult
            ),
        )
        for definition in definitions
    )
    return OperationRegistry(definitions=definitions, public_registrations=registrations)
