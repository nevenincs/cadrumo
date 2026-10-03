"""Authenticated, recorded Modelo wizard calculation attempts."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING, Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, TypeAdapter, ValidationError, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.config import override_settings
from ...core.external_constants import OutputLanguage
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect
from ...core.time.clock import now
from ...domain.calculations.registry.ids import BindingId
from ..operations.access_resolution import (
    ADMISSION_REPLAY_ACTIONS,
    COMMITTING_LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access_profile,
    require_single_period_admission,
)
from ..operations.capabilities import RECORDED_COOPERATIVE_IDEMPOTENT_REQUEST_BOUND_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
)
from ..user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .calculation_action_ports import CalculationActionPortsFactory
from .metadata_projection import ModeloWorkMetadataSnapshot
from .operation_definitions import (
    ModeloWorkCalculatePublicResultV2,
    ModeloWorkCalculateRequest,
    calculate_prepared_modelo_work,
    calculation_public_result,
    prepare_modelo_work_calculation,
)
from .work_lifecycle import ActiveWorkUnitUse, require_active_work_unit
from .work_lifecycle_ports import ActiveWorkLifecyclePortsFactory
from .work_missing_input import ModeloWorkMissingInputError
from .work_wizard import ModeloWorkWizardStep, modelo_work_wizard_follow_up_step

if TYPE_CHECKING:
    from ...domain.attachments.protocols import AttachmentStoreProtocol

MODELO_WORK_WIZARD_ATTEMPT_OPERATION_DEFINITION_ID = "modelo.work.wizard_attempt"
_BINDING_ID_ADAPTER: TypeAdapter[str] = TypeAdapter(BindingId)


class ModeloWorkWizardAttemptRequest(BaseModel):
    """Bind one exact profile and language to the canonical calculate request."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    output_language: OutputLanguage
    calculation: ModeloWorkCalculateRequest


class ModeloWorkWizardAttemptCalculated(BaseModel):
    """A completed attempt carrying the existing calculation publication."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["calculated"] = "calculated"
    result: ModeloWorkCalculatePublicResultV2


class ModeloWorkWizardAttemptNeedsInput(BaseModel):
    """A pre-publication missing input with canonical unit and grounded step."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["needs_input"] = "needs_input"
    unit: ModeloWorkMetadataSnapshot
    step: ModeloWorkWizardStep

    @model_validator(mode="after")
    def _grounded_binding(self) -> Self:
        if self.step.channel != "binding" or not self.step.legal_refs or not self.step.source_refs:
            raise ValueError("wizard attempt needs one grounded binding step")
        try:
            _BINDING_ID_ADAPTER.validate_python(self.step.key, strict=True)
        except ValidationError as exc:
            raise ValueError("wizard attempt needs a canonical binding id") from exc
        return self


class ModeloWorkWizardAttemptProjection(BaseModel):
    """Exactly one calculated or needs-input result for one profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result_version: Literal[1] = 1
    profile_id: UUID
    output_language: OutputLanguage
    outcome: Annotated[
        ModeloWorkWizardAttemptCalculated | ModeloWorkWizardAttemptNeedsInput,
        Field(discriminator="kind"),
    ]

    @model_validator(mode="after")
    def _bound_profile(self) -> Self:
        unit = (
            self.outcome.result.unit
            if isinstance(self.outcome, ModeloWorkWizardAttemptCalculated)
            else self.outcome.unit
        )
        if unit.bucket_id != str(self.profile_id):
            raise ValueError("wizard attempt result belongs to a different profile")
        return self


class ModeloWorkWizardAttemptExecutor:
    """Try the canonical calculation and return one safe wizard result."""

    def __init__(
        self,
        *,
        calculation_action_ports_factory: CalculationActionPortsFactory,
        attachment_store_factory: Callable[[str], AttachmentStoreProtocol],
    ) -> None:
        """Retain the same composition-owned factories as ordinary calculation."""
        self._calculation_action_ports_factory = calculation_action_ports_factory
        self._attachment_store_factory = attachment_store_factory

    async def execute(
        self,
        request: OperationRequest[ModeloWorkWizardAttemptRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Classify only the engine's typed pre-publication refusal as needs-input."""
        payload = request.payload
        work_unit_id = payload.calculation.work_unit_id
        if request.definition_id != MODELO_WORK_WIZARD_ATTEMPT_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id, expected_subject_ref=work_unit_id)
        await context.events.phase(MODELO_WORK_WIZARD_ATTEMPT_OPERATION_DEFINITION_ID)
        prepared = await prepare_modelo_work_calculation(
            payload.calculation,
            operation=context.authority_operation,
            calculation_action_ports_factory=self._calculation_action_ports_factory,
            attachment_store_factory=self._attachment_store_factory,
        )
        if prepared.work_unit.bucket_id != str(payload.profile_id):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)

        async def publish() -> str:
            async with context.cancellation.irreversible_section():
                # Preparation inside the service may already write migrations or
                # IVA decisions before its engine refuses a missing binding.
                await context.events.effect(OperationEffect.UNKNOWN)
                try:
                    result = await asyncio.to_thread(
                        calculate_prepared_modelo_work,
                        prepared,
                        actor=payload.calculation.actor,
                    )
                except ModeloWorkMissingInputError as error:
                    missing_error = error

                    def follow_up() -> tuple[ModeloWorkMetadataSnapshot, ModeloWorkWizardStep | None]:
                        current_unit = require_active_work_unit(
                            prepared.ports.work_unit_repository.load(),
                            work_unit_id=work_unit_id,
                            repository_bucket_id=prepared.ports.work_unit_repository.bucket_id,
                            use=ActiveWorkUnitUse.CALCULATE,
                        )
                        with override_settings(cadrumo_output_language=payload.output_language.value):
                            step = modelo_work_wizard_follow_up_step(
                                missing_error,
                                unit=current_unit,
                                operation=context.authority_operation,
                            )
                        return ModeloWorkMetadataSnapshot.from_work_unit(current_unit), step

                    unit, step = await asyncio.to_thread(follow_up)
                    if (
                        step is None
                        or step.channel != "binding"
                        or step.key != error.binding_id
                        or not (step.legal_refs and step.source_refs)
                    ):
                        raise
                    projection = ModeloWorkWizardAttemptProjection(
                        profile_id=payload.profile_id,
                        output_language=payload.output_language,
                        outcome=ModeloWorkWizardAttemptNeedsInput(unit=unit, step=step),
                    )
                else:
                    if result.revision_published:
                        await context.events.effect(OperationEffect.UPDATED)
                    public_result = await asyncio.to_thread(
                        calculation_public_result,
                        result,
                        operation=context.authority_operation,
                    )
                    projection = ModeloWorkWizardAttemptProjection(
                        profile_id=payload.profile_id,
                        output_language=payload.output_language,
                        outcome=ModeloWorkWizardAttemptCalculated(result=public_result),
                    )
                return await context.operands.put(projection, written_at=now())

        return await await_cancellation_complete(publish(), task_name="modelo-work-wizard-attempt")


def build_modelo_work_wizard_attempt_definition(
    *,
    calculation_action_ports_factory: CalculationActionPortsFactory,
    attachment_store_factory: Callable[[str], AttachmentStoreProtocol],
) -> OperationDefinition:
    """Record one secure calculation attempt with a typed interactive result."""
    return OperationDefinition(
        definition_id=MODELO_WORK_WIZARD_ATTEMPT_OPERATION_DEFINITION_ID,
        request_type=ModeloWorkWizardAttemptRequest,
        result_type=ModeloWorkWizardAttemptProjection,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloWorkWizardAttemptRequest,
            executor_type=ModeloWorkWizardAttemptExecutor,
            build=lambda: ModeloWorkWizardAttemptExecutor(
                calculation_action_ports_factory=calculation_action_ports_factory,
                attachment_store_factory=attachment_store_factory,
            ),
        ),
        phase_codes=(MODELO_WORK_WIZARD_ATTEMPT_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=RECORDED_COOPERATIVE_IDEMPOTENT_REQUEST_BOUND_SECURE_INPUT_UPDATE_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
    )


def build_modelo_work_wizard_attempt_registration(
    definition: OperationDefinition,
    factory: ActiveWorkLifecyclePortsFactory,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind exact work-period access and encrypted result disclosure."""

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        payload = request.payload
        if request.definition_id != MODELO_WORK_WIZARD_ATTEMPT_OPERATION_DEFINITION_ID or not isinstance(
            payload, ModeloWorkWizardAttemptRequest
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if payload.profile_id != context.profile_id or request.subject_ref != payload.calculation.work_unit_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        admitted = context.admitted_request
        if admitted is not None and context.action in ADMISSION_REPLAY_ACTIONS | {AccessAction.COMMIT}:
            periods = require_single_period_admission(
                admitted, profile_id=context.profile_id, definition_id=request.definition_id
            )
        else:
            repository = factory().work_unit_repository
            if repository.bucket_id != str(payload.profile_id):
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            unit = require_active_work_unit(
                repository.load(),
                work_unit_id=payload.calculation.work_unit_id,
                repository_bucket_id=repository.bucket_id,
                use=ActiveWorkUnitUse.CALCULATE,
            )
            if unit.bucket_id != str(payload.profile_id):
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            periods = frozenset({unit.period})
        return bind_operation_access_profile(
            context,
            COMMITTING_LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
            profile_id=context.profile_id,
            definition_id=request.definition_id,
            periods=periods,
        )

    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ModeloWorkWizardAttemptProjection,
        access_resolver=resolve,
    )
