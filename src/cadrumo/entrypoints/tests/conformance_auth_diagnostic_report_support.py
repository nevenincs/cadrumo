"""Registered-executor conformance scenario for the encrypted phone-state diagnostic report."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from ...adapters.persistence.profile.auth_diagnostics import build_auth_diagnostic_persistence
from ...application.auth.diagnostic_report_operation import (
    AUTH_DIAGNOSTIC_REPORT_OPERATION_DEFINITION_ID,
    AuthDiagnosticReportProjection,
    AuthDiagnosticReportRequest,
)
from ...application.auth.diagnostics import AuthDiagnosticPhoneState, AuthDiagnosticReportResult
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.time.clock import now
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)

_DIAGNOSTIC_ID = "conformance-diagnostic-1"
_PHONE_STATE = AuthDiagnosticPhoneState.APP_PROMPTED_NOT_ACCEPTED
_CAPTURED_AT = datetime(2026, 5, 19, 8, 0, tzinfo=UTC)
_SEEDED_PAYLOAD: dict[str, object] = {
    "diagnostic_id": _DIAGNOSTIC_ID,
    "reason": "post-auth-landing-timeout",
    "url": "https://diagnostics.invalid/landing",
    "captured_at": _CAPTURED_AT.isoformat(),
    "html": "<main>conformance diagnostic capture</main>",
}


def _prepare_report(context: ConformanceFamilyContext) -> ConformancePreparation:
    persistence = build_auth_diagnostic_persistence()
    persistence.save_record(_DIAGNOSTIC_ID, json.dumps(_SEEDED_PAYLOAD).encode("utf-8"), written_at=_CAPTURED_AT)
    request = AuthDiagnosticReportRequest(
        profile_id=context.profile_id, diagnostic_id=_DIAGNOSTIC_ID, phone_state=_PHONE_STATE
    )
    started_at = now()

    def verify(outcome: ConformanceOutcome) -> None:
        projection = outcome.resolve_result(AuthDiagnosticReportProjection)
        assert projection.report is not None
        reported_at = projection.report.reported_at
        assert started_at <= reported_at <= now()
        assert projection == AuthDiagnosticReportProjection(
            profile_id=context.profile_id,
            operation_id=AUTH_DIAGNOSTIC_REPORT_OPERATION_DEFINITION_ID,
            outcome="completed",
            effect=OperationEffect.UPDATED,
            report=AuthDiagnosticReportResult(
                diagnostic_id=_DIAGNOSTIC_ID, phone_state=_PHONE_STATE, reported_at=reported_at
            ),
        )
        # The operator's report is written back into the same encrypted record,
        # beside everything the capture already held.
        stored = persistence.load_record(_DIAGNOSTIC_ID)
        assert stored is not None
        persisted = json.loads(stored.payload.decode("utf-8"))
        for key, value in _SEEDED_PAYLOAD.items():
            assert persisted[key] == value, key
        assert persisted["operator_report"]["phone_state"] == _PHONE_STATE.value
        assert datetime.fromisoformat(persisted["operator_report"]["reported_at"]) == reported_at

    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(context.profile_id)), request=request, verify=verify
    )


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    if context.definition.definition_id == AUTH_DIAGNOSTIC_REPORT_OPERATION_DEFINITION_ID:
        return _prepare_report(context)
    raise AssertionError(f"no auth diagnostic report conformance scenario for {context.definition.definition_id}")


AUTH_DIAGNOSTIC_REPORT_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        RegisteredExecutorConformanceCase(
            AUTH_DIAGNOSTIC_REPORT_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            # A seeded record exists, so the guarded save runs and settles UPDATED.
            OperationEffect.UPDATED,
            (AUTH_DIAGNOSTIC_REPORT_OPERATION_DEFINITION_ID,),
        ),
    ),
    prepare=_prepare,
)


def _prepare_absent_report(context: ConformanceFamilyContext) -> ConformancePreparation:
    persistence = build_auth_diagnostic_persistence()
    assert persistence.list_records() == ()

    def verify(outcome: ConformanceOutcome) -> None:
        del outcome
        assert persistence.list_records() == ()

    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(context.profile_id)),
        request=AuthDiagnosticReportRequest(
            profile_id=context.profile_id,
            diagnostic_id="absent-conformance-diagnostic",
            phone_state=AuthDiagnosticPhoneState.APP_DID_NOT_PROMPT,
        ),
        verify=verify,
    )


AUTH_DIAGNOSTIC_ABSENT_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        RegisteredExecutorConformanceCase(
            AUTH_DIAGNOSTIC_REPORT_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            (AUTH_DIAGNOSTIC_REPORT_OPERATION_DEFINITION_ID,),
            expected_refusal_ref="REFUSED_AUTH_DIAGNOSTIC_NOT_FOUND",
        ),
    ),
    prepare=_prepare_absent_report,
)
