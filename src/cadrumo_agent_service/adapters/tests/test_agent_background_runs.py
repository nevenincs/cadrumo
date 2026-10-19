"""The background-request exchange, against a loopback gateway that answers in the agent's published shapes.

The gateway here is a stand-in for cadrumo-agent's: it records what the
adapter sends and answers as the agent's committed request, reply and refusal
shapes say. It proves the adapter's side of that contract, not the agent's.
"""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any, override
from urllib.parse import parse_qs, urlsplit

import pytest

from cadrumo_client.contracts.model_runs import (
    ModelRunAttachment,
    ModelRunBody,
    ModelRunLane,
    ModelRunMediaKind,
    ModelRunOutput,
    ModelRunRefusal,
    ModelRunRefusalCode,
)

from ..agent_background_runs import HOST_ADMISSION_HEADER, BackgroundRunEndpoint, HostedBackgroundRuns

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BEARER = b"synthetic-gateway-bearer-NOT-REAL"
_HOST_TOKEN = b"synthetic-host-token-NOT-REAL"
_LANE = ModelRunLane(provider_id="example", transport="api", model="example-model-1")
_PNG = b"\x89PNG\r\n\x1a\nsynthetic"


@dataclass
class _Gateway:
    start_status: int = 201
    start_detail: dict[str, Any] | None = None
    reply: dict[str, Any] = field(
        default_factory=lambda: {
            "status": "completed",
            "settled": True,
            "background_request": True,
            "reply": '{"total": "12.00"}',
            "failure_reason": None,
            "provider": "example",
            "transport": "api",
            "model": "example-model-1",
            "agent_version": "9.9.9",
        }
    )
    catalog: list[dict[str, Any]] = field(default_factory=list)
    requests: list[tuple[str, str, dict[str, str], bytes]] = field(default_factory=list)


def _handler(gateway: _Gateway) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def _record(self) -> bytes:
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b""
            gateway.requests.append((self.command, self.path, dict(self.headers.items()), body))
            return body

        def _answer(self, status: int, document: object | None = None) -> None:
            payload = b"" if document is None else json.dumps(document).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_PUT(self) -> None:
            self._record()
            self._answer(201, {"name": self.path.rsplit("/", 1)[-1]})

        def do_POST(self) -> None:
            self._record()
            if gateway.start_status == 201:
                self._answer(201, {"run_id": "accepted"})
            else:
                self._answer(gateway.start_status, {"detail": gateway.start_detail})

        def do_GET(self) -> None:
            self._record()
            if self.path.startswith("/v1/provider-catalog"):
                self._answer(200, {"api_version": "v1", "providers": gateway.catalog})
            else:
                self._answer(200, {"api_version": "v1", "run_id": "r", **gateway.reply})

        def do_DELETE(self) -> None:
            self._record()
            self._answer(204)

        @override
        def log_message(self, format: str, *args: Any) -> None:
            del format, args

    return Handler


@pytest.fixture
def gateway(tmp_path: Path) -> Iterator[tuple[_Gateway, HostedBackgroundRuns]]:
    state = _Gateway()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(state))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = BackgroundRunEndpoint(port=server.server_address[1], workspace_root=tmp_path)
    runs = HostedBackgroundRuns(endpoint=lambda: endpoint, bearer=bytearray(_BEARER), host_token=bytearray(_HOST_TOKEN))
    try:
        yield state, runs
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def _body(*attachments: ModelRunAttachment) -> ModelRunBody:
    return ModelRunBody(system="Answer in JSON.", prompt="Read this.", attachments=attachments, max_output_tokens=256)


def test_a_run_uploads_starts_reads_and_cleans_up_in_the_published_shapes(
    gateway: tuple[_Gateway, HostedBackgroundRuns], tmp_path: Path
) -> None:
    state, runs = gateway
    image = ModelRunAttachment(media_type="image/png", base64_data=base64.b64encode(_PNG).decode())

    output = runs.run(lane=_LANE, body=_body(image), deadline_seconds=1)

    assert output == ModelRunOutput(
        text='{"total": "12.00"}',
        provider_id="example",
        transport="api",
        model="example-model-1",
        agent_version="9.9.9",
    )
    methods = [(method, urlsplit(path).path) for method, path, _, _ in state.requests]
    upload, start, reply, _, _ = state.requests
    run_id = json.loads(start[3])["run_id"]
    assert methods == [
        ("PUT", f"/v1/conversations/{run_id}/attachments/input-1.png"),
        ("POST", "/v1/runs"),
        ("GET", f"/v1/runs/{run_id}/reply"),
        ("DELETE", f"/v1/runs/{run_id}"),
        ("DELETE", f"/v1/conversations/{run_id}/attachments"),
    ]
    assert upload[3] == _PNG
    assert upload[2]["X-Content-SHA256"] == hashlib.sha256(_PNG).hexdigest()
    assert json.loads(start[3]) == {
        "run_id": run_id,
        "message": "Read this.",
        "agent": {
            "provider": "example",
            "transport": "api",
            "model": "example-model-1",
            "workspace_root": str(tmp_path),
        },
        "background": {"system": "Answer in JSON.", "max_output_tokens": 256, "deadline_seconds": 5},
        "attachments": [{"name": "input-1.png", "sha256": hashlib.sha256(_PNG).hexdigest()}],
    }
    assert int(parse_qs(urlsplit(reply[1]).query)["wait_seconds"][0]) >= 1
    for _, path, headers, _ in state.requests:
        assert headers["Authorization"] == "Bearer " + _BEARER.decode()
        assert (HOST_ADMISSION_HEADER in headers) == (path == "/v1/runs")
    assert start[2][HOST_ADMISSION_HEADER] == _HOST_TOKEN.decode()


@pytest.mark.parametrize(
    ("status", "code", "expected"),
    (
        (403, "background_not_admitted", ModelRunRefusalCode.SERVICE_UNAVAILABLE),
        (422, "background_request_invalid", ModelRunRefusalCode.RUN_FAILED),
        (422, "background_lane_unsupported", ModelRunRefusalCode.LANE_UNAVAILABLE),
        (422, "input_not_supported", ModelRunRefusalCode.INPUT_NOT_SUPPORTED),
        (422, "a_code_this_service_does_not_know", ModelRunRefusalCode.RUN_FAILED),
    ),
)
def test_each_admission_refusal_maps_into_the_closed_set_and_no_run_is_deleted(
    gateway: tuple[_Gateway, HostedBackgroundRuns], status: int, code: str, expected: ModelRunRefusalCode
) -> None:
    state, runs = gateway
    state.start_status = status
    state.start_detail = {"code": code, "message": "refused"}

    assert runs.run(lane=_LANE, body=_body(), deadline_seconds=30) == ModelRunRefusal(code=expected)
    assert [method for method, _, _, _ in state.requests] == ["POST"]


def test_a_reply_over_its_limit_is_refused_as_invalid_output(gateway: tuple[_Gateway, HostedBackgroundRuns]) -> None:
    state, runs = gateway
    state.reply.update(status="failed", reply=None, failure_reason="output_limit_exceeded: the reply used 300 tokens")

    refused = runs.run(lane=_LANE, body=_body(), deadline_seconds=30)

    assert refused == ModelRunRefusal(code=ModelRunRefusalCode.OUTPUT_INVALID)
    assert [method for method, _, _, _ in state.requests][-1] == "DELETE"


def test_a_failed_run_is_refused_as_failed(gateway: tuple[_Gateway, HostedBackgroundRuns]) -> None:
    state, runs = gateway
    state.reply.update(status="failed", reply=None, failure_reason="provider_error")

    assert runs.run(lane=_LANE, body=_body(), deadline_seconds=30) == ModelRunRefusal(
        code=ModelRunRefusalCode.RUN_FAILED
    )


def test_a_format_no_background_request_carries_is_refused_before_anything_is_sent(
    gateway: tuple[_Gateway, HostedBackgroundRuns],
) -> None:
    state, runs = gateway
    text = ModelRunAttachment(media_type="text/plain", base64_data=base64.b64encode(b"x").decode())

    refused = runs.run(lane=_LANE, body=_body(text), deadline_seconds=30)

    assert refused == ModelRunRefusal(code=ModelRunRefusalCode.INPUT_NOT_SUPPORTED)
    assert state.requests == []


def test_accepted_media_is_read_from_the_lane_s_background_requests_record(
    gateway: tuple[_Gateway, HostedBackgroundRuns],
) -> None:
    state, runs = gateway
    support = {"text": "proven", "image": "proven", "pdf": "unsupported"}
    state.catalog = [
        {"provider_id": "other", "transport": "api", "background_requests": {**support, "accepts_images": False}},
        {
            "provider_id": "example",
            "transport": "api",
            "background_requests": {**support, "accepts_images": True, "accepts_pdfs": False},
        },
    ]

    assert runs.accepted_media(_LANE) == (ModelRunMediaKind.IMAGE,)
    assert runs.accepted_media(_LANE.model_copy(update={"transport": "cli"})) is None


def test_a_wiped_host_token_refuses_every_run_as_unavailable(tmp_path: Path) -> None:
    endpoint = BackgroundRunEndpoint(port=1, workspace_root=tmp_path)
    runs = HostedBackgroundRuns(endpoint=lambda: endpoint, bearer=bytearray(_BEARER), host_token=bytearray())

    assert runs.run(lane=_LANE, body=_body(), deadline_seconds=30) == ModelRunRefusal(
        code=ModelRunRefusalCode.SERVICE_UNAVAILABLE
    )
