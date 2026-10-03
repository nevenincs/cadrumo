"""Recorded, exact-profile discovery of canonical Modelo work units."""

from __future__ import annotations

from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, model_validator

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import profile_operation_subject
from ...domain.modelos.work_unit import WorkUnitState
from ..operations.access_resolution import (
    ADMISSION_REPLAY_ACTIONS,
    LIFECYCLE_WHOLE_PROFILE_REGISTERED_RESULT_TAX_VALUES_ACCESS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access_profile,
    require_period_independent_admission,
)
from ..operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES
from ..operations.models import CredentialFreeOperationRequest, OperationRequest
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.read_capture import capture_read_result
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
)
from ..user_profile.access_contracts import (
    AccessDenialCode,
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
        payload = request.payload
        profile_id = str(payload.profile_id)
        if request.definition_id != MODELO_WORK_LIST_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
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

        return await capture_read_result(context, read, task_name="modelo-work-list")


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
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
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
        if admitted is not None and context.action in ADMISSION_REPLAY_ACTIONS:
            require_period_independent_admission(
                admitted, profile_id=context.profile_id, definition_id=request.definition_id
            )
        return bind_operation_access_profile(
            context,
            LIFECYCLE_WHOLE_PROFILE_REGISTERED_RESULT_TAX_VALUES_ACCESS,
            profile_id=context.profile_id,
            definition_id=request.definition_id,
            periods=frozenset(),
        )

    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ModeloWorkListProjection,
        access_resolver=resolve,
    )
