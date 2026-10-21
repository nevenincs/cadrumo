"""Sign-in observation stays responsive while the gateway lifecycle owns its lock."""

import json
import socket
import struct
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest

from cadrumo_client.transport.service_client import InstalledServiceClient

from ...admin import AdminServer
from ...service import AgentService
from ..auth_attempt import AuthAttempt

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


def _read_frame(stream: socket.socket) -> bytes:
    def exact(size: int) -> bytes:
        result = bytearray()
        while len(result) < size:
            part = stream.recv(size - len(result))
            if not part:
                raise EOFError("administration response ended")
            result.extend(part)
        return bytes(result)

    (size,) = struct.unpack("!I", exact(4))
    return exact(size)


@pytest.mark.parametrize("closing", [False, True])
def test_settings_read_reports_lost_authority_while_the_gateway_is_stopping(tmp_path: Path, closing: bool) -> None:
    service = AgentService(
        client=cast(InstalledServiceClient, SimpleNamespace(lease=None)),
        storage_root=tmp_path,
        gateway_bearer=bytearray(),
        emit=lambda _event: None,
    )
    if closing:
        service._closing.set()
    bearer = bytearray(b"a" * 64)
    server = AdminServer(service, bearer=bearer)
    request = {"version": 1, "request_id": str(uuid4()), "action": "status"}
    try:
        with service._guard, socket.create_connection(("127.0.0.1", server.port), timeout=2) as stream:
            for payload in (bearer, json.dumps(request).encode()):
                stream.sendall(struct.pack("!I", len(payload)) + payload)
            reply = json.loads(_read_frame(stream))
            assert reply["request_id"] == request["request_id"]
            assert reply["result"] == {
                "kind": "refused",
                "code": "service_stopping" if closing else "signed_out",
            }
    finally:
        server.close()


@pytest.mark.parametrize("action", ["connect_status", "connect_cancel"])
@pytest.mark.parametrize("authority", ["current", "revoked", "signed_out", "closing", "wrong_attempt"])
def test_existing_attempt_is_observed_without_the_gateway_lifecycle_lock(
    tmp_path: Path, action: str, authority: str
) -> None:
    client = SimpleNamespace(lease=object())
    service = AgentService(
        client=cast(InstalledServiceClient, client),
        storage_root=tmp_path,
        gateway_bearer=bytearray(),
        emit=lambda _event: None,
    )
    current = Event()
    current.set()
    settled = Event()
    # A genuine launch refusal supplies the terminal snapshot. No provider,
    # credential files or fabricated authentication success is needed here.
    attempt = AuthAttempt(
        provider="example",
        lane="example_cli",
        executable=tmp_path / "absent.exe",
        arguments=(),
        directory=tmp_path,
        environment={},
        valid=current.is_set,
        settled=settled.set,
    )
    assert settled.wait(5)
    service._auth_attempt = attempt
    assert attempt.observe()["event"] == "failed"
    if authority == "revoked":
        current.clear()
    elif authority == "signed_out":
        client.lease = None
    elif authority == "closing":
        service._closing.set()
    attempt_id = str(uuid4()) if authority == "wrong_attempt" else attempt.id
    bearer = bytearray(b"a" * 64)
    server = AdminServer(service, bearer=bearer)
    request = {"version": 1, "request_id": str(uuid4()), "action": action, "attempt_id": attempt_id}
    try:
        # The HTTP-independent admin worker is a different thread. Holding
        # the real lock recreates startup/reaping contention deterministically;
        # the response must arrive before the lifecycle operation releases it.
        with service._guard, socket.create_connection(("127.0.0.1", server.port), timeout=2) as stream:
            for payload in (bearer, json.dumps(request).encode()):
                stream.sendall(struct.pack("!I", len(payload)) + payload)
            reply = json.loads(_read_frame(stream))
            assert reply["request_id"] == request["request_id"]
            answer = reply["result"]
            if authority in {"signed_out", "closing", "wrong_attempt"}:
                code = {
                    "signed_out": "signed_out",
                    "closing": "service_stopping",
                    "wrong_attempt": "invalid_request",
                }[authority]
                assert answer == {"kind": "refused", "code": code}
            else:
                assert answer["attempt_id"] == attempt.id
                assert answer["event"] == ("cancelled" if authority == "revoked" else "failed")
                assert "url" not in answer and "user_code" not in answer
                assert attempt._cancel.is_set() == (action == "connect_cancel" or authority == "revoked")
    finally:
        server.close()
        attempt.close()
