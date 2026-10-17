"""A refused session hold answers with its root cause on the refusal line itself."""

from __future__ import annotations

import json
import logging
from uuid import uuid4

import pytest

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_runtime.host import session_hold

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _refuse_untrusted_peer() -> None:
    raise RefusalError(RefusalCode.PEER_UNTRUSTED, check="desktop_holder_descriptor_absent")


def test_refused_hold_logs_and_answers_with_the_refusal_report(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    async def open_client(*, profile_id: object, frontend: OperationFrontendProjection) -> object:
        _refuse_untrusted_peer()
        raise AssertionError("unreachable")

    monkeypatch.setattr(session_hold, "open_installed_client", open_client)
    with caplog.at_level(logging.DEBUG):
        assert session_hold.main(["--profile-id", str(uuid4())]) == 1
    captured = capsys.readouterr()

    (answer,) = [json.loads(line) for line in captured.out.splitlines()]
    assert set(answer) == {"kind", "request_id", "code", "report"}
    assert answer["kind"] == "session_refused" and answer["code"] == "unavailable"

    (document,) = [json.loads(line) for line in captured.err.splitlines() if line.startswith("{")]
    error = document["error"]
    # The parent reads the same cause with the refusal, without the message or a second pipe.
    assert "message" in error
    assert answer["report"] == {**document, "error": {k: v for k, v in error.items() if k != "message"}}
    assert document["command"] == "session.hold" and document["status"] == "error"
    assert error["context"]["reason"] == RefusalCode.PEER_UNTRUSTED.value
    assert error["context"]["exception_type"] == "cadrumo_client.contracts.contracts.RefusalError"
    assert error["context"]["raised_at"].startswith(
        "cadrumo_runtime.host.tests.test_session_hold_failure_report:_refuse_untrusted_peer:"
    )
    assert "desktop_holder_descriptor_absent" not in captured.err

    (record,) = [record for record in caplog.records if getattr(record, "failure_boundary", None) == "session_hold"]
    assert record.__dict__["trace_id"] == error["trace_id"] == error["context"]["trace_id"]
    assert record.__dict__["reason"] == "desktop_holder_descriptor_absent"
    assert record.__dict__["error_code"] == error["code"]


def test_unexpected_hold_failure_reports_its_type_and_frame(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    async def open_client(*, profile_id: object, frontend: OperationFrontendProjection) -> object:
        raise KeyError("private-profile-label")

    monkeypatch.setattr(session_hold, "open_installed_client", open_client)
    assert session_hold.main(["--profile-id", str(uuid4())]) == 1
    captured = capsys.readouterr()

    (document,) = [json.loads(line) for line in captured.err.splitlines() if line.startswith("{")]
    (answer,) = [json.loads(line) for line in captured.out.splitlines()]
    assert answer["report"]["error"]["context"] == document["error"]["context"]
    assert document["error"]["code"] == "INTERNAL_CLI_UNEXPECTED_BOUNDARY"
    assert document["error"]["context"]["exception_type"] == "KeyError"
    assert document["error"]["context"]["raised_at"].endswith(":open_client:" + str(_line_of_key_error()))
    assert "private-profile-label" not in captured.err + captured.out


def _line_of_key_error() -> int:
    import inspect

    source, start = inspect.getsourcelines(test_unexpected_hold_failure_reports_its_type_and_frame)
    return start + next(index for index, line in enumerate(source) if 'raise KeyError("private-profile-label")' in line)
