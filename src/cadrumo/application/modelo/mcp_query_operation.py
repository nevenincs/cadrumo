"""Agent-specific, typed modelo binding and readiness projections.

The canonical readers remain in query_read_operation. This module validates
caller values against the same pinned declaration and publishes only closed
result fields whose disclosure was authorized for the MCP destination.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal

from pydantic import BaseModel, TypeAdapter

from ...core.async_cleanup import await_cancellation_complete
from ...core.operations import OperationEffect
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.schema_scalars import CalendarDate, DecimalValue
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.registry import OperationFrontendProjection, OperationPublicDefinitionRegistrationV1
from ..operator_actions.preconditions import PROFILE_SETUP_DECLARED_COMPLETE_CONDITION
from ..operator_actions.projection import PreconditionVerdictSnapshot
from ..state_projection import ModeloProfileRefusalCause, ProjectionModeloReadiness
from ..user_profile.access_contracts import AccessDenialCode, DisclosureCategory
from ..user_profile.access_errors import ProfileAccessRefusedError
from .mcp_binding_validation import resolve_typed_bindings
from .mcp_query_contracts import (
    MODELO_BINDINGS_RESOLVE_TYPED_OPERATION_DEFINITION_ID,
    MODELO_READINESS_SUMMARY_OPERATION_DEFINITION_ID,
    ModeloBindingsResolveTypedProjection,
    ModeloReadinessSafeLedgerIssue,
    ModeloReadinessSafeMissingRequirement,
    ModeloReadinessSafeRecovery,
    ModeloReadinessSummaryProjection,
)
from .query_read_contracts import (
    ModeloBindingsResolveRequest,
    ModeloQueryReadPortsFactory,
    ModeloReadinessOperationRequest,
    ModeloReadinessProjection,
)
from .query_read_operation import (
    modelo_query_read_capabilities,
    read_modelo_readiness,
    require_modelo_query_worker_identity,
    resolve_modelo_query_read_access,
)

_DECIMAL = TypeAdapter[Decimal](DecimalValue)
_CALENDAR_DATE = TypeAdapter[str](CalendarDate)


def _readiness_summary(
    payload: ModeloReadinessOperationRequest,
    factory: ModeloQueryReadPortsFactory,
    operation: PinnedAuthorityOperation,
) -> ModeloReadinessSummaryProjection:
    # The canonical reader constructs all axes once. Its human prose stays in
    # worker memory and never enters the agent result operand.
    source = read_modelo_readiness(payload, factory, operation=operation)
    _require_readiness_refusal_causes(source)
    report = ModeloReadinessProjection.from_report(
        payload.profile_id,
        source,
        language=payload.language,
        authority_generation=operation.generation.logical_generation,
    )
    verdict = report.profile_precondition_verdict
    _require_safe_setup_recovery(source, verdict)
    return ModeloReadinessSummaryProjection(
        authority_generation=report.authority_generation,
        profile_id=report.profile_id,
        language=report.language,
        modelo=report.modelo,
        revision_id=report.revision_id,
        filing_year=report.filing_year,
        period=report.period,
        ready=report.ready,
        profile_ready=report.profile_ready,
        per_operation_requirements_assessed=report.per_operation_requirements_assessed,
        profile_refusal_cause=source.profile_refusal_cause,
        profile_recovery=_safe_setup_recovery(verdict),
        registry_ready=report.registry_ready,
        registry_refusal_cause=source.registry_refusal_cause,
        binding_ready=report.binding_ready,
        missing=_safe_missing_requirements(source),
        missing_bindings=report.missing_bindings,
        ledger_preflight_required=report.ledger_preflight_required,
        ledger_ready=report.ledger_ready,
        ledger_period=report.ledger_period,
        ledger_checked_transaction_count=report.ledger_checked_transaction_count,
        ledger_issues=_safe_ledger_issues(source),
    )


def _require_readiness_refusal_causes(source: ProjectionModeloReadiness) -> None:
    if (source.profile_refusal and source.profile_refusal_cause is None) or (
        source.registry_refusal and source.registry_refusal_cause is None
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)


def _require_safe_setup_recovery(
    source: ProjectionModeloReadiness,
    verdict: PreconditionVerdictSnapshot | None,
) -> None:
    if verdict is None:
        return
    if source.profile_refusal_cause is not ModeloProfileRefusalCause.SETUP_INCOMPLETE:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if (
        verdict.failed_condition_id != PROFILE_SETUP_DECLARED_COMPLETE_CONDITION
        or verdict.action_id != "operator.profile.complete_setup"
        or verdict.missing_argument_names
        or verdict.argument_bindings
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)


def _safe_setup_recovery(verdict: PreconditionVerdictSnapshot | None) -> ModeloReadinessSafeRecovery | None:
    if verdict is None:
        return None
    return ModeloReadinessSafeRecovery(
        failed_condition_id="profile.setup.declared_complete",
        action_id="operator.profile.complete_setup",
        missing_argument_names=(),
    )


def _safe_missing_requirements(source: ProjectionModeloReadiness) -> tuple[ModeloReadinessSafeMissingRequirement, ...]:
    return tuple(
        ModeloReadinessSafeMissingRequirement(
            section_key=row.section_key,
            field_key=row.field_key,
            legal_refs=row.legal_refs,
            modelos=row.modelos,
        )
        for row in source.missing
    )


def _safe_ledger_issues(source: ProjectionModeloReadiness) -> tuple[ModeloReadinessSafeLedgerIssue, ...]:
    return tuple(
        ModeloReadinessSafeLedgerIssue(transaction_id=row.transaction_id, reason=row.reason)
        for row in source.ledger_issues
    )


class ModeloBindingsResolveTypedExecutor:
    """Capture validated exact override values through the retained pin."""

    async def execute(
        self, request: OperationRequest[ModeloBindingsResolveRequest], context: OperationExecutorContext
    ) -> str:
        """Capture the validated preview inside the admitted worker."""
        require_modelo_query_worker_identity(
            MODELO_BINDINGS_RESOLVE_TYPED_OPERATION_DEFINITION_ID, request.payload.profile_id, request, context
        )
        await context.events.phase(MODELO_BINDINGS_RESOLVE_TYPED_OPERATION_DEFINITION_ID)

        async def capture() -> str:
            result = await asyncio.to_thread(resolve_typed_bindings, request.payload, context.authority_operation)
            ref = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return ref

        return await await_cancellation_complete(capture(), task_name="modelo-bindings-resolve-typed")


class ModeloReadinessSummaryExecutor:
    """Capture safe readiness causes without diagnostic strings."""

    def __init__(self, factory: ModeloQueryReadPortsFactory) -> None:
        """Retain the exact-profile readiness read-port factory."""
        self._factory = factory

    async def execute(
        self, request: OperationRequest[ModeloReadinessOperationRequest], context: OperationExecutorContext
    ) -> str:
        """Capture all canonical readiness axes with safe typed causes."""
        require_modelo_query_worker_identity(
            MODELO_READINESS_SUMMARY_OPERATION_DEFINITION_ID, request.payload.profile_id, request, context
        )
        await context.events.phase(MODELO_READINESS_SUMMARY_OPERATION_DEFINITION_ID)

        async def capture() -> str:
            result = await asyncio.to_thread(
                _readiness_summary, request.payload, self._factory, context.authority_operation
            )
            ref = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return ref

        return await await_cancellation_complete(capture(), task_name="modelo-readiness-summary")


def build_modelo_bindings_resolve_typed_definition() -> OperationDefinition:
    """Define the agent-only validated binding preview."""
    return build_single_phase_definition(
        definition_id=MODELO_BINDINGS_RESOLVE_TYPED_OPERATION_DEFINITION_ID,
        request_type=ModeloBindingsResolveRequest,
        result_type=ModeloBindingsResolveTypedProjection,
        executor_type=ModeloBindingsResolveTypedExecutor,
        build=ModeloBindingsResolveTypedExecutor,
        capabilities=modelo_query_read_capabilities(sensitive=True),
        permitted_frontends=frozenset({OperationFrontendProjection.MCP}),
    )


def build_modelo_readiness_summary_definition(factory: ModeloQueryReadPortsFactory) -> OperationDefinition:
    """Define the agent-only readiness summary."""
    return build_single_phase_definition(
        definition_id=MODELO_READINESS_SUMMARY_OPERATION_DEFINITION_ID,
        request_type=ModeloReadinessOperationRequest,
        result_type=ModeloReadinessSummaryProjection,
        executor_type=ModeloReadinessSummaryExecutor,
        build=lambda: ModeloReadinessSummaryExecutor(factory),
        capabilities=modelo_query_read_capabilities(),
        permitted_frontends=frozenset({OperationFrontendProjection.MCP}),
    )


def _registration(
    definition: OperationDefinition, request_type: type[BaseModel], result_type: type[BaseModel]
) -> OperationPublicDefinitionRegistrationV1:
    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        if context.frontend is not OperationFrontendProjection.MCP:
            raise ProfileAccessRefusedError(AccessDenialCode.FRONTEND_DENIED)
        return resolve_modelo_query_read_access(
            request,
            context,
            definition_id=definition.definition_id,
            payload_type=request_type,
            result_category=DisclosureCategory.TAX_VALUES,
        )

    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=result_type,
        access_resolver=resolve,
    )


def build_modelo_bindings_resolve_typed_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Register the closed typed preview and its exact result grant."""
    return _registration(definition, ModeloBindingsResolveRequest, ModeloBindingsResolveTypedProjection)


def build_modelo_readiness_summary_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Register the closed readiness summary and its all-period rule."""
    return _registration(definition, ModeloReadinessOperationRequest, ModeloReadinessSummaryProjection)
