"""Registered exact-profile mutations for operator-local modelo observations."""

from __future__ import annotations

import asyncio
from decimal import Decimal

from pydantic import BaseModel

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.hashing import canonical_json_bytes
from ...core.operations import OperationEffect
from ...core.period import Period
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..ledger.read_access import resolve_ledger_commit_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_NON_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_access_request_profile_payload, require_operation_profile
from ..operations.registry import OperationFrontendProjection, OperationPublicDefinitionRegistrationV1
from ..runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_errors import ModeloLocalObservationError
from .calculation_action_ports import CalculationActionPortsFactory
from .filing_record_view_operation import ModeloFilingObservationLayersProjection
from .local_observation_actions import (
    LocalObservationPorts,
    ModeloLocalObservationClearResult,
    ModeloLocalObservationResult,
    clear_operator_local_observation,
    record_operator_local_observation,
)
from .local_observation_contracts import (
    MODELO_LOCAL_OBSERVATION_OPERATION_DEFINITION_ID,
    ModeloLocalObservationMutationProjection,
    ModeloLocalObservationMutationReport,
    ModeloLocalObservationMutationRequest,
)
from .local_observation_projection import (
    project_cleared_observation,
    project_modelo_local_observation_result,
    project_recorded_observation,
)


def _local_observation_ports(
    factory: CalculationActionPortsFactory,
    *,
    profile_id: str,
    operation: PinnedAuthorityOperation,
) -> LocalObservationPorts:
    """Build the canonical calculation repository bundle for one exact profile."""
    calculation_ports = factory(bucket_id=profile_id, operation=operation)
    if calculation_ports.work_unit_repository.bucket_id != profile_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return LocalObservationPorts(
        bucket_id=profile_id,
        observation_repository=calculation_ports.observation_repository,
        bucket_event_repository=calculation_ports.bucket_event_repository,
        work_unit_repository=calculation_ports.work_unit_repository,
    )


class ModeloLocalObservationMutationExecutor:
    """Run the existing local observation service in exact-profile worker custody."""

    def __init__(self, factory: CalculationActionPortsFactory) -> None:
        """Retain the canonical profile-bound calculation ports factory."""
        self._factory = factory

    async def execute(
        self,
        request: OperationRequest[ModeloLocalObservationMutationRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Commit one audited override or clear under the supervisor COMMIT fence."""
        payload = request.payload
        profile_id = str(payload.profile_id)
        if request.definition_id != MODELO_LOCAL_OBSERVATION_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)

        period = payload.period.to_period()
        actor = payload.actor or f"profile:{profile_id}"
        ports = _local_observation_ports(
            self._factory,
            profile_id=profile_id,
            operation=context.authority_operation,
        )
        await context.events.phase(MODELO_LOCAL_OBSERVATION_OPERATION_DEFINITION_ID)

        def mutate() -> ModeloLocalObservationResult | ModeloLocalObservationClearResult:
            """Call the existing application action; both actions batch all writes once."""
            if payload.action == "record":
                values = {row.casilla_id: Decimal(row.value) for row in payload.casilla_values}
                return record_operator_local_observation(
                    modelo=payload.modelo,
                    filing_year=period.filing_year,
                    period=period,
                    casilla_values=values,
                    actor=actor,
                    reason=payload.reason,
                    ports=ports,
                    operation=context.authority_operation,
                )
            return clear_operator_local_observation(
                payload.modelo,
                period.filing_year,
                period,
                reason=payload.reason,
                actor=actor,
                ports=ports,
            )

        async def commit_and_publish() -> str:
            async with context.cancellation.irreversible_section():
                if require_active_bucket_id() != profile_id:
                    raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
                await context.events.effect(OperationEffect.UNKNOWN)
                try:
                    result = await asyncio.to_thread(mutate)
                except ModeloLocalObservationError:
                    # This exception is raised by pre-write validation/read paths.
                    await context.events.effect(OperationEffect.NONE)
                    raise

                await context.events.effect(OperationEffect.UPDATED)
                return await self._publish_result(payload, result, actor, ports, context, period)

        return await await_cancellation_complete(commit_and_publish(), task_name="modelo-local-observation-mutation")

    async def _publish_result(
        self,
        payload: ModeloLocalObservationMutationRequest,
        result: ModeloLocalObservationResult | ModeloLocalObservationClearResult,
        actor: str,
        ports: LocalObservationPorts,
        context: OperationExecutorContext,
        period: Period,
    ) -> str:
        """Read persisted layers and publish the exact committed request's result."""
        layers = await asyncio.to_thread(
            ports.observation_repository.load_observation_layers,
            payload.modelo,
            period,
        )
        layer_projection = ModeloFilingObservationLayersProjection.from_layers(layers)
        if payload.action == "record":
            if not isinstance(result, ModeloLocalObservationResult):
                raise ValueError("record action returned a clear result")
            projection = project_recorded_observation(
                profile_id=payload.profile_id,
                result=result,
                layers=layer_projection,
            )
        else:
            if not isinstance(result, ModeloLocalObservationClearResult):
                raise ValueError("clear action returned a record result")
            projection = project_cleared_observation(
                profile_id=payload.profile_id,
                result=result,
                layers=layer_projection,
            )
        if (
            projection.modelo != payload.modelo
            or projection.period != payload.period
            or projection.captured_by != actor
            or projection.reason != payload.reason
            or projection.observation_layers.modelo != payload.modelo
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        report = ModeloLocalObservationMutationReport(
            projection=projection,
            local_write_performed=True,
        )
        if len(canonical_json_bytes(report.model_dump(mode="json"))) > PROJECTION_DOCUMENT_MAX_BYTES:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        return await context.operands.put(report, written_at=now())


def build_modelo_local_observation_definition(factory: CalculationActionPortsFactory) -> OperationDefinition:
    """Declare one durable mutation with encrypted request and result custody."""
    return build_single_phase_definition(
        definition_id=MODELO_LOCAL_OBSERVATION_OPERATION_DEFINITION_ID,
        request_type=ModeloLocalObservationMutationRequest,
        result_type=ModeloLocalObservationMutationReport,
        executor_type=ModeloLocalObservationMutationExecutor,
        build=lambda: ModeloLocalObservationMutationExecutor(factory),
        capabilities=RECORDED_NON_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
    )


def resolve_modelo_local_observation_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    /,
) -> ResolvedOperationAccess:
    """Require exact profile and filing period access, plus fresh COMMIT authority."""
    payload = require_access_request_profile_payload(
        request,
        definition_id=MODELO_LOCAL_OBSERVATION_OPERATION_DEFINITION_ID,
        payload_type=ModeloLocalObservationMutationRequest,
        access_profile_id=context.profile_id,
    )
    return resolve_ledger_commit_access(
        request,
        context,
        profile_id=payload.profile_id,
        periods=frozenset({payload.period.to_period()}),
    )


def build_modelo_local_observation_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the secure request and receipt-projected output schemas."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ModeloLocalObservationMutationProjection,
        result_projector=project_modelo_local_observation_result,
        access_resolver=resolve_modelo_local_observation_access,
    )
