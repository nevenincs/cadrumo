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
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Final
from urllib.parse import urlencode

import pytest
from pydantic import TypeAdapter

from cadrumo.tests.audited_process import run_audited_process
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
_ENVIRONMENT_NAMES_PROBE: Final = """
import json, sys
from cadrumo_agent.control.config import Settings
from cadrumo_agent.control.settings_base import env_name
print(json.dumps({field: env_name(Settings, field) for field in json.loads(sys.argv[1])}))
"""
_ENVIRONMENT_NAMES: Final = TypeAdapter(dict[str, str])
_TOOL_LESS_LANE: Final = ModelRunLane(provider_id="claude", transport="cli", model="haiku", reads_off_host=True)
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

    def lane_for_refusal(self, *, background: bool, pdf: bool | None = None) -> ModelRunLane:
        """Choose a selectable lane whose own catalog declares the refusal precondition."""
        status, catalog = self.exchange(
            "GET", "/v1/provider-catalog?" + urlencode({"workspace_root": str(self.endpoint.workspace_root)})
        )
        assert status == 200 and isinstance(catalog, dict), (status, catalog)
        records = catalog["providers"]
        assert isinstance(records, list)
        for record in records:
            support = record["background_requests"]
            if record["health"]["selectable"] is not True or record["executable"] is not True:
                continue
            if (support["text"] != "unsupported") is not background:
                continue
            if pdf is not None and (support["pdf"] != "unsupported") is not pdf:
                continue
            if pdf is False and support["image"] == "unsupported":
                continue
            models = record["catalog"]["models"]
            assert models, "the selected refusal fixture must name a declared model"
            # The gateway never reads the flag, and this route does not serve it; the agent's declared
            # catalogue marks only the keyless local lane, the one ``local_lane`` picks, as on-host.
            return ModelRunLane(
                provider_id=record["provider_id"],
                transport=record["transport"],
                model=models[0]["model"],
                reads_off_host=(record["provider_id"], record["transport"]) != ("ollama", "api"),
            )
        pytest.fail(f"the agent catalog provides no selectable refusal fixture for background={background}, pdf={pdf}")

    def local_lane(self) -> ModelRunLane:
        """The keyless lane on this computer's server, naming a model its catalog declares."""
        status, catalog = self.exchange(
            "GET", "/v1/provider-catalog?" + urlencode({"workspace_root": str(self.endpoint.workspace_root)})
        )
        assert status == 200 and isinstance(catalog, dict), (status, catalog)
        for record in catalog["providers"]:
            if (record["provider_id"], record["transport"]) == ("ollama", "api"):
                models = record["catalog"]["models"]
                assert models, "the local lane must declare a model"
                return ModelRunLane(
                    provider_id="ollama", transport="api", model=models[0]["model"], reads_off_host=False
                )
        pytest.fail("the agent catalog serves no local lane")

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


def _agent_setting_environment(checkout: Path, values: Mapping[str, str]) -> dict[str, str]:
    """Take each name from the external agent's own field schema, including its aliases."""
    result = run_audited_process(
        [str(checkout / ".venv" / "Scripts" / "python.exe"), "-c", _ENVIRONMENT_NAMES_PROBE, json.dumps(tuple(values))],
        cwd=checkout,
        env=system_environment(os.environ),
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    names = _ENVIRONMENT_NAMES.validate_json(result.stdout, strict=True)
    assert names.keys() == values.keys(), "the agent must declare every requested settings field"
    assert len(set(names.values())) == len(names), "the fixture must not overwrite another agent setting"
    return {names[field]: value for field, value in values.items()}


class _EmptyOllamaHandler(BaseHTTPRequestHandler):
    """A loopback Ollama server with nothing installed: the agent's probe reads it, no model runs on it."""

    def do_GET(self) -> None:
        answers = {"/api/version": {"version": "0.0.0-synthetic"}, "/api/tags": {"models": []}}
        answer = answers.get(self.path)
        payload = json.dumps(answer if answer is not None else {"error": "not found"}).encode()
        self.send_response(200 if answer is not None else 404)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


@pytest.fixture(scope="module")
def empty_ollama() -> Iterator[int]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _EmptyOllamaHandler)
    serving = Thread(target=server.serve_forever, name="empty-ollama", daemon=False)
    serving.start()
    try:
        yield int(server.server_address[1])
    finally:
        server.shutdown()
        server.server_close()
        serving.join()


@pytest.fixture(scope="module")
def gateway(tmp_path_factory: pytest.TempPathFactory, empty_ollama: int) -> Iterator[_Gateway]:
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
    }
    environment.update(
        _agent_setting_environment(
            checkout,
            {
                "environment": "production",
                "port": str(port),
                "worker_port": str(_free_port()),
                "auto_spawn_worker": "true",
                "agent_home": str(root / "home"),
                "workspace_root": str(root / "workspace"),
                "database_backend": "sqlite",
                "database_url": f"sqlite+aiosqlite:///{(root / 'agent.db').as_posix()}",
                "checkpoint_backend": "sqlite",
                "checkpoint_database_url": f"sqlite+aiosqlite:///{(root / 'checkpoint.db').as_posix()}",
                "gateway_service_token": bearer,
                "internal_token": secrets.token_urlsafe(32),
                "host_token": host_token,
                "ollama_base_url": f"http://127.0.0.1:{empty_ollama}",
            },
        )
    )
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
    lane = gateway.lane_for_refusal(background=False)
    status, answer = gateway.background(run_id, lane)
    assert (status, _refusal_code(answer)) == (422, "background_lane_unsupported"), (status, answer)

    assert gateway.runs().run(lane=lane, body=_body(), deadline_seconds=30) == ModelRunRefusal(
        code=ModelRunRefusalCode.LANE_UNAVAILABLE
    )


def test_a_pdf_on_a_lane_that_takes_none_is_refused_and_its_upload_removed(gateway: _Gateway) -> None:
    run_id = secrets.token_hex(16)
    lane = gateway.lane_for_refusal(background=True, pdf=False)

    refused = gateway.runs(run_id=run_id).run(lane=lane, body=_body(("application/pdf", _PDF)), deadline_seconds=30)

    assert refused == ModelRunRefusal(code=ModelRunRefusalCode.INPUT_NOT_SUPPORTED), refused
    assert gateway.runs().accepted_media(lane) == (ModelRunMediaKind.IMAGE,)
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


def test_a_reply_option_the_lane_does_not_honour_is_refused_by_the_agent_and_never_sent(gateway: _Gateway) -> None:
    run_id = secrets.token_hex(16)
    status, answer = gateway.background(
        run_id,
        _TOOL_LESS_LANE,
        background={"system": "", "max_output_tokens": 16, "deadline_seconds": 30, "temperature": 0.0},
    )
    assert (status, _refusal_code(answer)) == (422, "background_option_unsupported"), (status, answer)

    body = _body().model_copy(
        update={"temperature": 0.0, "context_tokens": 4096, "response_schema": {"type": "object"}}
    )
    outcome = gateway.runs().run(lane=_TOOL_LESS_LANE, body=body, deadline_seconds=30)

    # Admitted without the options, the run then fails at the provider the disposable profile is not signed in to.
    assert outcome == ModelRunRefusal(code=ModelRunRefusalCode.RUN_FAILED), outcome


def test_a_model_the_local_server_has_not_installed_is_refused_as_not_installed(gateway: _Gateway) -> None:
    lane = gateway.local_lane()
    status, answer = gateway.background(secrets.token_hex(16), lane)
    assert (status, _refusal_code(answer)) == (422, "model_not_installed"), (status, answer)

    outcome = gateway.runs().run(lane=lane, body=_body(), deadline_seconds=30)

    assert outcome == ModelRunRefusal(code=ModelRunRefusalCode.MODEL_NOT_INSTALLED), outcome
