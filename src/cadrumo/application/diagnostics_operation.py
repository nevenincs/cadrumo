"""Registered exact-profile diagnostics and consent-gated telemetry dispatch.

Canonical services own aggregation, payload construction, consent and transport.
Remote dispatch runs outside COMMIT custody and completes before cancellation
settlement. A best-effort sink invocation proves no delivery: its effect stays
UNKNOWN, and the existing sent flag means attempted handoff.
"""

from __future__ import annotations

import asyncio
from datetime import date
from typing import TypedDict

from pydantic import BaseModel

from ..core.async_cleanup import await_cancellation_complete
from ..core.config import Settings
from ..core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ..core.telemetry.consent import telemetry_emit_permitted
from ..core.telemetry.emit import TelemetrySink
from ..core.telemetry.schema import TelemetryEventPayload
from ..core.time.clock import now
from .diagnostics_operation_ports import (
    DiagnosticsReadPortsFactory,
    DiagnosticsTelemetryFlushPorts,
    DiagnosticsTelemetryFlushPortsFactory,
)
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
from .diagnostics_telemetry import build_telemetry_flush_preview, flush_telemetry
from .diagnostics_telemetry_contracts import (
    DiagnosticsTelemetryFlushExecutionResult,
    DiagnosticsTelemetryFlushProjection,
    DiagnosticsTelemetryFlushRequest,
    DiagnosticsTelemetryPreviewSnapshot,
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
    OperationFrontendProjection,
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
DIAGNOSTICS_TELEMETRY_FLUSH_OPERATION_DEFINITION_ID = "diagnostics.telemetry.flush"
_FLUSH_FRONTENDS = frozenset({OperationFrontendProjection.CLI})


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
                    run_telemetry_port=ports.run_telemetry_port,
                    auth_probe_port=ports.auth_probe_port,
                )
                values["run_health"] = DiagnosticsRunHealthSnapshot.from_report(report)
            elif payload.kind == "runs":
                rows = list_recent_runs(**common, limit=payload.limit, run_telemetry_port=ports.run_telemetry_port)
                values["runs"] = tuple(row.model_dump() for row in rows)
            elif payload.kind == "latency":
                values["latency"] = DiagnosticsLatencySnapshot.from_report(
                    build_latency_report(**common, run_telemetry_port=ports.run_telemetry_port)
                )
            elif payload.kind == "errors":
                values["errors"] = build_error_breakdown(
                    **common, run_telemetry_port=ports.run_telemetry_port
                ).model_dump()
            else:
                values["llm_usage"] = DiagnosticsUsageSnapshot.from_report(
                    build_llm_usage_report(**common, run_telemetry_port=ports.run_telemetry_port)
                )
            return DiagnosticsReadExecutionResult(projection=DiagnosticsReadProjection.model_validate(values))

        return await capture_read_result(context, read, task_name="diagnostics-read-settlement")


def _flush_settings(ports: DiagnosticsTelemetryFlushPorts, payload: DiagnosticsTelemetryFlushRequest) -> Settings:
    settings = ports.settings_factory()
    overrides: dict[str, object] = {}
    for name, value in (
        ("cadrumo_telemetry_opt_in", payload.opt_in),
        ("cadrumo_telemetry_tier", payload.tier),
        ("cadrumo_telemetry_endpoint", payload.endpoint),
    ):
        if value is not None:
            overrides[name] = value
    return Settings.model_validate({**settings.model_dump(), **overrides})


class _DispatchTracker:
    """Own one invocation's sink attempt; no transport/delivery inference."""

    def __init__(self) -> None:
        self.attempted = False
        self.intent_recorded = False

    def track(self, sink: TelemetrySink) -> TelemetrySink:
        tracker = self

        class TrackedSink:
            """Delegate the one admitted sink invocation without changing its payload."""

            def send(self, payload: TelemetryEventPayload) -> None:
                """Record the possible external effect before entering the actual sink."""
                tracker.attempted = True
                sink.send(payload)

        return TrackedSink()


class DiagnosticsTelemetryFlushExecutor:
    """Settle existing consent-gated dispatch without holding COMMIT over HTTP."""

    def __init__(self, factory: DiagnosticsTelemetryFlushPortsFactory) -> None:
        """Retain only composition-owned worker capability construction."""
        self._factory = factory

    async def execute(
        self, request: OperationRequest[DiagnosticsTelemetryFlushRequest], context: OperationExecutorContext
    ) -> str:
        """Build once, authorize at dispatch, join the thread and retain its result."""
        payload = request.payload
        if request.definition_id != DIAGNOSTICS_TELEMETRY_FLUSH_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase("diagnostics.telemetry.flush.prepare")
        operation = context.authority_operation
        ports = self._factory(profile_id=payload.profile_id, operation=operation)
        if ports.profile_id != payload.profile_id or ports.operation is not operation:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        tracker = _DispatchTracker()
        loop = asyncio.get_running_loop()

        async def authorize_dispatch() -> Settings:
            async with context.cancellation.irreversible_section():
                require_operation_profile(request, context, payload.profile_id)
                current = _flush_settings(ports, payload)
                if (
                    telemetry_emit_permitted(current, acknowledged=payload.acknowledged)
                    and current.cadrumo_telemetry_endpoint
                ):
                    tracker.intent_recorded = True
                    await context.events.effect(OperationEffect.UNKNOWN)
                    await context.events.phase("diagnostics.telemetry.flush.dispatch")
                return current

        def before_dispatch() -> Settings:
            # Only the owned worker thread blocks here. The worker loop remains
            # free to execute the short authorization coroutine, then releases
            # COMMIT before the canonical service invokes the remote sink.
            return asyncio.run_coroutine_threadsafe(authorize_dispatch(), loop).result()

        def flush() -> DiagnosticsTelemetryFlushExecutionResult:
            require_operation_profile(request, context, payload.profile_id)
            settings = _flush_settings(ports, payload)
            if payload.dry_run:
                preview = build_telemetry_flush_preview(
                    settings=settings,
                    acknowledged=payload.acknowledged,
                    run_telemetry_port=ports.run_telemetry_port,
                    auth_probe_port=ports.auth_probe_port,
                )
            else:
                preview = flush_telemetry(
                    settings=settings,
                    acknowledged=payload.acknowledged,
                    run_telemetry_port=ports.run_telemetry_port,
                    auth_probe_port=ports.auth_probe_port,
                    before_dispatch=before_dispatch,
                    sink_factory=lambda current: tracker.track(ports.sink_factory(current)),
                )
            return DiagnosticsTelemetryFlushExecutionResult(
                projection=DiagnosticsTelemetryFlushProjection(
                    profile_id=payload.profile_id,
                    dry_run=payload.dry_run,
                    preview=DiagnosticsTelemetryPreviewSnapshot.model_validate(preview.model_dump()),
                    sent=tracker.attempted,
                )
            )

        async def settle() -> str:
            try:
                result = await asyncio.to_thread(flush)
            except BaseException:
                if not tracker.attempted and tracker.intent_recorded:
                    await context.events.effect(OperationEffect.NONE)
                raise
            effect = OperationEffect.UNKNOWN if tracker.attempted else OperationEffect.NONE
            await context.events.effect(effect)
            await context.events.phase("diagnostics.telemetry.flush.settlement")
            return await context.operands.put(result, written_at=now())

        return await await_cancellation_complete(settle(), task_name="diagnostics-telemetry-settlement")


def _resolve_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, *, flush: bool
) -> ResolvedOperationAccess:
    expected = (
        DIAGNOSTICS_TELEMETRY_FLUSH_OPERATION_DEFINITION_ID if flush else DIAGNOSTICS_READ_OPERATION_DEFINITION_ID
    )
    payload = require_access_request_profile_payload(
        request,
        definition_id=expected,
        payload_type=DiagnosticsTelemetryFlushRequest if flush else DiagnosticsReadRequest,
        access_profile_id=context.profile_id,
    )
    frontends = _FLUSH_FRONTENDS if flush else ALL_OPERATION_FRONTENDS
    actions = _diagnostics_access_actions(payload)
    require_declared_frontend_and_action(context, frontends=frontends, actions=actions)
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


def _diagnostics_access_actions(
    payload: DiagnosticsReadRequest | DiagnosticsTelemetryFlushRequest,
) -> frozenset[AccessAction]:
    actions = RESUMABLE_READ_ACTIONS
    if isinstance(payload, DiagnosticsTelemetryFlushRequest) and not payload.dry_run:
        actions = actions | frozenset({AccessAction.COMMIT})
    return actions


def resolve_diagnostics_read_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Authorize exact profile and reviewed disclosure for every supported frontend."""
    return _resolve_access(request, context, flush=False)


def resolve_diagnostics_telemetry_flush_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Authorize invocation consent and the real-send COMMIT boundary separately."""
    return _resolve_access(request, context, flush=True)


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


def project_diagnostics_telemetry_flush_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Preserve full preview and the truthful NONE/UNKNOWN external effect."""
    if type(result) is not DiagnosticsTelemetryFlushExecutionResult:
        raise ValueError("invalid diagnostics telemetry result")
    projection = DiagnosticsTelemetryFlushProjection.model_validate_json(
        result.projection.model_dump_json(), strict=True
    )
    require_terminal_receipt_match(
        receipt,
        definition_id=DIAGNOSTICS_TELEMETRY_FLUSH_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(projection.profile_id)),
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.UNKNOWN if projection.sent else OperationEffect.NONE,
        message=_RECEIPT_CONTRADICTION,
    )
    return projection


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


def build_diagnostics_telemetry_flush_definition(factory: DiagnosticsTelemetryFlushPortsFactory) -> OperationDefinition:
    """Register full dry/no-op preview and the existing consent-gated effect."""
    return OperationDefinition(
        definition_id=DIAGNOSTICS_TELEMETRY_FLUSH_OPERATION_DEFINITION_ID,
        request_type=DiagnosticsTelemetryFlushRequest,
        result_type=DiagnosticsTelemetryFlushExecutionResult,
        executor_factory=OperationExecutorFactory(
            request_type=DiagnosticsTelemetryFlushRequest,
            executor_type=DiagnosticsTelemetryFlushExecutor,
            build=lambda: DiagnosticsTelemetryFlushExecutor(factory),
        ),
        phase_codes=(
            "diagnostics.telemetry.flush.prepare",
            "diagnostics.telemetry.flush.dispatch",
            "diagnostics.telemetry.flush.settlement",
        ),
        interaction_kinds=frozenset(),
        capabilities=_capabilities(),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=_FLUSH_FRONTENDS,
    )


def build_diagnostics_telemetry_flush_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Enroll complete telemetry preview and exact-profile effect authority."""
    if definition.definition_id != DIAGNOSTICS_TELEMETRY_FLUSH_OPERATION_DEFINITION_ID:
        raise ValueError("unexpected diagnostics telemetry definition")
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=DiagnosticsTelemetryFlushProjection,
        result_projector=project_diagnostics_telemetry_flush_result,
        access_resolver=resolve_diagnostics_telemetry_flush_access,
    )
