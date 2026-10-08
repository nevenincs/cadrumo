"""Registered exact-profile diagnostics reads over locally recorded runs."""

from __future__ import annotations

from datetime import date
from typing import TypedDict

from pydantic import BaseModel

from ..core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .diagnostics_operation_ports import DiagnosticsReadPortsFactory
from .diagnostics_read_contracts import (
    DiagnosticsReadExecutionResult,
    DiagnosticsReadProjection,
    DiagnosticsReadRequest,
)
from .diagnostics_run_health import (
    build_error_breakdown,
    build_latency_report,
    build_llm_usage_report,
    build_run_health_report,
    list_recent_runs,
)
from .diagnostics_run_report_contracts import (
    DiagnosticsLatencySnapshot,
    DiagnosticsRunHealthSnapshot,
)
from .diagnostics_usage_contracts import (
    DiagnosticsUsageSnapshot,
)
from .operations.access_resolution import (
    RESUMABLE_READ_ACTIONS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access,
    operation_disclosures,
    require_declared_frontend_and_action,
    require_period_independent_replay_or_authority,
)
from .operations.capabilities import RECORDED_IDEMPOTENT_SECURE_STORED_READ_CAPABILITIES, OperationCapabilities
from .operations.models import (
    OperationRequest,
    OperationTerminalReceipt,
    require_terminal_receipt_match,
)
from .operations.operation_definition import OperationDefinition, OperationExecutorFactory
from .operations.owner import OperationExecutorContext
from .operations.profile_guard import require_access_request_profile_payload, require_operation_profile
from .operations.read_capture import capture_read_result
from .operations.registry import (
    ALL_OPERATION_FRONTENDS,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
)
from .user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
)
from .user_profile.access_errors import ProfileAccessRefusedError

DIAGNOSTICS_READ_OPERATION_DEFINITION_ID = "diagnostics.read"


class _ReportFilters(TypedDict):
    """Canonical report keyword types, with no additional filtering policy."""

    since: date | None
    until: date | None
    provider: str | None


class DiagnosticsReadExecutor:
    """Run existing report services inside immutable exact-profile custody."""

    def __init__(self, factory: DiagnosticsReadPortsFactory) -> None:
        """Retain the composition-owned factory until exact worker execution."""
        self._factory = factory

    async def execute(
        self, request: OperationRequest[DiagnosticsReadRequest], context: OperationExecutorContext
    ) -> str:
        """Capture a complete canonical report without any write or remote call."""
        payload = request.payload
        if request.definition_id != DIAGNOSTICS_READ_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase("diagnostics.read.execute")

        def read() -> DiagnosticsReadExecutionResult:
            require_operation_profile(request, context, payload.profile_id)
            operation = context.authority_operation
            ports = self._factory(profile_id=payload.profile_id, operation=operation)
            if ports.profile_id != payload.profile_id or ports.operation is not operation:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            common: _ReportFilters = {"since": payload.since, "until": payload.until, "provider": payload.provider}
            values = payload.model_dump()
            if payload.kind == "run_health":
                report = build_run_health_report(
                    **common,
                    run_record_port=ports.run_record_port,
                    auth_probe_port=ports.auth_probe_port,
                )
                values["run_health"] = DiagnosticsRunHealthSnapshot.from_report(report)
            elif payload.kind == "runs":
                rows = list_recent_runs(**common, limit=payload.limit, run_record_port=ports.run_record_port)
                values["runs"] = tuple(row.model_dump() for row in rows)
            elif payload.kind == "latency":
                values["latency"] = DiagnosticsLatencySnapshot.from_report(
                    build_latency_report(**common, run_record_port=ports.run_record_port)
                )
            elif payload.kind == "errors":
                values["errors"] = build_error_breakdown(**common, run_record_port=ports.run_record_port).model_dump()
            else:
                values["llm_usage"] = DiagnosticsUsageSnapshot.from_report(
                    build_llm_usage_report(**common, run_record_port=ports.run_record_port)
                )
            return DiagnosticsReadExecutionResult(projection=DiagnosticsReadProjection.model_validate(values))

        return await capture_read_result(context, read, task_name="diagnostics-read-settlement")


def _resolve_access(request: OperationRequest[BaseModel], context: OperationAccessContext) -> ResolvedOperationAccess:
    expected = DIAGNOSTICS_READ_OPERATION_DEFINITION_ID
    payload = require_access_request_profile_payload(
        request,
        definition_id=expected,
        payload_type=DiagnosticsReadRequest,
        access_profile_id=context.profile_id,
    )
    actions = RESUMABLE_READ_ACTIONS
    require_declared_frontend_and_action(context, frontends=ALL_OPERATION_FRONTENDS, actions=actions)
    require_period_independent_replay_or_authority(context, profile_id=payload.profile_id, definition_id=expected)
    disclosures = operation_disclosures(
        context,
        observed_by=frozenset({AccessAction.OBSERVE}),
        result_categories=frozenset({DisclosureCategory.PROFILE_VALUES}),
        result_schema_id=expected + ".result",
    )
    return bind_operation_access(
        context,
        profile_id=payload.profile_id,
        definition_id=expected,
        actions=actions,
        disclosures=disclosures,
        periods=frozenset(),
        period_independent=True,
        requires_all_periods=True,
        requires_human=False,
        provider=Availability.NOT_REQUIRED,
    )


def resolve_diagnostics_read_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Authorize exact profile and reviewed disclosure for every supported frontend."""
    return _resolve_access(request, context)


_RECEIPT_CONTRADICTION = "diagnostics result differs from its settled exact-profile receipt"


def project_diagnostics_read_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release one complete typed report only after exact destination authorization."""
    if type(result) is not DiagnosticsReadExecutionResult:
        raise ValueError("invalid diagnostics read result")
    require_terminal_receipt_match(
        receipt,
        definition_id=DIAGNOSTICS_READ_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(result.projection.profile_id)),
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
        message=_RECEIPT_CONTRADICTION,
    )
    return DiagnosticsReadProjection.model_validate_json(result.projection.model_dump_json(), strict=True)


def _capabilities() -> OperationCapabilities:
    return RECORDED_IDEMPOTENT_SECURE_STORED_READ_CAPABILITIES


def build_diagnostics_read_definition(factory: DiagnosticsReadPortsFactory) -> OperationDefinition:
    """Register canonical local report reads without a mutation boundary."""
    return OperationDefinition(
        definition_id=DIAGNOSTICS_READ_OPERATION_DEFINITION_ID,
        request_type=DiagnosticsReadRequest,
        result_type=DiagnosticsReadExecutionResult,
        executor_factory=OperationExecutorFactory(
            request_type=DiagnosticsReadRequest,
            executor_type=DiagnosticsReadExecutor,
            build=lambda: DiagnosticsReadExecutor(factory),
        ),
        phase_codes=("diagnostics.read.execute",),
        interaction_kinds=frozenset(),
        capabilities=_capabilities(),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=ALL_OPERATION_FRONTENDS,
    )


def build_diagnostics_read_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Enroll closed request/report schemas and reviewed destination consent."""
    if definition.definition_id != DIAGNOSTICS_READ_OPERATION_DEFINITION_ID:
        raise ValueError("unexpected diagnostics read definition")
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=DiagnosticsReadProjection,
        result_projector=project_diagnostics_read_result,
        access_resolver=resolve_diagnostics_read_access,
    )
