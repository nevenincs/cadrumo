"""Registered exact-profile diagnostics and consent-gated telemetry dispatch.

Canonical services own aggregation, payload construction, consent and transport.
Remote dispatch runs outside COMMIT custody and completes before cancellation
settlement. A best-effort sink invocation proves no delivery: its effect stays
UNKNOWN, and the existing sent flag means attempted handoff.
"""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal, Self, TypedDict, cast
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ..core.async_cleanup import await_cancellation_complete
from ..core.config import Settings
from ..core.errors.hierarchy import pydantic_validation_boundary
from ..core.identity.digest import ContentDigest
from ..core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ..core.telemetry.consent import telemetry_emit_permitted
from ..core.telemetry.emit import TelemetrySink
from ..core.telemetry.schema import TelemetryEventPayload
from ..core.telemetry.tier import TelemetryTier
from ..core.time.clock import now
from ..core.time.date_range import validate_inclusive_date_range
from .diagnostics_operation_ports import (
    DiagnosticsReadPortsFactory,
    DiagnosticsTelemetryFlushPorts,
    DiagnosticsTelemetryFlushPortsFactory,
)
from .diagnostics_run_health import (
    ErrorKindCount,
    ErrorsBreakdownReport,
    LatencyPercentiles,
    LatencyReport,
    LlmRunHealthProviderMetrics,
    LlmRunProviderMetrics,
    LlmUsageModelMetrics,
    LlmUsageReport,
    RunHealthReport,
    RunRecordView,
    build_error_breakdown,
    build_latency_report,
    build_llm_usage_report,
    build_run_health_report,
    list_recent_runs,
)
from .diagnostics_telemetry import TelemetryFlushPreview, build_telemetry_flush_preview, flush_telemetry
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
    CredentialFreeOperationRequest,
    OperationRequest,
    OperationTerminalReceipt,
    require_terminal_receipt_match,
)
from .operations.operation_definition import OperationDefinition, OperationExecutorFactory
from .operations.owner import OperationExecutorContext
from .operations.profile_guard import require_operation_profile
from .operations.public_scalar import PublicDecimal
from .operations.read_capture import capture_read_result
from .operations.registry import (
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
type DiagnosticsReadKind = Literal["run_health", "runs", "latency", "errors", "llm_usage"]
_READ_FRONTENDS = frozenset(OperationFrontendProjection)
_FLUSH_FRONTENDS = frozenset({OperationFrontendProjection.CLI})


class _ReportFilters(TypedDict):
    """Canonical report keyword types, with no additional filtering policy."""

    since: date | None
    until: date | None
    provider: str | None


class DiagnosticsReadRequest(CredentialFreeOperationRequest):
    """Only exact routing and the existing inclusive report filters."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    kind: DiagnosticsReadKind
    since: date | None = None
    until: date | None = None
    provider: str | None = None
    limit: Annotated[int, Field(ge=1)] | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _filters(self) -> Self:
        validate_inclusive_date_range(self.since, self.until)
        if self.limit is not None and self.kind != "runs":
            raise ValueError("limit belongs only to diagnostics runs")
        return self


class _TimingSnapshot(BaseModel):
    """Canonical timing facts with the shared lossless public decimal scalar."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    runs: Annotated[int, Field(ge=0)]
    succeeded: Annotated[int, Field(ge=0)]
    failed: Annotated[int, Field(ge=0)]
    min_duration_ms: int | None = None
    max_duration_ms: int | None = None
    mean_duration_ms: PublicDecimal | None = None


class DiagnosticsRunProviderSnapshot(_TimingSnapshot):
    """Closed copy of the canonical provider timing facts."""

    provider: Annotated[str, Field(min_length=1)]

    @classmethod
    def from_metrics(cls, value: LlmRunProviderMetrics) -> DiagnosticsRunProviderSnapshot:
        """Copy canonical facts without changing decimal precision."""
        return cls.model_validate(_public_timing_values(value))

    def to_metrics(self) -> LlmRunProviderMetrics:
        """Restore the canonical timing row without calculating aggregates."""
        return LlmRunProviderMetrics.model_validate(_native_timing_values(self))


class DiagnosticsRunHealthSnapshot(BaseModel):
    """Complete canonical local auth/timing report, without broader evidence."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    since: date | None = None
    until: date | None = None
    llm_providers: tuple[DiagnosticsRunProviderSnapshot, ...] = ()
    total_runs: Annotated[int, Field(ge=0)] = 0
    total_succeeded: Annotated[int, Field(ge=0)] = 0
    total_failed: Annotated[int, Field(ge=0)] = 0
    auth_provider: str = ""
    auth_configured: bool = False
    persisted_session_present: bool = False
    persisted_session_expired: bool | None = None
    persisted_session_state: str = ""
    probe_summary: str = ""

    @classmethod
    def from_report(cls, value: RunHealthReport) -> DiagnosticsRunHealthSnapshot:
        """Copy the complete service report, including local auth facts."""
        return cls(
            **value.model_dump(exclude={"llm_providers"}),
            llm_providers=tuple(DiagnosticsRunProviderSnapshot.from_metrics(row) for row in value.llm_providers),
        )

    def to_report(self) -> RunHealthReport:
        """Restore the existing report and its canonical derived properties."""
        return RunHealthReport(
            **self.model_dump(exclude={"llm_providers"}),
            llm_providers=tuple(row.to_metrics() for row in self.llm_providers),
        )


class DiagnosticsRunRecordSnapshot(RunRecordView):
    """Complete canonical timing/outcome row."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG


class DiagnosticsLatencyPercentilesSnapshot(BaseModel):
    """Canonical percentiles; the existing service computes every value."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    entries: Annotated[int, Field(ge=0)] = 0
    min_duration_ms: int | None = None
    max_duration_ms: int | None = None
    mean_duration_ms: PublicDecimal | None = None
    p50_duration_ms: int | None = None
    p95_duration_ms: int | None = None
    p99_duration_ms: int | None = None

    @classmethod
    def from_metrics(cls, value: LatencyPercentiles) -> DiagnosticsLatencyPercentilesSnapshot:
        """Copy percentiles produced by the canonical nearest-rank service."""
        return cls.model_validate(_public_timing_values(value))

    def to_metrics(self) -> LatencyPercentiles:
        """Restore existing percentile facts without computing any percentile."""
        return LatencyPercentiles.model_validate(_native_timing_values(self))


class DiagnosticsLatencySnapshot(BaseModel):
    """Complete canonical latency report with a closed nested schema."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    since: date | None = None
    until: date | None = None
    provider: str | None = None
    overall: DiagnosticsLatencyPercentilesSnapshot = Field(default_factory=DiagnosticsLatencyPercentilesSnapshot)
    by_provider: tuple[tuple[str, DiagnosticsLatencyPercentilesSnapshot], ...] = ()

    @classmethod
    def from_report(cls, value: LatencyReport) -> DiagnosticsLatencySnapshot:
        """Copy the full canonical overall and provider reports."""
        return cls(
            since=value.since,
            until=value.until,
            provider=value.provider,
            overall=DiagnosticsLatencyPercentilesSnapshot.from_metrics(value.overall),
            by_provider=tuple(
                (provider, DiagnosticsLatencyPercentilesSnapshot.from_metrics(row))
                for provider, row in value.by_provider
            ),
        )

    def to_report(self) -> LatencyReport:
        """Restore the complete canonical latency presenter model."""
        return LatencyReport(
            since=self.since,
            until=self.until,
            provider=self.provider,
            overall=self.overall.to_metrics(),
            by_provider=tuple((provider, row.to_metrics()) for provider, row in self.by_provider),
        )


class DiagnosticsErrorCountSnapshot(ErrorKindCount):
    """Canonical stable error-kind count."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG


class DiagnosticsErrorsSnapshot(BaseModel):
    """Complete canonical failed-run breakdown."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    since: date | None = None
    until: date | None = None
    provider: str | None = None
    total_runs: Annotated[int, Field(ge=0)] = 0
    total_failed: Annotated[int, Field(ge=0)] = 0
    by_error_kind: tuple[DiagnosticsErrorCountSnapshot, ...] = ()

    def to_report(self) -> ErrorsBreakdownReport:
        """Restore every canonical report field and its existing failure property."""
        return ErrorsBreakdownReport.model_validate(self.model_dump())


class DiagnosticsUsageModelSnapshot(_TimingSnapshot):
    """Canonical per-model metrics, restored for existing success-rate calculation."""

    model: str = ""
    total_duration_ms: Annotated[int, Field(ge=0)] = 0

    @classmethod
    def from_metrics(cls, value: LlmUsageModelMetrics) -> DiagnosticsUsageModelSnapshot:
        """Copy the complete model row without recomputing metrics."""
        return cls.model_validate(_public_timing_values(value))

    def to_metrics(self) -> LlmUsageModelMetrics:
        """Restore the existing per-model metrics and derived success rate."""
        return LlmUsageModelMetrics.model_validate(_native_timing_values(self))


class DiagnosticsUsageProviderSnapshot(_TimingSnapshot):
    """Canonical per-provider/model metrics with closed nested schemas."""

    provider: Annotated[str, Field(min_length=1)]
    total_duration_ms: Annotated[int, Field(ge=0)] = 0
    models: tuple[DiagnosticsUsageModelSnapshot, ...] = ()

    @classmethod
    def from_metrics(cls, value: LlmRunHealthProviderMetrics) -> DiagnosticsUsageProviderSnapshot:
        """Copy the complete canonical provider row and its ordered model rows."""
        return cls.model_validate(
            {
                **_public_timing_values(value, exclude={"models"}),
                "models": tuple(DiagnosticsUsageModelSnapshot.from_metrics(row) for row in value.models),
            }
        )

    def to_metrics(self) -> LlmRunHealthProviderMetrics:
        """Restore existing provider metrics and their canonical derived properties."""
        return LlmRunHealthProviderMetrics.model_validate(
            {
                **_native_timing_values(self, exclude={"models"}),
                "models": tuple(row.to_metrics() for row in self.models),
            }
        )


class DiagnosticsUsageSnapshot(BaseModel):
    """Complete canonical usage report, restored for existing summary properties."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    since: date | None = None
    until: date | None = None
    by_provider: tuple[DiagnosticsUsageProviderSnapshot, ...] = ()
    total_runs: Annotated[int, Field(ge=0)] = 0
    total_succeeded: Annotated[int, Field(ge=0)] = 0
    total_failed: Annotated[int, Field(ge=0)] = 0

    @classmethod
    def from_report(cls, value: LlmUsageReport) -> DiagnosticsUsageSnapshot:
        """Copy the full service report and ordered provider/model breakdowns."""
        return cls(
            **value.model_dump(exclude={"by_provider"}),
            by_provider=tuple(DiagnosticsUsageProviderSnapshot.from_metrics(row) for row in value.by_provider),
        )

    def to_report(self) -> LlmUsageReport:
        """Restore the complete existing usage presenter contract."""
        return LlmUsageReport(
            **self.model_dump(exclude={"by_provider"}),
            by_provider=tuple(row.to_metrics() for row in self.by_provider),
        )


def _public_timing_values(value: BaseModel, *, exclude: set[str] | None = None) -> dict[str, object]:
    """Copy only the decimal representation; preserve every other service fact."""
    values = cast("dict[str, object]", value.model_dump(exclude=exclude))
    mean = values["mean_duration_ms"]
    if isinstance(mean, Decimal):
        values["mean_duration_ms"] = PublicDecimal(decimal=str(mean))
    return values


def _native_timing_values(
    value: _TimingSnapshot | DiagnosticsLatencyPercentilesSnapshot, *, exclude: set[str] | None = None
) -> dict[str, object]:
    """Restore the shared public scalar without calculating timing metrics."""
    excluded = exclude | {"mean_duration_ms"} if exclude is not None else {"mean_duration_ms"}
    values = cast("dict[str, object]", value.model_dump(exclude=excluded))
    mean = value.mean_duration_ms
    values["mean_duration_ms"] = Decimal(mean.decimal) if mean is not None else None
    return values


class DiagnosticsReadProjection(DiagnosticsReadRequest):
    """One complete canonical report and the exact selection that produced it."""

    run_health: DiagnosticsRunHealthSnapshot | None = None
    runs: tuple[DiagnosticsRunRecordSnapshot, ...] | None = None
    latency: DiagnosticsLatencySnapshot | None = None
    errors: DiagnosticsErrorsSnapshot | None = None
    llm_usage: DiagnosticsUsageSnapshot | None = None

    @model_validator(mode="after")
    def _one_report(self) -> Self:
        selected = {
            "run_health": self.run_health,
            "runs": self.runs,
            "latency": self.latency,
            "errors": self.errors,
            "llm_usage": self.llm_usage,
        }
        if any((value is not None) != (kind == self.kind) for kind, value in selected.items()):
            raise ValueError("diagnostics result does not match its report kind")
        for report in (self.run_health, self.latency, self.errors, self.llm_usage):
            if report is not None and (report.since != self.since or report.until != self.until):
                raise ValueError("diagnostics report window differs from the request")
        for report in (self.latency, self.errors):
            if report is not None and report.provider != self.provider:
                raise ValueError("diagnostics report provider differs from the request")
        if self.runs is not None and self.limit is not None and len(self.runs) > self.limit:
            raise ValueError("diagnostics run rows exceed the requested limit")
        return self


class DiagnosticsReadExecutionResult(BaseModel):
    """Encrypted retained report until current destination authorization."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: DiagnosticsReadProjection


class DiagnosticsTelemetryFlushRequest(CredentialFreeOperationRequest):
    """Per-invocation consent and explicit worker telemetry overrides."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    dry_run: bool = True
    acknowledged: bool = False
    opt_in: bool | None = None
    tier: TelemetryTier | None = None
    endpoint: str | None = None


class DiagnosticsTelemetryCountersSnapshot(BaseModel):
    """The exact three counters produced by the canonical diagnostics flush."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    runs: Annotated[int, Field(ge=0)]
    succeeded: Annotated[int, Field(ge=0)]
    failed: Annotated[int, Field(ge=0)]


class DiagnosticsTelemetryTimingsSnapshot(BaseModel):
    """Flush reports no timings; an undeclared metric is refused, never dropped."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG


class DiagnosticsTelemetryPayloadSnapshot(BaseModel):
    """Closed complete copy of the canonical flush payload, with identical JSON."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    schema_version: Literal[1] = 1
    workspace_hash: ContentDigest
    command: Literal["diagnostics.llm_run"]
    counters: DiagnosticsTelemetryCountersSnapshot
    timings_ms: DiagnosticsTelemetryTimingsSnapshot
    succeeded: bool
    error_kind: None = None
    captured_at: Annotated[str, Field(min_length=1)]


class DiagnosticsTelemetryPreviewSnapshot(BaseModel):
    """Complete canonical allowlisted payload and current consent verdict."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    payload: DiagnosticsTelemetryPayloadSnapshot
    gate_permits: bool
    endpoint_configured: bool
    would_send: bool

    def to_preview(self) -> TelemetryFlushPreview:
        """Restore the canonical presenter model without recomputing any value."""
        return TelemetryFlushPreview.model_validate(self.model_dump())


class DiagnosticsTelemetryFlushProjection(BaseModel):
    """Legacy sent flag means attempted handoff, never confirmed delivery."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    dry_run: bool
    preview: DiagnosticsTelemetryPreviewSnapshot
    sent: bool

    @model_validator(mode="after")
    def _send_facts(self) -> Self:
        if self.preview.would_send != (self.preview.gate_permits and self.preview.endpoint_configured):
            raise ValueError("telemetry preview gate facts are inconsistent")
        if self.sent != (not self.dry_run and self.preview.would_send):
            raise ValueError("telemetry attempted handoff differs from its preview")
        return self


class DiagnosticsTelemetryFlushExecutionResult(BaseModel):
    """Encrypted retained preview and its settled external-attempt fact."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: DiagnosticsTelemetryFlushProjection


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
    payload = request.payload
    expected_type = DiagnosticsTelemetryFlushRequest if flush else DiagnosticsReadRequest
    if request.definition_id != expected or type(payload) is not expected_type:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if not isinstance(payload, (DiagnosticsReadRequest, DiagnosticsTelemetryFlushRequest)):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if payload.profile_id != context.profile_id or request.subject_ref != profile_operation_subject(
        str(payload.profile_id)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    frontends = _FLUSH_FRONTENDS if flush else _READ_FRONTENDS
    actions = RESUMABLE_READ_ACTIONS
    if isinstance(payload, DiagnosticsTelemetryFlushRequest) and not payload.dry_run:
        actions = actions | frozenset({AccessAction.COMMIT})
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
        permitted_frontends=_READ_FRONTENDS,
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
