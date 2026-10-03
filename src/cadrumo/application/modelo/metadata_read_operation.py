"""Registered exact-profile work metadata reads through the canonical selector."""

from __future__ import annotations

import asyncio
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from ...core.async_cleanup import await_cancellation_complete
from ...core.filing_year import FilingYear
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, profile_operation_subject
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.ids import RevisionId
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
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.public_period import PublicPeriod
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
from .work_addressing import (
    ModeloWorkAddressNotFoundError,
    ModeloWorkPeriodTokenError,
    ModeloWorkSelectorError,
    resolve_modelo_work_unit_for_operator_target,
)
from .work_lifecycle_ports import ActiveWorkLifecyclePortsFactory

MODELO_WORK_METADATA_OPERATION_DEFINITION_ID = "modelo.work.metadata"


class ModeloWorkMetadataRequest(CredentialFreeOperationRequest):
    """Bounded selectors resolved only within the explicitly admitted profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    work_unit_id: Annotated[str, Field(pattern=r"^(?:[0-9a-f]{12}|[0-9a-f]{64})$")] | None = None
    modelo: Annotated[str, Field(min_length=1, max_length=16)] | None = None
    year: FilingYear | None = None
    period: PublicPeriod | None = None
    revision: RevisionId | None = None


class ModeloWorkMetadataProjection(BaseModel):
    """Private metadata from one canonical catalogue read, never a mutation receipt."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    result_version: Literal[1] = 1
    profile_id: UUID
    unit: ModeloWorkMetadataSnapshot


def _read_unit(
    payload: ModeloWorkMetadataRequest, factory: ActiveWorkLifecyclePortsFactory, *, operation: PinnedAuthorityOperation
) -> WorkUnit:
    ports = factory()
    repository = ports.work_unit_repository
    if repository.bucket_id != str(payload.profile_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    unit = resolve_modelo_work_unit_for_operator_target(
        work_unit_id=payload.work_unit_id,
        modelo=payload.modelo,
        year=payload.year,
        period=payload.period.to_period() if payload.period is not None else None,
        registry_revision_id=payload.revision,
        bucket_id=str(payload.profile_id),
        catalogue=repository.load(),
        resolved_bucket_id=str(payload.profile_id),
        operation=operation,
    )
    if unit.bucket_id != str(payload.profile_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return unit


class ModeloWorkMetadataExecutor:
    """Retain canonical read and encrypted result ownership through cancellation."""

    def __init__(self, factory: ActiveWorkLifecyclePortsFactory) -> None:
        """Bind the execution profile's canonical catalogue capability."""
        self._factory = factory

    async def execute(
        self, request: OperationRequest[ModeloWorkMetadataRequest], context: OperationExecutorContext
    ) -> str:
        """Capture one selected unit and retain its result in encrypted custody."""
        if (
            request.definition_id != MODELO_WORK_METADATA_OPERATION_DEFINITION_ID
            or request.subject_ref != profile_operation_subject(str(request.payload.profile_id))
            or context.identity.subject_ref != request.subject_ref
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(MODELO_WORK_METADATA_OPERATION_DEFINITION_ID)

        async def capture() -> str:
            unit = await asyncio.to_thread(
                _read_unit, request.payload, self._factory, operation=context.authority_operation
            )
            result = ModeloWorkMetadataProjection(
                profile_id=request.payload.profile_id, unit=ModeloWorkMetadataSnapshot.from_work_unit(unit)
            )
            reference = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(capture(), task_name="modelo-metadata-read")


def build_modelo_metadata_definition(factory: ActiveWorkLifecyclePortsFactory) -> OperationDefinition:
    """Declare one read using the existing operation journal and custody owner."""
    return OperationDefinition(
        definition_id=MODELO_WORK_METADATA_OPERATION_DEFINITION_ID,
        request_type=ModeloWorkMetadataRequest,
        result_type=ModeloWorkMetadataProjection,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloWorkMetadataRequest,
            executor_type=ModeloWorkMetadataExecutor,
            build=lambda: ModeloWorkMetadataExecutor(factory),
        ),
        phase_codes=(MODELO_WORK_METADATA_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
    )


def build_modelo_metadata_registration(
    definition: OperationDefinition, factory: ActiveWorkLifecyclePortsFactory
) -> OperationPublicDefinitionRegistrationV1:
    """Bind canonical selection to fresh profile, period and disclosure checks."""

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        payload = request.payload
        if request.definition_id != MODELO_WORK_METADATA_OPERATION_DEFINITION_ID or not isinstance(
            payload, ModeloWorkMetadataRequest
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if payload.profile_id != context.profile_id or request.subject_ref != profile_operation_subject(
            str(payload.profile_id)
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        admitted = context.admitted_request
        if admitted is not None and context.action in ADMISSION_REPLAY_ACTIONS:
            periods = require_single_period_admission(
                admitted, profile_id=context.profile_id, definition_id=request.definition_id
            )
        else:
            if context.authority_operation is None:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            try:
                unit = _read_unit(payload, factory, operation=context.authority_operation)
            except (ModeloWorkSelectorError, ModeloWorkAddressNotFoundError, ModeloWorkPeriodTokenError):
                # Invalid or ambiguous operator selection is a normal refusal.
                # Candidate identities remain private; repository/custody faults
                # still propagate to the worker's fail-closed lifetime boundary.
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED) from None
            periods = frozenset({unit.period})
        return bind_operation_access_profile(
            context,
            LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
            profile_id=context.profile_id,
            definition_id=request.definition_id,
            periods=periods,
        )

    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ModeloWorkMetadataProjection,
        access_resolver=resolve,
    )
