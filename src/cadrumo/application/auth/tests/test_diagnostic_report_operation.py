"""Encrypted diagnostic report preparation and registered refusal contract."""

from __future__ import annotations

import asyncio
from datetime import datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest

from ....core.operations import profile_operation_subject
from ...operations.models import OperationIdentity, OperationRequest
from ...operations.owner import OperationExecutorContext
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import AccessDenialCode
from ...user_profile.access_errors import ProfileAccessRefusedError
from .. import diagnostic_report_operation as diagnostic_report_module
from ..diagnostic_report_operation import (
    AUTH_DIAGNOSTIC_NOT_FOUND_REFUSAL_CODE,
    AUTH_DIAGNOSTIC_REPORT_OPERATION_DEFINITION_ID,
    AuthDiagnosticReportExecutor,
    AuthDiagnosticReportPorts,
    AuthDiagnosticReportRequest,
    build_auth_diagnostic_report_definition,
    build_auth_diagnostic_report_registration,
)
from ..diagnostics import (
    AuthDiagnosticPhoneState,
    persist_auth_diagnostic_phone_state,
    prepare_auth_diagnostic_phone_state,
)
from ..diagnostics_ports import AuthDiagnosticPersistenceRecord

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("3a3a3a3a-3a3a-4a3a-8a3a-3a3a3a3a3a3a")
_OTHER = UUID("4b4b4b4b-4b4b-4b4b-8b4b-4b4b4b4b4b4b")


class _UnusedDiagnosticFactory:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, *, bucket_id: str) -> AuthDiagnosticReportPorts:
        self.calls.append(bucket_id)
        raise AssertionError(f"unexpected execution for {bucket_id}")


class _PhaseRecorder:
    def __init__(self) -> None:
        self.phases: list[str] = []

    async def phase(self, phase_code: str) -> None:
        self.phases.append(phase_code)


class _DiagnosticPort:
    def __init__(self) -> None:
        self.saved: list[tuple[str, bytes]] = []

    def list_records(self) -> tuple[AuthDiagnosticPersistenceRecord, ...]:
        return ()

    def load_record(self, diagnostic_id: str) -> AuthDiagnosticPersistenceRecord | None:
        if diagnostic_id != "d-1":
            return None
        return AuthDiagnosticPersistenceRecord(payload=b'{"diagnostic_id":"d-1"}')

    def save_record(self, diagnostic_id: str, payload: bytes, *, written_at: datetime) -> None:
        del written_at
        self.saved.append((diagnostic_id, payload))


def test_report_prepare_is_prewrite_and_commit_preserves_canonical_phone_state() -> None:
    """A known miss writes nothing; a prepared known record writes only on commit."""
    port = _DiagnosticPort()
    assert (
        prepare_auth_diagnostic_phone_state(
            "missing", AuthDiagnosticPhoneState.APP_DID_NOT_PROMPT.value, persistence=port
        )
        is None
    )
    prepared = prepare_auth_diagnostic_phone_state(
        "d-1", AuthDiagnosticPhoneState.APP_DID_NOT_PROMPT.value, persistence=port
    )
    assert prepared is not None
    assert port.saved == []
    persist_auth_diagnostic_phone_state(prepared, persistence=port)
    assert port.saved[0][0] == "d-1"
    assert b"app_did_not_prompt" in port.saved[0][1]
    assert prepared.result.phone_state is AuthDiagnosticPhoneState.APP_DID_NOT_PROMPT


def test_report_public_definition_is_a_real_human_mutation() -> None:
    """The public schema compiles with typed absence and a closed phone state."""
    factory = _UnusedDiagnosticFactory()
    definition = build_auth_diagnostic_report_definition(factory)
    registration = build_auth_diagnostic_report_registration(definition)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    assert AUTH_DIAGNOSTIC_NOT_FOUND_REFUSAL_CODE in registry.definitions[0].refusal_detail_codes
    assert OperationFrontendProjection.MCP not in registry.definitions[0].permitted_frontends
    request = AuthDiagnosticReportRequest(
        profile_id=_PROFILE,
        diagnostic_id="d-1",
        phone_state=AuthDiagnosticPhoneState.APP_DID_NOT_PROMPT,
    )
    assert request.phone_state.value == "app_did_not_prompt"
    assert factory.calls == []


@pytest.mark.parametrize("mismatch", ["request_subject", "context_definition", "context_subject"])
def test_report_executor_refuses_identity_mismatch_before_profile_access_or_work(
    monkeypatch: pytest.MonkeyPatch, mismatch: str
) -> None:
    """The real executor refuses all three identity mismatches before protected work."""
    expected_subject = profile_operation_subject(str(_PROFILE))
    other_subject = profile_operation_subject(str(_OTHER))
    request_subject = other_subject if mismatch == "request_subject" else expected_subject
    context_definition = (
        "auth.diagnostics.other" if mismatch == "context_definition" else AUTH_DIAGNOSTIC_REPORT_OPERATION_DEFINITION_ID
    )
    context_subject = other_subject if mismatch == "context_subject" else request_subject
    request = OperationRequest[AuthDiagnosticReportRequest](
        definition_id=AUTH_DIAGNOSTIC_REPORT_OPERATION_DEFINITION_ID,
        subject_ref=request_subject,
        payload=AuthDiagnosticReportRequest(
            profile_id=_PROFILE,
            diagnostic_id="d-1",
            phone_state=AuthDiagnosticPhoneState.APP_DID_NOT_PROMPT,
        ),
    )
    events = _PhaseRecorder()
    context = SimpleNamespace(
        identity=OperationIdentity(
            operation_id="b" * 64,
            definition_id=context_definition,
            subject_ref=context_subject,
        ),
        events=events,
    )
    active_profile_lookups: list[None] = []
    factory = _UnusedDiagnosticFactory()

    def active_profile_must_not_be_read() -> str:
        active_profile_lookups.append(None)
        raise AssertionError("identity refusal must precede the active-profile lookup")

    monkeypatch.setattr(diagnostic_report_module, "require_active_bucket_id", active_profile_must_not_be_read)

    with pytest.raises(ProfileAccessRefusedError) as refused:
        asyncio.run(AuthDiagnosticReportExecutor(factory).execute(request, cast(OperationExecutorContext, context)))

    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH
    assert active_profile_lookups == []
    assert events.phases == []
    assert factory.calls == []
