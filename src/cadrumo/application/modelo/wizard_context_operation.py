"""Authenticated discovery of the remaining inputs for a stored Modelo work unit."""

from __future__ import annotations

from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, model_validator

from ...core.config import override_settings
from ...core.external_constants import OutputLanguage
from ...core.identity.hex_ids import WorkUnitId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.modelos.work_unit import WorkUnit
from ..operations.access_resolution import (
    ADMISSION_REPLAY_ACTIONS,
    LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access_profile,
    require_single_period_admission,
)
from ..operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES
from ..operations.models import CredentialFreeOperationRequest, OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_access_request_work_unit_payload
from ..operations.read_capture import capture_read_result
from ..operations.registry import OperationFrontendProjection, OperationPublicDefinitionRegistrationV1
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .metadata_projection import ModeloWorkMetadataSnapshot
from .work_lifecycle import ActiveWorkUnitUse, require_active_work_unit
from .work_lifecycle_ports import ActiveWorkLifecyclePortsFactory
from .work_wizard import ModeloWorkWizardStep, discover_modelo_work_wizard_steps

MODELO_WORK_WIZARD_CONTEXT_OPERATION_DEFINITION_ID = "modelo.work.wizard_context"


class ModeloWorkWizardContextRequest(CredentialFreeOperationRequest):
    """Address an exact profile and full work-unit identity before private discovery."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    work_unit_id: WorkUnitId
    output_language: OutputLanguage


class ModeloWorkWizardContextProjection(BaseModel):
    """One private discovery snapshot for the canonical interactive flow renderer."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result_version: Literal[1] = 1
    profile_id: UUID
    unit: ModeloWorkMetadataSnapshot
    output_language: OutputLanguage
    steps: tuple[ModeloWorkWizardStep, ...]

    @model_validator(mode="after")
    def _bound_result(self) -> Self:
        if self.unit.bucket_id != str(self.profile_id):
            raise ValueError("wizard context belongs to a different profile")
        identities = tuple((step.channel, step.key) for step in self.steps)
        if len(set(identities)) != len(identities):
            raise ValueError("wizard context has duplicate input identities")
        return self


def _read_unit(payload: ModeloWorkWizardContextRequest, factory: ActiveWorkLifecyclePortsFactory) -> WorkUnit:
    repository = factory().work_unit_repository
    if repository.bucket_id != str(payload.profile_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    unit = require_active_work_unit(
        repository.load(),
        work_unit_id=payload.work_unit_id,
        repository_bucket_id=repository.bucket_id,
        use=ActiveWorkUnitUse.CALCULATE,
    )
    if unit.bucket_id != str(payload.profile_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return unit


class ModeloWorkWizardContextExecutor:
    """Read private profile readiness only inside the admitted profile worker."""

    def __init__(self, factory: ActiveWorkLifecyclePortsFactory) -> None:
        """Keep the active profile's lifecycle port factory for one invocation."""
        self._factory = factory

    async def execute(
        self, request: OperationRequest[ModeloWorkWizardContextRequest], context: OperationExecutorContext
    ) -> str:
        """Capture one authenticated, immutable discovery snapshot."""
        payload = request.payload
        if (
            request.definition_id != MODELO_WORK_WIZARD_CONTEXT_OPERATION_DEFINITION_ID
            or request.subject_ref != payload.work_unit_id
            or context.identity.subject_ref != request.subject_ref
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(MODELO_WORK_WIZARD_CONTEXT_OPERATION_DEFINITION_ID)

        def discover() -> ModeloWorkWizardContextProjection:
            unit = _read_unit(payload, self._factory)
            with override_settings(cadrumo_output_language=payload.output_language.value):
                steps = discover_modelo_work_wizard_steps(unit, operation=context.authority_operation)
            return ModeloWorkWizardContextProjection(
                profile_id=payload.profile_id,
                unit=ModeloWorkMetadataSnapshot.from_work_unit(unit),
                output_language=payload.output_language,
                steps=steps,
            )

        return await capture_read_result(context, discover, task_name="modelo-work-wizard-context")


def build_modelo_work_wizard_context_definition(factory: ActiveWorkLifecyclePortsFactory) -> OperationDefinition:
    """Declare a recorded read with an encrypted profile-bound result."""
    return build_single_phase_definition(
        definition_id=MODELO_WORK_WIZARD_CONTEXT_OPERATION_DEFINITION_ID,
        request_type=ModeloWorkWizardContextRequest,
        result_type=ModeloWorkWizardContextProjection,
        executor_type=ModeloWorkWizardContextExecutor,
        build=lambda: ModeloWorkWizardContextExecutor(factory),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
    )


def build_modelo_work_wizard_context_registration(
    definition: OperationDefinition, factory: ActiveWorkLifecyclePortsFactory
) -> OperationPublicDefinitionRegistrationV1:
    """Resolve the stored period before admission and preserve its historical disclosure scope."""

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        payload = require_access_request_work_unit_payload(
            request,
            definition_id=MODELO_WORK_WIZARD_CONTEXT_OPERATION_DEFINITION_ID,
            payload_type=ModeloWorkWizardContextRequest,
            access_profile_id=context.profile_id,
        )
        admitted = context.admitted_request
        if admitted is not None and context.action in ADMISSION_REPLAY_ACTIONS:
            periods = require_single_period_admission(
                admitted, profile_id=context.profile_id, definition_id=request.definition_id
            )
        else:
            periods = frozenset({_read_unit(payload, factory).period})
        return bind_operation_access_profile(
            context,
            LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
            profile_id=context.profile_id,
            definition_id=request.definition_id,
            periods=periods,
        )

    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ModeloWorkWizardContextProjection,
        access_resolver=resolve,
    )
