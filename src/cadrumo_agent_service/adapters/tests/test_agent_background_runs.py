"""Background requests the adapter refuses before it reaches any gateway, and how it reads the agent's refusals."""

from __future__ import annotations

import base64
import json
import threading
from collections.abc import Generator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import override

import pytest
from pydantic import JsonValue, ValidationError

from cadrumo_client.contracts.model_runs import (
    ModelRunAttachment,
    ModelRunBody,
    ModelRunLane,
    ModelRunRefusal,
    ModelRunRefusalCode,
)

from ..agent_background_runs import (
    RUN_START_SECONDS,
    BackgroundRunEndpoint,
    HostedBackgroundRuns,
    settled_reply_outcome,
    start_refusal,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_LANE = ModelRunLane(
    provider_id="example",
    transport="api",
    model="example-model-1",
    reads_off_host=True,
)


def _unreachable(tmp_path: Path) -> BackgroundRunEndpoint:
    """An endpoint nothing listens on: any exchange would fail rather than be answered."""
    return BackgroundRunEndpoint(port=1, workspace_root=tmp_path)


def _body(*attachments: ModelRunAttachment) -> ModelRunBody:
    return ModelRunBody(prompt="Read this.", attachments=attachments, max_output_tokens=16)


def test_a_format_no_background_request_carries_is_refused_as_unsupported(tmp_path: Path) -> None:
    endpoint = _unreachable(tmp_path)
    runs = HostedBackgroundRuns(
        endpoint=lambda: endpoint, bearer=bytearray(b"synthetic-bearer"), host_token=bytearray(b"synthetic-host")
    )
    text = ModelRunAttachment(media_type="text/plain", base64_data=base64.b64encode(b"x").decode())

    assert runs.run(lane=_LANE, body=_body(text), deadline_seconds=30, options=()) == ModelRunRefusal(
        code=ModelRunRefusalCode.INPUT_NOT_SUPPORTED
    )


def test_a_wiped_host_token_or_no_ready_agent_refuses_as_unavailable(tmp_path: Path) -> None:
    endpoint = _unreachable(tmp_path)
    wiped = HostedBackgroundRuns(
        endpoint=lambda: endpoint, bearer=bytearray(b"synthetic-bearer"), host_token=bytearray()
    )
    absent = HostedBackgroundRuns(
        endpoint=lambda: None, bearer=bytearray(b"synthetic-bearer"), host_token=bytearray(b"synthetic-host")
    )

    for runs in (wiped, absent):
        assert runs.run(lane=_LANE, body=_body(), deadline_seconds=30, options=()) == ModelRunRefusal(
            code=ModelRunRefusalCode.SERVICE_UNAVAILABLE
        )


@pytest.mark.parametrize(
    "options",
    [
        pytest.param({"context_tokens": 511}, id="context-below-floor"),
        pytest.param({"context_tokens": 1_048_577}, id="context-above-ceiling"),
        pytest.param({"response_schema": {"description": "x" * 32_768}}, id="schema-over-bound"),
    ],
)
def test_a_reply_option_outside_the_agent_s_bounds_is_refused_by_the_contract(options: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ModelRunBody.model_validate({"prompt": "Read this.", "max_output_tokens": 16, **options})


def test_reply_options_at_the_agent_s_bounds_are_accepted() -> None:
    schema: dict[str, JsonValue] = {"description": "x" * (32_768 - len('{"description":""}'))}
    body = ModelRunBody(
        prompt="Read this.", max_output_tokens=16, context_tokens=512, response_schema=schema, temperature=0.0
    )

    assert (body.context_tokens, body.response_schema) == (512, schema)


def _selection_refusal(code: str) -> bytes:
    """The 422 body cadrumo-agent's run start answers a refused selection with."""
    return json.dumps({"detail": {"code": code, "message": "synthetic refusal", "offered": []}}).encode()


@pytest.mark.parametrize(
    ("status", "payload", "expected"),
    [
        pytest.param(
            422,
            _selection_refusal("provider_not_executable"),
            ModelRunRefusalCode.LANE_UNAVAILABLE,
            id="not-executable",
        ),
        pytest.param(
            422, _selection_refusal("unknown_provider"), ModelRunRefusalCode.LANE_UNAVAILABLE, id="unknown-provider"
        ),
        pytest.param(
            422,
            _selection_refusal("provider_not_selectable"),
            ModelRunRefusalCode.LANE_UNAVAILABLE,
            id="not-selectable",
        ),
        pytest.param(
            422, _selection_refusal("model_not_installed"), ModelRunRefusalCode.MODEL_NOT_INSTALLED, id="not-installed"
        ),
        pytest.param(
            422, _selection_refusal("model_does_not_fit"), ModelRunRefusalCode.MODEL_DOES_NOT_FIT, id="does-not-fit"
        ),
        pytest.param(
            403,
            _selection_refusal("background_not_admitted"),
            ModelRunRefusalCode.SERVICE_UNAVAILABLE,
            id="not-admitted",
        ),
        pytest.param(
            503,
            json.dumps({"detail": "gateway is draining"}).encode(),
            ModelRunRefusalCode.SERVICE_UNAVAILABLE,
            id="busy-agent",
        ),
        pytest.param(
            503, b"service unavailable", ModelRunRefusalCode.SERVICE_UNAVAILABLE, id="busy-agent-without-json"
        ),
        pytest.param(
            422, _selection_refusal("model_without_tools"), ModelRunRefusalCode.RUN_FAILED, id="unmapped-code"
        ),
        pytest.param(
            409,
            json.dumps({"detail": "predecessor run is not settled"}).encode(),
            ModelRunRefusalCode.RUN_FAILED,
            id="uncoded-conflict",
        ),
    ],
)
def test_a_run_start_the_agent_refuses_reads_as_its_closed_refusal(
    status: int, payload: bytes, expected: ModelRunRefusalCode
) -> None:
    assert start_refusal(status, payload) is expected


_AGENT_LOAD_BOUND_SECONDS = 60.0
"""cadrumo-agent's bound on loading a local model before it answers a run start."""


def test_a_run_start_waits_past_the_agent_s_model_load_bound() -> None:
    assert RUN_START_SECONDS > _AGENT_LOAD_BOUND_SECONDS


@contextmanager
def _run_start_recorded(tmp_path: Path) -> Generator[tuple[BackgroundRunEndpoint, list[dict[str, object]]]]:
    """Serve a loopback gateway that records each run-start request and refuses it as not installed.

    The refusal ends the run at its start, so the only request on the wire is
    the one under test and nothing needs cleaning up afterwards.
    """
    received: list[dict[str, object]] = []

    class _Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            received.append(json.loads(self.rfile.read(length)))
            payload = _selection_refusal("model_not_installed")
            self.send_response(422)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        @override
        def log_message(self, format: str, *args: object) -> None:
            del format, args

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield BackgroundRunEndpoint(port=server.server_address[1], workspace_root=tmp_path), received
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def _start_one(endpoint: BackgroundRunEndpoint, body: ModelRunBody) -> None:
    runs = HostedBackgroundRuns(
        endpoint=lambda: endpoint, bearer=bytearray(b"synthetic-bearer"), host_token=bytearray(b"synthetic-host")
    )
    outcome = runs.run(lane=_LANE, body=body, deadline_seconds=30, options=())
    assert outcome == ModelRunRefusal(code=ModelRunRefusalCode.MODEL_NOT_INSTALLED)


def test_a_run_that_states_no_reply_bound_sends_none_to_the_agent(tmp_path: Path) -> None:
    with _run_start_recorded(tmp_path) as (endpoint, received):
        _start_one(endpoint, ModelRunBody(prompt="Read this."))

    assert len(received) == 1
    assert received[0]["background"] == {"system": "", "deadline_seconds": 30}


def test_a_stated_reply_bound_reaches_the_agent_unchanged(tmp_path: Path) -> None:
    with _run_start_recorded(tmp_path) as (endpoint, received):
        _start_one(endpoint, ModelRunBody(prompt="Read this.", max_output_tokens=16))

    assert len(received) == 1
    assert received[0]["background"] == {"system": "", "max_output_tokens": 16, "deadline_seconds": 30}


def _reply(**fields: object) -> bytes:
    """A reply read shaped as cadrumo-agent's ``GET /v1/runs/{run_id}/reply`` answers it."""
    document: dict[str, object] = {
        "run_id": "run-1",
        "status": "failed",
        "settled": True,
        "background_request": True,
        "reply": None,
        "failure_reason": "provider_error",
        "provider_condition": None,
        "provider": "local",
        "transport": "api",
        "model": "example-model-1",
        "agent_version": "0.0.0",
    }
    document.update(fields)
    return json.dumps(document).encode()


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        pytest.param(
            _reply(provider_condition="model_does_not_fit"),
            ModelRunRefusal(code=ModelRunRefusalCode.MODEL_DOES_NOT_FIT),
            id="does-not-fit-mid-turn",
        ),
        pytest.param(
            _reply(provider_condition="provider_unavailable"),
            ModelRunRefusal(code=ModelRunRefusalCode.RUN_FAILED),
            id="other-failed-load",
        ),
        pytest.param(_reply(), ModelRunRefusal(code=ModelRunRefusalCode.RUN_FAILED), id="failed-without-condition"),
        pytest.param(
            _reply(failure_reason="output_limit_exceeded: 16"),
            ModelRunRefusal(code=ModelRunRefusalCode.OUTPUT_INVALID),
            id="output-limit",
        ),
        pytest.param(b"not json", ModelRunRefusal(code=ModelRunRefusalCode.RUN_FAILED), id="outside-the-contract"),
        pytest.param(_reply(status="running", settled=False), None, id="not-settled"),
    ],
)
def test_a_settled_reply_reads_as_its_outcome(payload: bytes, expected: ModelRunRefusal | None) -> None:
    assert settled_reply_outcome(payload, _LANE) == expected


def test_a_completed_reply_ignores_a_stale_provider_condition() -> None:
    outcome = settled_reply_outcome(
        _reply(status="completed", reply="read", failure_reason=None, provider_condition="model_does_not_fit"), _LANE
    )

    assert not isinstance(outcome, ModelRunRefusal)
    assert outcome is not None
    assert outcome.text == "read"
