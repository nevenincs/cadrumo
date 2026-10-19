"""Background requests against a real cadrumo-agent gateway, with no provider reachable.

The gateway runs from the cadrumo-agent checkout ``CADRUMO_DEV_AGENT_CHECKOUT``
names, non-hosted, in a disposable home and a disposable user profile, inside
the service's own kill-on-close job. No provider credential reaches it and the
profile holds no provider sign-in, so a run it admits fails at the provider's
authentication instead of making a provider call. A completed reply is proven
through the hosted service on a signed-in profile, not here.
"""

from __future__ import annotations

import base64
import json
import os
import secrets
import socket
from collections.abc import Iterator
from dataclasses import dataclass
from http.client import HTTPConnection
from pathlib import Path
from typing import Final
from urllib.parse import urlencode

import pytest

from cadrumo_client.contracts.model_runs import (
    ModelRunAttachment,
    ModelRunBody,
    ModelRunLane,
    ModelRunMediaKind,
    ModelRunRefusal,
    ModelRunRefusalCode,
)

from ...host.controller import AgentProcess
from ...host.launch_environment import system_environment
from ..agent_background_runs import HOST_ADMISSION_HEADER, BackgroundRunEndpoint, HostedBackgroundRuns
from ..agent_process import WindowsAgentProcessLauncher

pytestmark = [
    pytest.mark.integration,
    pytest.mark.external_tool,
    pytest.mark.windows_only,
    pytest.mark.hex_outbound_adapter,
]

CHECKOUT_VARIABLE: Final = "CADRUMO_DEV_AGENT_CHECKOUT"
_READY_BOUND_SECONDS: Final = 120.0
_EXIT_OBSERVATION_SECONDS: Final = 0.25
_TOOL_LESS_LANE: Final = ModelRunLane(provider_id="claude", transport="cli", model="haiku")
_TOOLED_ONLY_LANE: Final = ModelRunLane(provider_id="kimi", transport="cli", model="kimi-for-coding")
_PNG: Final = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
_PDF: Final = b"\n".join(
    (
        b"%PDF-1.4",
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 10 10]>>endobj",
        b"trailer<</Root 1 0 R>>",
        b"%%EOF",
        b"",
    )
)


@dataclass(frozen=True)
class _Gateway:
    endpoint: BackgroundRunEndpoint
    bearer: str
    host_token: str

    def runs(self, *, host_token: str | None = None, run_id: str | None = None) -> HostedBackgroundRuns:
        """The adapter under test, bound to this gateway."""
        return HostedBackgroundRuns(
            endpoint=lambda: self.endpoint,
            bearer=bytearray(self.bearer, "ascii"),
            host_token=bytearray(self.host_token if host_token is None else host_token, "ascii"),
            run_ids=(lambda: secrets.token_hex(16)) if run_id is None else (lambda: run_id),
        )

    def exchange(
        self, method: str, path: str, *, body: bytes | None = None, host_token: bool = False
    ) -> tuple[int, object]:
        """One raw request as a client of the gateway, returning its status and decoded body."""
        headers = {"Authorization": f"Bearer {self.bearer}", "Content-Type": "application/json"}
        if host_token:
            headers[HOST_ADMISSION_HEADER] = self.host_token
        connection = HTTPConnection("127.0.0.1", self.endpoint.port, timeout=60)
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            payload = response.read()
        finally:
            connection.close()
        return response.status, (json.loads(payload) if payload else None)

    def background(self, run_id: str, lane: ModelRunLane, **extra: object) -> tuple[int, object]:
        request = {
            "run_id": run_id,
            "message": "Answer with an empty JSON object.",
            "agent": {
                "provider": lane.provider_id,
                "transport": lane.transport,
                "model": lane.model,
                "workspace_root": str(self.endpoint.workspace_root),
            },
            "background": {"system": "", "max_output_tokens": 16, "deadline_seconds": 30},
            **extra,
        }
        return self.exchange("POST", "/v1/runs", body=json.dumps(request).encode(), host_token=True)


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _answers_health(port: int) -> bool:
    connection = HTTPConnection("127.0.0.1", port, timeout=2)
    try:
        connection.request("GET", "/health")
        return connection.getresponse().status == 200
    except OSError:
        return False
    finally:
        connection.close()


def _agent_checkout() -> Path:
    named = os.environ.get(CHECKOUT_VARIABLE)
    if named is None or not named.strip():
        pytest.fail(f"{CHECKOUT_VARIABLE} must name a cadrumo-agent checkout at 3b6c85b or later", pytrace=False)
    checkout = Path(named)
    program = checkout / ".venv" / "Scripts" / "cadrumo-agent.exe"
    if not checkout.is_absolute() or not program.is_file():
        pytest.fail(f"{CHECKOUT_VARIABLE} names no synced cadrumo-agent checkout: {program} is absent", pytrace=False)
    return checkout


def _await_ready(process: AgentProcess, port: int) -> None:
    """Return once the gateway answers its health route; fail at once if the tree exits first."""
    for _ in range(int(_READY_BOUND_SECONDS / _EXIT_OBSERVATION_SECONDS)):
        if _answers_health(port):
            return
        status = process.wait(timeout=_EXIT_OBSERVATION_SECONDS)
        if status is not None:
            pytest.fail(f"the agent gateway exited with status {status} before it was ready", pytrace=False)
    pytest.fail("the agent gateway never answered its health route", pytrace=False)


@pytest.fixture(scope="module")
def gateway(tmp_path_factory: pytest.TempPathFactory) -> Iterator[_Gateway]:
    checkout = _agent_checkout()
    root = tmp_path_factory.mktemp("agent-gateway")
    profile = root / "profile"
    for directory in (profile / "AppData" / "Roaming", profile / "AppData" / "Local", root / "workspace"):
        directory.mkdir(parents=True)
    bearer, host_token = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    port = _free_port()
    environment = system_environment(os.environ) | {
        "USERPROFILE": str(profile),
        "HOME": str(profile),
        "APPDATA": str(profile / "AppData" / "Roaming"),
        "LOCALAPPDATA": str(profile / "AppData" / "Local"),
        "CADRUMO_AGENT_ENVIRONMENT": "production",
        "CADRUMO_AGENT_PORT": str(port),
        "CADRUMO_AGENT_WORKER_PORT": str(_free_port()),
        "CADRUMO_AGENT_AUTO_SPAWN_WORKER": "true",
        "CADRUMO_AGENT_HOME": str(root / "home"),
        "CADRUMO_AGENT_WORKSPACE_ROOT": str(root / "workspace"),
        "CADRUMO_AGENT_DATABASE_BACKEND": "sqlite",
        "CADRUMO_AGENT_DATABASE_URL": f"sqlite+aiosqlite:///{(root / 'agent.db').as_posix()}",
        "CADRUMO_AGENT_CHECKPOINT_BACKEND": "sqlite",
        "CADRUMO_AGENT_CHECKPOINT_DATABASE_URL": f"sqlite+aiosqlite:///{(root / 'checkpoint.db').as_posix()}",
        "CADRUMO_AGENT_GATEWAY_TOKEN": bearer,
        "CADRUMO_AGENT_INTERNAL_TOKEN": secrets.token_urlsafe(32),
        "CADRUMO_AGENT_HOST_TOKEN": host_token,
    }
    process = WindowsAgentProcessLauncher().launch(
        executable=checkout / ".venv" / "Scripts" / "cadrumo-agent.exe",
        arguments=("serve",),
        directory=checkout,
        environment=environment,
    )
    try:
        _await_ready(process, port)
        yield _Gateway(BackgroundRunEndpoint(port=port, workspace_root=root / "workspace"), bearer, host_token)
    finally:
        # Ends every member of the job, the workers the gateway spawned too, and
        # raises unless the job is verified empty within the bound.
        process.terminate(timeout=30)


def _body(*attachments: tuple[str, bytes]) -> ModelRunBody:
    return ModelRunBody(
        prompt="Answer with an empty JSON object.",
        attachments=tuple(
            ModelRunAttachment(media_type=media_type, base64_data=base64.b64encode(data).decode())
            for media_type, data in attachments
        ),
        max_output_tokens=16,
    )


def _refusal_code(answer: object) -> object:
    return answer.get("detail", {}).get("code") if isinstance(answer, dict) else None


def test_without_the_host_s_own_token_the_agent_refuses_and_the_run_is_unavailable(gateway: _Gateway) -> None:
    run_id = secrets.token_hex(16)
    status, answer = gateway.exchange(
        "POST",
        "/v1/runs",
        body=json.dumps(
            {
                "run_id": run_id,
                "message": "x",
                "agent": {
                    "provider": "claude",
                    "transport": "cli",
                    "model": "haiku",
                    "workspace_root": str(gateway.endpoint.workspace_root),
                },
                "background": {},
            }
        ).encode(),
    )
    assert (status, _refusal_code(answer)) == (403, "background_not_admitted")

    runs = gateway.runs(host_token=secrets.token_urlsafe(32), run_id=run_id)
    assert runs.run(lane=_TOOL_LESS_LANE, body=_body(), deadline_seconds=30) == ModelRunRefusal(
        code=ModelRunRefusalCode.SERVICE_UNAVAILABLE
    )
    assert gateway.exchange("GET", f"/v1/runs/{run_id}/reply")[0] == 404


def test_a_lane_that_cannot_run_without_tools_is_refused_as_unavailable(gateway: _Gateway) -> None:
    run_id = secrets.token_hex(16)
    status, answer = gateway.background(run_id, _TOOLED_ONLY_LANE)
    assert (status, _refusal_code(answer)) == (422, "background_lane_unsupported")

    assert gateway.runs().run(lane=_TOOLED_ONLY_LANE, body=_body(), deadline_seconds=30) == ModelRunRefusal(
        code=ModelRunRefusalCode.LANE_UNAVAILABLE
    )


def test_a_pdf_on_a_lane_that_takes_none_is_refused_and_its_upload_removed(gateway: _Gateway) -> None:
    run_id = secrets.token_hex(16)

    refused = gateway.runs(run_id=run_id).run(
        lane=_TOOL_LESS_LANE, body=_body(("application/pdf", _PDF)), deadline_seconds=30
    )

    assert refused == ModelRunRefusal(code=ModelRunRefusalCode.INPUT_NOT_SUPPORTED)
    assert gateway.runs().accepted_media(_TOOL_LESS_LANE) == (ModelRunMediaKind.IMAGE,)
    status, listed = gateway.exchange("GET", f"/v1/conversations/{run_id}/attachments")
    assert status == 404 or (isinstance(listed, dict) and not listed.get("attachments"))


def test_a_background_request_that_continues_a_run_is_refused_as_invalid(gateway: _Gateway) -> None:
    status, answer = gateway.background(secrets.token_hex(16), _TOOL_LESS_LANE, continues_run_id=secrets.token_hex(16))

    assert (status, _refusal_code(answer)) == (422, "background_request_invalid")


def test_an_admitted_run_is_hidden_from_the_run_listing_and_settles_without_a_provider(gateway: _Gateway) -> None:
    run_id = secrets.token_hex(16)
    status, started = gateway.background(run_id, _TOOL_LESS_LANE)
    assert status == 201, started
    try:
        listed = gateway.exchange("GET", "/v1/runs")[1]
        assert isinstance(listed, dict)
        assert run_id not in {run.get("run_id") for run in listed["runs"]}
        status, reply = gateway.exchange("GET", f"/v1/runs/{run_id}/reply?" + urlencode({"wait_seconds": 120}))
        assert status == 200 and isinstance(reply, dict)
        assert (reply["settled"], reply["background_request"], reply["status"], reply["reply"]) == (
            True,
            True,
            "failed",
            None,
        )
    finally:
        assert gateway.exchange("DELETE", f"/v1/runs/{run_id}")[0] in {200, 204}


def test_a_run_uploads_starts_reads_its_reply_and_deletes_what_it_left(gateway: _Gateway) -> None:
    run_id = secrets.token_hex(16)

    outcome = gateway.runs(run_id=run_id).run(
        lane=_TOOL_LESS_LANE, body=_body(("image/png", _PNG)), deadline_seconds=60
    )

    # The disposable profile holds no provider sign-in, so the admitted run fails at the provider.
    assert outcome == ModelRunRefusal(code=ModelRunRefusalCode.RUN_FAILED)
    assert gateway.exchange("GET", f"/v1/runs/{run_id}/reply")[0] == 404
    status, listed = gateway.exchange("GET", f"/v1/conversations/{run_id}/attachments")
    assert status == 404 or (isinstance(listed, dict) and not listed.get("attachments"))
