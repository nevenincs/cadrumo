"""Service startup retains typed failures without exposing exception payloads."""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from cadrumo.tests.log_records import delivered_records, delivered_text
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.service_client import InstalledServiceClient

from ...adapters.agent_programs import AgentProgramRefusalError
from ...providers.domain.record import LocalEngine
from ...service import AgentService
from ...service_support import service_failure
from ..controller import AgentHostError, AgentHostRefusal
from ..launcher_protocol import AgentLauncherRefusal

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (AgentHostError(AgentHostRefusal.STORES_NEWER), "agent_service_incompatible"),
        (AgentHostError(AgentHostRefusal.SIGNED_OUT), "agent_signed_out"),
        (AgentHostError(AgentHostRefusal.TIMEOUT), "agent_timeout"),
        (RefusalError(RefusalCode.TIMEOUT), "agent_timeout"),
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
    assert "hosted_lane_unproven" in delivered_text(caplog)


def test_unexpected_failure_never_serializes_or_logs_the_exception(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR, logger="cadrumo_agent_service.service"):
        result = service_failure(ValueError("synthetic-private-payload"))
    assert result == {"event": "refused", "code": "service_failed"}
    assert "ValueError" in delivered_text(caplog)
    assert "synthetic-private-payload" not in delivered_text(caplog)


def test_runtime_refusal_keeps_its_closed_reason_in_diagnostics(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="cadrumo_agent_service.service"):
        result = service_failure(RefusalError(RefusalCode.TIMEOUT))
    assert result == {"event": "refused", "code": "agent_timeout"}
    assert RefusalCode.TIMEOUT.value in delivered_text(caplog)


def test_an_absent_runtime_is_reported_as_typed_unavailability(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="cadrumo_agent_service.service"):
        result = service_failure(RefusalError(RefusalCode.UNAVAILABLE))
    assert result == {"event": "refused", "code": "agent_runtime_unavailable"}
    assert RefusalCode.UNAVAILABLE.value in delivered_text(caplog)


_LOGGER_NAME = "cadrumo_agent_service.service"


def _cancelled_start_records(
    caplog: pytest.LogCaptureFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cancel: str
) -> tuple[list[dict[str, Any]], list[logging.LogRecord]]:
    """Run the service's real start thread body with a start that is cancelled the way ``cancel`` cancels it."""
    emitted: list[dict[str, Any]] = []
    client = SimpleNamespace(lease=object(), connection=SimpleNamespace(close=lambda: None))
    service = AgentService(
        local_engine_default=LocalEngine.LLAMACPP,
        client=cast(InstalledServiceClient, client),
        storage_root=tmp_path / "storage",
        gateway_bearer=bytearray(b"synthetic-bearer"),
        emit=emitted.append,
    )

    def cancelled_start(deadline: object, cancellation: object) -> dict[str, Any]:
        if cancel == "sign_out":
            client.lease = None  # the runtime withdrew the lease before the service was closed
            service.request_close()
        elif cancel == "close":
            service.request_close()
        elif cancel == "stop":
            service._admit_stop()
        raise AgentHostError(AgentHostRefusal.CANCELLED)

    monkeypatch.setattr(service, "_start_owned", cancelled_start)
    service._closing.clear()
    try:
        with caplog.at_level(logging.INFO, logger=_LOGGER_NAME):
            service._startup_cancellation = None
            service._background_start()
            records = delivered_records(caplog, _LOGGER_NAME)
    finally:
        service.close()
    return emitted, records


def test_a_start_cancelled_by_a_person_sign_out_is_one_info_record_and_no_warning(
    caplog: pytest.LogCaptureFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, records = _cancelled_start_records(caplog, tmp_path, monkeypatch, "sign_out")
    cancelled = [record for record in records if "agent startup" in record.getMessage()]
    assert [(record.levelno, record.getMessage()) for record in cancelled] == [
        (logging.INFO, "agent startup cancelled: person signed out")
    ]
    assert not [record for record in records if record.levelno >= logging.WARNING]


def test_a_start_cancelled_by_the_service_closing_is_logged_at_info(
    caplog: pytest.LogCaptureFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, records = _cancelled_start_records(caplog, tmp_path, monkeypatch, "close")
    cancelled = [record for record in records if "agent startup" in record.getMessage()]
    assert [(record.levelno, record.getMessage()) for record in cancelled] == [
        (logging.INFO, "agent startup cancelled: service stopping")
    ]


def test_a_start_cancelled_by_a_stop_request_is_logged_at_info_with_its_cause(
    caplog: pytest.LogCaptureFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, records = _cancelled_start_records(caplog, tmp_path, monkeypatch, "stop")
    cancelled = [record for record in records if "agent startup" in record.getMessage()]
    assert [(record.levelno, record.getMessage()) for record in cancelled] == [
        (logging.INFO, "agent startup cancelled: stop requested")
    ]


def test_a_cancelled_start_with_no_known_cause_stays_a_warning(
    caplog: pytest.LogCaptureFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    emitted, records = _cancelled_start_records(caplog, tmp_path, monkeypatch, "unknown")
    cancelled = [record for record in records if "agent startup" in record.getMessage()]
    assert [(record.levelno, record.getMessage()) for record in cancelled] == [
        (logging.WARNING, "agent startup refused reason=cancelled agent_code=None")
    ]
    assert emitted[-1]["event"] == "refused"


@pytest.mark.parametrize("cancel", ["sign_out", "close", "stop"])
def test_the_published_refusal_of_a_cancelled_start_does_not_change_with_its_cause(
    caplog: pytest.LogCaptureFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cancel: str
) -> None:
    emitted, _ = _cancelled_start_records(caplog, tmp_path, monkeypatch, cancel)
    unknown, _ = _cancelled_start_records(caplog, tmp_path, monkeypatch, "unknown")
    code = service_failure(AgentHostError(AgentHostRefusal.CANCELLED))
    assert unknown == [code]
    assert emitted in ([], [code])  # a closing service publishes nothing; a stop request publishes the same code


def test_a_refusal_that_is_not_a_cancellation_still_logs_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    error = AgentHostError(AgentHostRefusal.LAUNCH_FAILED)
    error.cancel_cause = "person signed out"
    with caplog.at_level(logging.INFO, logger=_LOGGER_NAME):
        service_failure(error)
    assert [(record.levelno, record.getMessage()) for record in delivered_records(caplog, _LOGGER_NAME)] == [
        (logging.WARNING, "agent startup refused reason=launch_failed agent_code=None")
    ]
