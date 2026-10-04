"""Registered-executor conformance scenario for the consent-gated telemetry flush."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from ...adapters.persistence.llm.run_telemetry import LLMRunRecord, LLMRunTelemetryRecorder
from ...application.diagnostics_operation import DIAGNOSTICS_TELEMETRY_FLUSH_OPERATION_DEFINITION_ID
from ...application.diagnostics_telemetry_contracts import (
    DiagnosticsTelemetryCountersSnapshot,
    DiagnosticsTelemetryFlushProjection,
    DiagnosticsTelemetryFlushRequest,
    DiagnosticsTelemetryPayloadSnapshot,
    DiagnosticsTelemetryPreviewSnapshot,
    DiagnosticsTelemetryTimingsSnapshot,
)
from ...core.config import load_settings
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.time.clock import now
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)

# The reserved ``.invalid`` top-level domain never resolves, so even a defect in
# the consent gate could not reach a real collector.
_ENDPOINT = "https://telemetry.invalid/ingest"
_CALLER = "cadrumo.application.ledger.llm_classification"
_PROVIDER = "llm:claude:conformance-model"

# Two successes and one failure: the flush aggregates every recorded run.
_SEEDED_RUNS = (
    LLMRunRecord(
        run_id="conformance-flush-first",
        caller=_CALLER,
        provider=_PROVIDER,
        model="conformance-model",
        duration_ms=700,
        succeeded=True,
        started_at=datetime(2026, 4, 1, 9, 0, tzinfo=UTC),
    ),
    LLMRunRecord(
        run_id="conformance-flush-second",
        caller=_CALLER,
        provider=_PROVIDER,
        model="conformance-model",
        duration_ms=900,
        succeeded=True,
        started_at=datetime(2026, 4, 2, 9, 0, tzinfo=UTC),
    ),
    LLMRunRecord(
        run_id="conformance-flush-failed",
        caller=_CALLER,
        provider=_PROVIDER,
        model="conformance-model",
        duration_ms=45000,
        succeeded=False,
        error_kind="LLMClassifierError",
        started_at=datetime(2026, 4, 3, 9, 0, tzinfo=UTC),
    ),
)


def _prepare_flush(context: ConformanceFamilyContext) -> ConformancePreparation:
    recorder = LLMRunTelemetryRecorder()
    for record in _SEEDED_RUNS:
        recorder.record(record)
    succeeded = sum(1 for record in _SEEDED_RUNS if record.succeeded)
    failed = len(_SEEDED_RUNS) - succeeded
    # The workspace pseudonym is the SHA-256 of the resolved local storage root.
    workspace_hash = hashlib.sha256(
        str(Path(load_settings().cadrumo_local_storage_root).resolve()).encode("utf-8")
    ).hexdigest()
    # A real (non-dry-run) flush that the operator did not acknowledge: the
    # consent gate ANDs the per-invocation acknowledgement, so nothing is sent
    # whatever the deployment's opt-in or tier, and the effect stays NONE.
    request = DiagnosticsTelemetryFlushRequest(
        profile_id=context.profile_id,
        dry_run=False,
        acknowledged=False,
        endpoint=_ENDPOINT,
    )
    started_at = now()

    def verify(outcome: ConformanceOutcome) -> None:
        projection = outcome.resolve_result(DiagnosticsTelemetryFlushProjection)
        settled_at = now()
        captured_at = datetime.fromisoformat(projection.preview.payload.captured_at)
        assert started_at <= captured_at <= settled_at
        assert projection == DiagnosticsTelemetryFlushProjection(
            profile_id=context.profile_id,
            dry_run=False,
            preview=DiagnosticsTelemetryPreviewSnapshot(
                payload=DiagnosticsTelemetryPayloadSnapshot(
                    workspace_hash=workspace_hash,
                    command="diagnostics.llm_run",
                    counters=DiagnosticsTelemetryCountersSnapshot(
                        runs=len(_SEEDED_RUNS), succeeded=succeeded, failed=failed
                    ),
                    timings_ms=DiagnosticsTelemetryTimingsSnapshot(),
                    succeeded=failed == 0,
                    captured_at=projection.preview.payload.captured_at,
                ),
                gate_permits=False,
                endpoint_configured=True,
                would_send=False,
            ),
            sent=False,
        )

    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(context.profile_id)), request=request, verify=verify
    )


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    if context.definition.definition_id == DIAGNOSTICS_TELEMETRY_FLUSH_OPERATION_DEFINITION_ID:
        return _prepare_flush(context)
    raise AssertionError(f"no telemetry conformance scenario for {context.definition.definition_id}")


DIAGNOSTICS_TELEMETRY_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        RegisteredExecutorConformanceCase(
            DIAGNOSTICS_TELEMETRY_FLUSH_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            # No sink invocation was attempted, so no external effect can have occurred.
            OperationEffect.NONE,
            # `dispatch` is published only when the consent gate and an endpoint both permit a send.
            (
                "diagnostics.telemetry.flush.prepare",
                "diagnostics.telemetry.flush.settlement",
            ),
        ),
    ),
    prepare=_prepare,
)
