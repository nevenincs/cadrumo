"""Authenticated discovery of the remaining inputs for a stored Modelo work unit."""

from __future__ import annotations

import asyncio
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.config import override_settings
from ...core.external_constants import OutputLanguage
from ...core.identity.hex_ids import WorkUnitId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
)
from ...core.time.clock import now
from ...domain.modelos.work_unit import WorkUnit
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

        async def capture() -> str:
            projection = await asyncio.to_thread(discover)
            reference = await context.operands.put(projection, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(capture(), task_name="modelo-work-wizard-context")


def build_modelo_work_wizard_context_definition(factory: ActiveWorkLifecyclePortsFactory) -> OperationDefinition:
    """Declare a recorded read with an encrypted profile-bound result."""
    return OperationDefinition(
        definition_id=MODELO_WORK_WIZARD_CONTEXT_OPERATION_DEFINITION_ID,
        request_type=ModeloWorkWizardContextRequest,
        result_type=ModeloWorkWizardContextProjection,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloWorkWizardContextRequest,
            executor_type=ModeloWorkWizardContextExecutor,
            build=lambda: ModeloWorkWizardContextExecutor(factory),
        ),
        phase_codes=(MODELO_WORK_WIZARD_CONTEXT_OPERATION_DEFINITION_ID,),
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


def build_modelo_work_wizard_context_registration(
    definition: OperationDefinition, factory: ActiveWorkLifecyclePortsFactory
) -> OperationPublicDefinitionRegistrationV1:
    """Resolve the stored period before admission and preserve its historical disclosure scope."""

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        payload = request.payload
        if request.definition_id != MODELO_WORK_WIZARD_CONTEXT_OPERATION_DEFINITION_ID or not isinstance(
            payload, ModeloWorkWizardContextRequest
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if payload.profile_id != context.profile_id or request.subject_ref != payload.work_unit_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        admitted = context.admitted_request
        if admitted is not None and context.action in {
            AccessAction.OBSERVE,
            AccessAction.RESULT,
            AccessAction.CANCEL,
            AccessAction.DETACH,
        }:
            if (
                admitted.profile_id != context.profile_id
                or admitted.definition_id != request.definition_id
                or admitted.action is not AccessAction.SUBMIT
                or admitted.period_independent
                or len(admitted.periods) != 1
            ):
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            periods = admitted.periods
        else:
            periods = frozenset({_read_unit(payload, factory).period})
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
                periods=periods,
                period_independent=False,
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
                periods=periods,
                allow_period_independent=False,
                backend=Availability.AVAILABLE,
                published_authority=context.published_authority,
                provider=Availability.NOT_REQUIRED,
                transaction_authority_required=False,
            ),
        )

    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request",
            schema_version=1,
            model_type=ModeloWorkWizardContextRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=ModeloWorkWizardContextProjection,
        ),
        access_resolver=resolve,
    )
