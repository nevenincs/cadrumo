"""A failing runtime command shows and logs its real root cause under one correlation id."""

from __future__ import annotations

import json
import logging
from contextvars import Context
from typing import cast, override
from uuid import uuid4

import pytest

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.login_session_port import profile_login_session_port
from cadrumo.core.bucket_pointer import BucketPointer
from cadrumo_client.contracts.profile_access import ProfileStatus
from cadrumo_client.transport import installed_client
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_runtime.commands import activity, presentation

from .runtime_cli import invoke_runtime_cli

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_INVARIANT_TYPE = "cadrumo.core.errors.hierarchy.InternalInvariantError"
_ACCESSOR_FRAME = "cadrumo.application.user_profile.login_session_port:profile_login_session_port:"


class _UncomposedClient(FrontendClient):
    """Resumes through the real login-session accessor in a context that never composed it."""

    def __init__(self) -> None:
        self._profile_id = uuid4()

    @override
    def resume_receipt(self, *, timeout: float = 5) -> ProfileStatus:
        Context().run(profile_login_session_port)
        return cast(ProfileStatus, object())

    @override
    def close(self) -> None:
        return None


def _invoke(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    client = _UncomposedClient()
    pointer = BucketPointer.selected(bucket_id=str(client.profile_id), transition_revision=1)
    monkeypatch.setattr(activity, "observe_active_profile_pointer", lambda: pointer)

    async def open_client(*, profile_id: object, frontend: OperationFrontendProjection) -> FrontendClient:
        assert profile_id == client.profile_id and frontend is OperationFrontendProjection.CLI
        return client

    monkeypatch.setattr(installed_client, "open_installed_client", open_client)
    result = invoke_runtime_cli(("--format", "json", "config", "activity"))
    assert result.exit_code == 6, result.output
    document = json.loads(result.output.strip().splitlines()[-1])
    assert isinstance(document, dict)
    return cast(dict[str, object], document["error"])


def _boundary_records(caplog: pytest.LogCaptureFixture, boundary: str) -> list[logging.LogRecord]:
    return [record for record in caplog.records if getattr(record, "failure_boundary", None) == boundary]


def test_internal_failure_names_its_root_cause_on_the_console_and_in_the_log(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG):
        error = _invoke(monkeypatch)

    assert error["code"] == "INTERNAL_INVARIANT"
    context = cast(dict[str, str], error["context"])
    # The unset context variable is the root; the invariant names what it means.
    assert context["exception_type"] == "LookupError"
    assert context["raised_at"].startswith(_ACCESSOR_FRAME)
    assert context["cause_chain"] == "InternalInvariantError <- LookupError"
    (record,) = _boundary_records(caplog, "runtime_cli")
    assert record.levelno == logging.ERROR
    assert record.__dict__["trace_id"] == error["trace_id"] == context["trace_id"]
    assert record.__dict__["error_code"] == "INTERNAL_INVARIANT"
    assert record.__dict__["error_type"] == _INVARIANT_TYPE
    assert str(record.__dict__["error_origin"]).startswith(_ACCESSOR_FRAME)
    assert str(record.__dict__["root_cause"]).startswith("LookupError@" + _ACCESSOR_FRAME)
    assert record.__dict__["invariant"] == "profile login-session infrastructure has not been composed"


def test_failing_error_context_capture_never_replaces_the_original_error(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def broken_language() -> str:
        raise RuntimeError("enrichment failed")

    monkeypatch.setattr(presentation, "output_language", broken_language)
    with caplog.at_level(logging.DEBUG):
        error = _invoke(monkeypatch)

    assert error["code"] == "INTERNAL_INVARIANT"
    assert cast(dict[str, str], error["context"])["raised_at"].startswith(_ACCESSOR_FRAME)
    (enrichment,) = _boundary_records(caplog, "runtime_error_context_capture")
    assert enrichment.__dict__["error_type"] == "RuntimeError"
    assert str(enrichment.__dict__["error_origin"]).endswith(":broken_language:" + str(_line_of_raise()))


def _line_of_raise() -> int:
    import inspect

    source, start = inspect.getsourcelines(test_failing_error_context_capture_never_replaces_the_original_error)
    return start + next(index for index, line in enumerate(source) if 'raise RuntimeError("enrichment failed")' in line)
