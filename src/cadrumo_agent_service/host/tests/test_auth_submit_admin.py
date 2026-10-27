"""The authorization code travels only in the separately framed secret."""

import json
import socket
import struct
from uuid import uuid4

import pytest
from pydantic import JsonValue, ValidationError

from ...admin import AdminRequest, AdminServer

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _send(stream: socket.socket, payload: bytes) -> None:
    stream.sendall(struct.pack("!I", len(payload)) + payload)


def _read(stream: socket.socket) -> dict[str, object]:
    def exact(size: int) -> bytes:
        result = bytearray()
        while len(result) < size:
            data = stream.recv(size - len(result))
            if not data:
                raise EOFError
            result.extend(data)
        return bytes(result)

    (size,) = struct.unpack("!I", exact(4))
    value: object = json.loads(exact(size))
    assert isinstance(value, dict)
    return {str(key): item for key, item in value.items()}


def test_secret_frame_is_separate_and_wiped_after_dispatch() -> None:
    class Target:
        secret: bytearray | None = None

        def admin(self, action: str, *, secret: bytearray | None = None, **_kwargs: object) -> dict[str, JsonValue]:
            assert action == "connect_submit_code"
            assert secret == bytearray(b"synthetic-code")
            self.secret = secret
            return {"event": "started"}

    target = Target()
    bearer = bytearray(b"a" * 64)
    server = AdminServer(target, bearer=bearer)
    request = {
        "version": 1,
        "request_id": str(uuid4()),
        "action": "connect_submit_code",
        "attempt_id": str(uuid4()),
        "secret_bytes": len(b"synthetic-code"),
    }
    try:
        with socket.create_connection(("127.0.0.1", server.port), timeout=5) as stream:
            _send(stream, bytes(bearer))
            _send(stream, json.dumps(request).encode())
            assert _read(stream) == {"event": "secret_ready", "request_id": request["request_id"]}
            _send(stream, b"synthetic-code")
            reply = _read(stream)
            assert reply["result"] == {"event": "started"}
            assert "synthetic-code" not in str(reply)
        assert target.secret == bytearray()
    finally:
        server.close()


def test_code_is_not_an_admin_metadata_field() -> None:
    with pytest.raises(ValidationError):
        AdminRequest.model_validate(
            {"version": 1, "request_id": str(uuid4()), "action": "connect_submit_code", "code": "synthetic-code"},
            strict=False,
        )
