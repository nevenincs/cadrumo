"""Encrypted diagnostic report preparation and registered refusal contract."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import pytest

from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ..diagnostic_report_operation import (
    AUTH_DIAGNOSTIC_NOT_FOUND_REFUSAL_CODE,
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

    def unused_factory(*, bucket_id: str) -> AuthDiagnosticReportPorts:
        raise AssertionError(f"unexpected execution for {bucket_id}")

    definition = build_auth_diagnostic_report_definition(unused_factory)
    registration = build_auth_diagnostic_report_registration(definition)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    assert AUTH_DIAGNOSTIC_NOT_FOUND_REFUSAL_CODE in registry.definitions[0].refusal_detail_codes
    assert OperationFrontendProjection.MCP not in registry.definitions[0].permitted_frontends
    request = AuthDiagnosticReportRequest(
        profile_id=UUID("3a3a3a3a-3a3a-4a3a-8a3a-3a3a3a3a3a3a"),
        diagnostic_id="d-1",
        phone_state=AuthDiagnosticPhoneState.APP_DID_NOT_PROMPT,
    )
    assert request.phone_state.value == "app_did_not_prompt"
