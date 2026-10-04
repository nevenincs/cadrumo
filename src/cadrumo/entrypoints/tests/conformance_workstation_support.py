"""Consent refusal and complete machine-report conformance through real executors."""

from __future__ import annotations

from datetime import UTC, datetime

from ...adapters.persistence.llm.run_telemetry import LLMRunRecord, LLMRunTelemetryRecorder
from ...application.diagnostics_telemetry_contracts import (
    DiagnosticsTelemetryFlushProjection,
    DiagnosticsTelemetryFlushRequest,
)
from ...application.workstation_check_operation import WorkstationCheckProjection, WorkstationCheckRequest
from ...core.capabilities import ServiceCapability
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    if context.definition.definition_id == "diagnostics.telemetry.flush":
        LLMRunTelemetryRecorder().record(
            LLMRunRecord(
                run_id="conformance-flush-success",
                caller="conformance",
                provider="llm:codex:conformance",
                model="conformance",
                duration_ms=10,
                succeeded=True,
                started_at=datetime(2026, 4, 1, tzinfo=UTC),
            )
        )
        LLMRunTelemetryRecorder().record(
            LLMRunRecord(
                run_id="conformance-flush-failure",
                caller="conformance",
                provider="llm:codex:conformance",
                model="conformance",
                duration_ms=20,
                succeeded=False,
                error_kind="LLMClassifierError",
                started_at=datetime(2026, 4, 2, tzinfo=UTC),
            )
        )
        request = DiagnosticsTelemetryFlushRequest(
            profile_id=context.profile_id,
            dry_run=False,
            acknowledged=False,
            opt_in=False,
            endpoint="http://127.0.0.1:1/telemetry",
        )

        def verify(outcome: ConformanceOutcome) -> None:
            result = outcome.resolve_result(DiagnosticsTelemetryFlushProjection)
            assert result.profile_id == context.profile_id and result.dry_run is False
            assert result.sent is False and result.preview.would_send is False
            assert result.preview.gate_permits is False and result.preview.endpoint_configured is True
            assert result.preview.payload.counters.runs == 2
            assert result.preview.payload.counters.succeeded == 1
            assert result.preview.payload.counters.failed == 1

        return ConformancePreparation(profile_operation_subject(str(context.profile_id)), request, verify=verify)
    if context.definition.definition_id == "diagnostics.workstation.check":

        def verify(outcome: ConformanceOutcome) -> None:
            result = outcome.resolve_result(WorkstationCheckProjection)
            assert result.profile_id == context.profile_id
            assert {row.capability for row in result.capabilities} == set(ServiceCapability)
            services = {row.service for row in result.dependencies}
            assert "extra:google" in services and result.preflight
            assert len(services) == len(result.dependencies)
            # Closed runtime endpoint proves absent local models remain unavailable.
            readers = tuple(row for row in result.dependencies if row.service.startswith("local-reader:"))
            assert {row.service for row in readers} == {
                "local-reader:text_extraction",
                "local-reader:vision_transcription",
            }
            assert all(not row.available for row in readers)
            assert all(row.to_status().facts["runtime_reachable"] is False for row in readers)

        return ConformancePreparation(
            profile_operation_subject(str(context.profile_id)),
            WorkstationCheckRequest(profile_id=context.profile_id),
            verify=verify,
        )
    raise AssertionError(context.definition.definition_id)


WORKSTATION_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        RegisteredExecutorConformanceCase(
            "diagnostics.telemetry.flush",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("diagnostics.telemetry.flush.prepare", "diagnostics.telemetry.flush.settlement"),
        ),
        RegisteredExecutorConformanceCase(
            "diagnostics.workstation.check",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("diagnostics.workstation.check",),
        ),
    ),
    prepare=_prepare,
    closes_model_runtime=True,
)
