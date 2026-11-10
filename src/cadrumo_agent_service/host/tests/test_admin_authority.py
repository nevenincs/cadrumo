"""Hosted gateway credentials cannot exercise parent-only admin ingress."""

from __future__ import annotations

import json
import socket
from threading import Event
from uuid import uuid4

import pytest
from pydantic import JsonValue, ValidationError

from cadrumo_client.contracts.deadline_budget import TimeoutDeadline

from ...admin import AdminRequest, AdminServer
from ...contracts import ServiceStartupFrame
from ...gateway_credentials import GatewayCredentials
from ...providers.domain.record import LocalEngine, LocalPlacement
from ..controller import AgentGenerations, ResolvedAgentCredentials
from ..credential_frame import build_credential_frame, wipe
from .admin_wire_support import read_frame, send_frame

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


class _CredentialSource:
    def resolve_for_agent(self, *, deadline: TimeoutDeadline | None = None) -> ResolvedAgentCredentials:
        return ResolvedAgentCredentials(AgentGenerations("synthetic-session", "synthetic-settings"), {})

    def current_generations(self, *, deadline: TimeoutDeadline | None = None) -> AgentGenerations:
        return AgentGenerations("synthetic-session", "synthetic-settings")


class _AdminRecorder:
    def __init__(self) -> None:
        self.actions: list[str] = []
        self.secret: bytearray | None = None
        self.metadata: dict[str, object] = {}

    def admin(self, action: str, *, secret: bytearray | None = None, **metadata: object) -> dict[str, JsonValue]:
        self.actions.append(action)
        self.secret = secret
        self.metadata = metadata
        if action == "set":
            assert secret == bytearray(b"synthetic-provider-secret")
        return {"kind": "served", "action": action}


def _startup(**fields: object) -> ServiceStartupFrame:
    """Parse a startup document the way the service does: from the JSON line the desktop writes to stdin."""
    document = {"bearer": "a" * 64, "gateway_bearer": "b" * 64, **fields}
    return ServiceStartupFrame.model_validate_json(json.dumps(document))


@pytest.mark.parametrize(
    "action",
    [
        "catalog",
        "status",
        "provider_lanes",
        "set",
        "remove",
        "turn_on",
        "reset",
        "auth",
        "sign_in",
        "start",
        "stop",
        "connect",
        "connect_status",
        "connect_cancel",
        "connect_submit_code",
        "local_models",
        "local_model_add",
        "local_model_remove",
        "local_models_reset",
        "reading_model_choose",
        "local_engine",
        "local_engine_choose",
    ],
)
def test_gateway_frame_secret_is_refused_and_parent_admin_secret_dispatches(action: str) -> None:
    startup = _startup(local_engine_default="llamacpp")
    parent = bytearray(startup.bearer, "ascii")
    gateway = bytearray(startup.gateway_bearer, "ascii")
    host_token = bytearray(b"c" * 43)
    resolved = GatewayCredentials(_CredentialSource(), gateway, host_token, Event()).resolve_for_agent()
    agent_frame = build_credential_frame(
        resolved.credentials, gateway_bearer=resolved.gateway_bearer, host_token=resolved.host_token
    )
    agent_token = json.loads(agent_frame)["gateway_bearer"].encode("ascii")
    assert parent not in agent_frame
    assert json.loads(agent_frame)["host_token"] == host_token.decode("ascii")
    target = _AdminRecorder()
    server = AdminServer(target, bearer=parent)
    request: dict[str, object] = {"version": 1, "request_id": str(uuid4()), "action": action}
    if action in {"set", "remove", "turn_on", "reset", "auth", "sign_in", "connect"}:
        request.update(provider="synthetic", expected_revision="0" * 64)
    if action == "connect":
        request["method"] = "browser"
    if action in {"connect_status", "connect_cancel", "connect_submit_code"}:
        request["attempt_id"] = str(uuid4())
    if action == "auth":
        request["choice"] = "provider_sign_in"
    if action in {"local_model_add", "local_model_remove", "local_models_reset", "reading_model_choose"}:
        request["expected_revision"] = "0" * 64
    if action in {"local_model_add", "local_model_remove", "reading_model_choose"}:
        request.update(provider="synthetic_api", model="synthetic-model-1")
    if action == "local_engine_choose":
        request.update(engine="llamacpp", placement="cpu_only", expected_revision="0" * 64)
    secret = b"synthetic-provider-secret"
    if action in {"set", "connect_submit_code"}:
        request["secret_bytes"] = len(secret)
    try:
        with socket.create_connection(("127.0.0.1", server.port), timeout=5) as stream:
            send_frame(stream, agent_token)
            assert read_frame(stream) == {"kind": "refused", "code": "unauthenticated"}
        assert target.actions == []
        with socket.create_connection(("127.0.0.1", server.port), timeout=5) as stream:
            send_frame(stream, parent)
            send_frame(stream, json.dumps(request).encode())
            if action in {"set", "connect_submit_code"}:
                assert read_frame(stream) == {"event": "secret_ready", "request_id": request["request_id"]}
                send_frame(stream, secret)
            assert read_frame(stream) == {
                "version": 1,
                "request_id": request["request_id"],
                "result": {"kind": "served", "action": action},
            }
        assert target.actions == [action]
        if action == "local_engine_choose":
            assert target.metadata["engine"] is LocalEngine.LLAMACPP
            assert target.metadata["placement"] is LocalPlacement.CPU_ONLY
            assert target.metadata["expected_revision"] == "0" * 64
        if action in {"set", "connect_submit_code"}:
            assert target.secret == bytearray()
    finally:
        server.close()
        wipe(parent)
        wipe(gateway)
        wipe(agent_frame)
        if resolved.gateway_bearer is not None:
            wipe(resolved.gateway_bearer)


@pytest.mark.parametrize(
    "document",
    [
        {"bearer": "a" * 64, "local_engine_default": "llamacpp"},
        {"gateway_bearer": "b" * 64, "local_engine_default": "llamacpp"},
        {"bearer": "a" * 64, "gateway_bearer": "a" * 64, "local_engine_default": "llamacpp"},
    ],
)
def test_startup_refuses_missing_or_shared_authority(document: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        ServiceStartupFrame.model_validate_json(json.dumps(document))


def test_startup_refuses_a_frame_that_names_no_default_engine() -> None:
    with pytest.raises(ValidationError):
        ServiceStartupFrame.model_validate_json(json.dumps({"bearer": "a" * 64, "gateway_bearer": "b" * 64}))


@pytest.mark.parametrize("engine", ["vllm", "", "LLAMACPP", None])
def test_startup_refuses_an_unknown_default_engine(engine: object) -> None:
    with pytest.raises(ValidationError):
        _startup(local_engine_default=engine)


@pytest.mark.parametrize("engine", list(LocalEngine))
def test_startup_accepts_each_declared_default_engine(engine: LocalEngine) -> None:
    assert _startup(local_engine_default=engine.value).local_engine_default is engine


@pytest.mark.parametrize("model", ["synthetic-vision:1", "synthetic vision/1", "m" * 512, "é" * 512])
def test_a_model_added_to_the_list_is_any_model_id_the_catalogues_carry(model: str) -> None:
    request = AdminRequest(version=1, request_id=uuid4(), action="local_model_add", model=model)
    assert request.model == model


@pytest.mark.parametrize("model", ["", "m" * 513, "tab\there", "line\nbreak", "del\x7f"])
def test_a_model_id_outside_the_shared_rule_is_refused(model: str) -> None:
    with pytest.raises(ValidationError):
        AdminRequest(version=1, request_id=uuid4(), action="local_model_add", model=model)


def _engine_request(engine: str, placement: str) -> AdminRequest:
    """Parse a choose request from its wire JSON, the one path the admin server validates by."""
    return AdminRequest.model_validate_json(
        json.dumps(
            {
                "version": 1,
                "request_id": str(uuid4()),
                "action": "local_engine_choose",
                "engine": engine,
                "placement": placement,
                "expected_revision": "0" * 64,
            }
        )
    )


@pytest.mark.parametrize(
    ("engine", "placement"),
    [(engine, placement) for engine in LocalEngine for placement in LocalPlacement],
)
def test_the_local_engine_is_chosen_by_every_declared_engine_and_placement(
    engine: LocalEngine, placement: LocalPlacement
) -> None:
    request = _engine_request(engine.value, placement.value)

    assert (request.engine, request.placement) == (engine, placement)
    assert isinstance(request.engine, LocalEngine)
    assert isinstance(request.placement, LocalPlacement)


@pytest.mark.parametrize(
    ("engine", "placement"),
    [("vllm", "auto"), ("", "auto"), ("LLAMACPP", "auto"), ("llamacpp", "gpu_only"), ("llamacpp", "CPU_ONLY")],
)
def test_an_unknown_engine_or_placement_token_is_refused_at_ingress(engine: str, placement: str) -> None:
    with pytest.raises(ValidationError):
        _engine_request(engine, placement)


def _lanes_request(**fields: object) -> bytes:
    return json.dumps({"version": 1, "request_id": str(uuid4()), "action": "provider_lanes", **fields}).encode()


@pytest.mark.parametrize(
    "fields",
    [
        {"unheard_of": 1},
        {"provider": "synthetic", "unheard_of": "x"},
        {"secret_bytes": 4, "unheard_of": None},
    ],
)
def test_the_lanes_read_refuses_a_field_the_request_does_not_declare(fields: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        AdminRequest.model_validate_json(_lanes_request(**fields))


def test_the_lanes_read_is_refused_a_secret_and_dispatches_nothing() -> None:
    parent = bytearray(b"a" * 64)
    target = _AdminRecorder()
    server = AdminServer(target, bearer=parent)
    request = json.loads(_lanes_request(secret_bytes=4))
    try:
        with socket.create_connection(("127.0.0.1", server.port), timeout=5) as stream:
            send_frame(stream, parent)
            send_frame(stream, json.dumps(request).encode())
            assert read_frame(stream) == {
                "version": 1,
                "request_id": request["request_id"],
                "result": {"kind": "refused", "code": "invalid_request"},
            }
        assert target.actions == []
    finally:
        server.close()
        wipe(parent)
