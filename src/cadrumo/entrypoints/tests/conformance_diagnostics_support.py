"""Registered-executor conformance scenarios for the diagnostics operation family."""

from __future__ import annotations

from datetime import UTC, date, datetime

from ...adapters.persistence.llm.run_records import LLMRunRecord, LLMRunRecorder
from ...application.diagnostics_operation import DIAGNOSTICS_READ_OPERATION_DEFINITION_ID
from ...application.diagnostics_read_contracts import DiagnosticsReadProjection, DiagnosticsReadRequest
from ...application.diagnostics_run_report_contracts import DiagnosticsRunRecordSnapshot
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)

_CLAUDE = "llm:claude:conformance-model"
_CODEX = "llm:codex:conformance-model"
_CALLER = "cadrumo.application.ledger.llm_classification"
_WINDOW_START = date(2026, 4, 1)
_WINDOW_END = date(2026, 4, 30)

# Seeded through the production recorder. Only the two Claude runs inside the
# window survive the provider and date filters; the other two prove each
# filter actually excludes.
_SEEDED_RUNS = (
    LLMRunRecord(
        run_id="conformance-run-before-window",
        caller=_CALLER,
        provider=_CLAUDE,
        model="conformance-model",
        duration_ms=900,
        succeeded=True,
        started_at=datetime(2026, 3, 31, 23, 0, tzinfo=UTC),
    ),
    LLMRunRecord(
        run_id="conformance-run-first",
        caller=_CALLER,
        provider=_CLAUDE,
        model="conformance-model",
        duration_ms=1200,
        succeeded=True,
        started_at=datetime(2026, 4, 1, 9, 0, tzinfo=UTC),
    ),
    LLMRunRecord(
        run_id="conformance-run-other-provider",
        caller=_CALLER,
        provider=_CODEX,
        model="conformance-model",
        duration_ms=800,
        succeeded=True,
        started_at=datetime(2026, 4, 2, 9, 0, tzinfo=UTC),
    ),
    LLMRunRecord(
        run_id="conformance-run-failed",
        caller=_CALLER,
        provider=_CLAUDE,
        model="conformance-model",
        duration_ms=45000,
        succeeded=False,
        error_kind="LLMClassifierError",
        started_at=datetime(2026, 4, 3, 9, 0, tzinfo=UTC),
    ),
)


def _expected_row(record: LLMRunRecord) -> DiagnosticsRunRecordSnapshot:
    return DiagnosticsRunRecordSnapshot(
        run_id=record.run_id,
        caller=record.caller,
        provider=record.provider,
        model=record.model,
        duration_ms=record.duration_ms,
        succeeded=record.succeeded,
        error_kind=record.error_kind,
        started_at=record.started_at,
    )


def _prepare_read(context: ConformanceFamilyContext) -> ConformancePreparation:
    recorder = LLMRunRecorder()
    for record in _SEEDED_RUNS:
        recorder.record(record)
    by_id = {record.run_id: record for record in _SEEDED_RUNS}
    request = DiagnosticsReadRequest(
        profile_id=context.profile_id,
        kind="runs",
        since=_WINDOW_START,
        until=_WINDOW_END,
        provider=_CLAUDE,
        limit=5,
    )
    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(context.profile_id)),
        request=request,
        expected_result=DiagnosticsReadProjection(
            profile_id=context.profile_id,
            kind="runs",
            since=_WINDOW_START,
            until=_WINDOW_END,
            provider=_CLAUDE,
            limit=5,
            # Most recent first.
            runs=(
                _expected_row(by_id["conformance-run-failed"]),
                _expected_row(by_id["conformance-run-first"]),
            ),
        ),
    )


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    if context.definition.definition_id == DIAGNOSTICS_READ_OPERATION_DEFINITION_ID:
        return _prepare_read(context)
    raise AssertionError(f"no diagnostics conformance scenario for {context.definition.definition_id}")


DIAGNOSTICS_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        RegisteredExecutorConformanceCase(
            DIAGNOSTICS_READ_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("diagnostics.read.execute",),
        ),
    ),
    prepare=_prepare,
)
