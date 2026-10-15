"""Service startup retains typed failures without exposing exception payloads."""

from __future__ import annotations

import logging

import pytest

from cadrumo_client.contracts.contracts import RefusalCode, RefusalError

from ...adapters.agent_programs import AgentProgramRefusalError
from ...service import service_failure
from ..controller import AgentHostError, AgentHostRefusal
from ..launcher_protocol import AgentLauncherRefusal

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (AgentHostError(AgentHostRefusal.STORES_NEWER), "agent_service_incompatible"),
        (AgentHostError(AgentHostRefusal.SIGNED_OUT), "agent_signed_out"),
        (AgentHostError(AgentHostRefusal.CREDENTIALS_UNAVAILABLE), "agent_provider_credential_missing"),
        (AgentProgramRefusalError(AgentLauncherRefusal.SERVICE_ABSENT), "agent_service_absent"),
    ],
)
def test_startup_failure_preserves_the_launcher_category(error: Exception, code: str) -> None:
    assert service_failure(error) == {"event": "refused", "code": code}


def test_hosted_proof_refusal_remains_visible_in_diagnostics(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="cadrumo_agent_service.service"):
        result = service_failure(AgentHostError(AgentHostRefusal.AGENT_REFUSED, agent_code="hosted_lane_unproven"))
    assert result == {"event": "refused", "code": "agent_service_failed"}
    assert "hosted_lane_unproven" in caplog.text


def test_unexpected_failure_never_serializes_or_logs_the_exception(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR, logger="cadrumo_agent_service.service"):
        result = service_failure(ValueError("synthetic-private-payload"))
    assert result == {"event": "refused", "code": "service_failed"}
    assert "ValueError" in caplog.text
    assert "synthetic-private-payload" not in caplog.text


def test_runtime_refusal_keeps_its_closed_reason_in_diagnostics(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="cadrumo_agent_service.service"):
        result = service_failure(RefusalError(RefusalCode.DEADLINE_EXCEEDED))
    assert result == {"event": "refused", "code": "service_failed"}
    assert RefusalCode.DEADLINE_EXCEEDED.value in caplog.text
