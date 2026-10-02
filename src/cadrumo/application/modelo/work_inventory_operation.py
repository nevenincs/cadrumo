"""Recorded, exact-profile discovery of canonical Modelo work units."""

from __future__ import annotations

import asyncio
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    profile_operation_subject,
)
from ...core.time.clock import now
from ...domain.modelos.work_unit import WorkUnitState
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ..operations.models import CredentialFreeOperationRequest, OperationRequest
from ..operations.owner import OperationExecutorContext
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    OperationAccessPolicy,
    OperationAccessRequest,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .metadata_projection import ModeloWorkMetadataSnapshot
from .work_lifecycle import list_work_units
from .work_lifecycle_ports import ActiveWorkLifecyclePortsFactory

MODELO_WORK_LIST_OPERATION_DEFINITION_ID = "modelo.work.list"


class ModeloWorkListRequest(CredentialFreeOperationRequest):
    """Select complete work inventory under one immutable profile identity."""

    profile_id: UUID
    include_discarded: bool = False


class ModeloWorkListProjection(BaseModel):
    """One complete encrypted snapshot of canonical work metadata."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result_version: Literal[1] = 1
    profile_id: UUID
    include_discarded: bool
    units: tuple[ModeloWorkMetadataSnapshot, ...]

    @model_validator(mode="after")
    def _exact_rows(self) -> Self:
        if len({row.work_unit_id for row in self.units}) != len(self.units):
            raise ValueError("work inventory repeats an identity")
        if any(row.bucket_id != str(self.profile_id) for row in self.units):
            raise ValueError("work inventory contains another profile")
        if not self.include_discarded and any(row.state is not WorkUnitState.BORRADOR for row in self.units):
            raise ValueError("work inventory contains hidden discarded work")
        return self


class ModeloWorkListExecutor:
    """Capture the lifecycle reader's complete order inside profile custody."""

    def __init__(self, factory: ActiveWorkLifecyclePortsFactory) -> None:
        """Retain the composition-owned exact-profile work repository factory."""
        self._factory = factory

    async def execute(self, request: OperationRequest[ModeloWorkListRequest], context: OperationExecutorContext) -> str:
        """Store one encrypted inventory without writing domain state."""
        from ...core.bucket_pointer import require_active_bucket_id

        payload = request.payload
        profile_id = str(payload.profile_id)
        if (
            request.definition_id != MODELO_WORK_LIST_OPERATION_DEFINITION_ID
            or request.subject_ref != profile_operation_subject(profile_id)
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != request.subject_ref
            or require_active_bucket_id() != profile_id
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(MODELO_WORK_LIST_OPERATION_DEFINITION_ID)

        def read() -> ModeloWorkListProjection:
            ports = self._factory()
            if ports.work_unit_repository.bucket_id != profile_id:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            units = list_work_units(
                bucket_id=profile_id,
                include_discarded=payload.include_discarded,
                ports=ports,
            )
            if any(unit.bucket_id != profile_id for unit in units):
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            return ModeloWorkListProjection(
                profile_id=payload.profile_id,
                include_discarded=payload.include_discarded,
                units=tuple(ModeloWorkMetadataSnapshot.from_work_unit(unit) for unit in units),
            )

        async def capture() -> str:
            projection = await asyncio.to_thread(read)
            reference = await context.operands.put(projection, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(capture(), task_name="modelo-work-list")


def build_modelo_work_list_definition(factory: ActiveWorkLifecyclePortsFactory) -> OperationDefinition:
    """Declare one credential-free request with an encrypted result."""
    return OperationDefinition(
        definition_id=MODELO_WORK_LIST_OPERATION_DEFINITION_ID,
        request_type=ModeloWorkListRequest,
        result_type=ModeloWorkListProjection,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloWorkListRequest,
            executor_type=ModeloWorkListExecutor,
            build=lambda: ModeloWorkListExecutor(factory),
        ),
        phase_codes=(MODELO_WORK_LIST_OPERATION_DEFINITION_ID,),
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


def build_modelo_work_list_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Require unrestricted whole-profile consent for work discovery."""

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        payload = request.payload
        if request.definition_id != definition.definition_id or not isinstance(payload, ModeloWorkListRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if payload.profile_id != context.profile_id or request.subject_ref != profile_operation_subject(
            str(payload.profile_id)
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        admitted = context.admitted_request
        if (
            admitted is not None
            and context.action
            in {
                AccessAction.OBSERVE,
                AccessAction.RESULT,
                AccessAction.CANCEL,
                AccessAction.DETACH,
            }
            and (
                admitted.profile_id != context.profile_id
                or admitted.definition_id != request.definition_id
                or admitted.action is not AccessAction.SUBMIT
                or not admitted.period_independent
                or admitted.periods
            )
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
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
        elif context.action is AccessAction.RESULT:
            schema = context.contract.result_schema
            if schema is None:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            disclosures = frozenset(
                (
                    DisclosurePermission(
                        destination_id=context.destination_id,
                        projection_id=schema.schema_id,
                        category=DisclosureCategory.TAX_VALUES,
                    ),
                )
            )
        return ResolvedOperationAccess(
            request=OperationAccessRequest(
                profile_id=context.profile_id,
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
                        AccessAction.OBSERVE,
                        AccessAction.RESULT,
                        AccessAction.CANCEL,
                        AccessAction.DETACH,
                    }
                ),
                disclosures=disclosures,
                periods=frozenset(),
                allow_period_independent=True,
                requires_all_periods=True,
                backend=Availability.AVAILABLE,
                published_authority=context.published_authority,
                provider=Availability.NOT_REQUIRED,
                transaction_authority_required=False,
            ),
        )

    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=ModeloWorkListRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result", schema_version=1, model_type=ModeloWorkListProjection
        ),
        access_resolver=resolve,
    )
