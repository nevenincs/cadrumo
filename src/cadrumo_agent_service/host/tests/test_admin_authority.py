"""Hosted gateway credentials cannot exercise parent-only admin ingress."""

from __future__ import annotations

import json
import socket
import struct
from threading import Event
from uuid import uuid4

import pytest
from pydantic import JsonValue, ValidationError

from ...admin import AdminServer
from ...contracts import ServiceStartupFrame
from ...service import _GatewayCredentials
from ..controller import AgentGenerations, ResolvedAgentCredentials
from ..credential_frame import build_credential_frame, wipe

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


class _CredentialSource:
    def resolve_for_agent(self) -> ResolvedAgentCredentials:
        return ResolvedAgentCredentials(AgentGenerations("synthetic-session", "synthetic-settings"), {})

    def current_generations(self) -> AgentGenerations:
        return AgentGenerations("synthetic-session", "synthetic-settings")


class _AdminRecorder:
    def __init__(self) -> None:
        self.actions: list[str] = []
        self.secret: bytearray | None = None

    def admin(self, action: str, *, secret: bytearray | None = None, **metadata: object) -> dict[str, JsonValue]:
        self.actions.append(action)
        self.secret = secret
        if action == "set":
            assert secret == bytearray(b"synthetic-provider-secret")
        return {"kind": "served", "action": action}


def _send(stream: socket.socket, payload: bytes | bytearray) -> None:
    stream.sendall(struct.pack("!I", len(payload)) + payload)


def _read(stream: socket.socket) -> dict[str, object]:
    def exact(size: int) -> bytes:
        result = bytearray()
        while len(result) < size:
            value = stream.recv(size - len(result))
            if not value:
                raise EOFError("admin_response_incomplete")
            result.extend(value)
        return bytes(result)

    (size,) = struct.unpack("!I", exact(4))
    document = json.loads(exact(size))
    assert isinstance(document, dict)
    return {str(key): value for key, value in document.items()}


@pytest.mark.parametrize("action", ["catalog", "status", "set", "remove", "reset", "auth", "sign_in", "start", "stop"])
def test_gateway_frame_secret_is_refused_and_parent_admin_secret_dispatches(action: str) -> None:
    startup = ServiceStartupFrame(bearer="a" * 64, gateway_bearer="b" * 64)
    parent = bytearray(startup.bearer, "ascii")
    gateway = bytearray(startup.gateway_bearer, "ascii")
    resolved = _GatewayCredentials(_CredentialSource(), gateway, Event()).resolve_for_agent()
    agent_frame = build_credential_frame(resolved.credentials, gateway_bearer=resolved.gateway_bearer)
    agent_token = json.loads(agent_frame)["gateway_bearer"].encode("ascii")
    assert parent not in agent_frame
    target = _AdminRecorder()
    server = AdminServer(target, bearer=parent)
    request: dict[str, object] = {"version": 1, "request_id": str(uuid4()), "action": action}
    if action in {"set", "remove", "reset", "auth", "sign_in"}:
        request.update(provider="synthetic", expected_revision="0" * 64)
    if action == "auth":
        request["choice"] = "provider_sign_in"
    secret = b"synthetic-provider-secret"
    if action == "set":
        request["secret_bytes"] = len(secret)
    try:
        with socket.create_connection(("127.0.0.1", server.port), timeout=5) as stream:
            _send(stream, agent_token)
            assert _read(stream) == {"kind": "refused", "code": "unauthenticated"}
        assert target.actions == []
        with socket.create_connection(("127.0.0.1", server.port), timeout=5) as stream:
            _send(stream, parent)
            _send(stream, json.dumps(request).encode())
            if action == "set":
                assert _read(stream) == {"event": "secret_ready", "request_id": request["request_id"]}
                _send(stream, secret)
            assert _read(stream) == {
                "version": 1,
                "request_id": request["request_id"],
                "result": {"kind": "served", "action": action},
            }
        assert target.actions == [action]
        if action == "set":
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
        {"bearer": "a" * 64},
        {"gateway_bearer": "b" * 64},
        {"bearer": "a" * 64, "gateway_bearer": "a" * 64},
    ],
)
def test_startup_refuses_missing_or_shared_authority(document: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        ServiceStartupFrame.model_validate(document)
