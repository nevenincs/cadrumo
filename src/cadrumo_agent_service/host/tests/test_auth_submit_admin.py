"""The authorization code travels only in the separately framed secret."""

import json
import socket
from uuid import uuid4

import pytest
from pydantic import JsonValue, ValidationError

from ...admin import AdminRequest, AdminServer
from .admin_wire_support import read_frame, send_frame

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


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
            send_frame(stream, bytes(bearer))
            send_frame(stream, json.dumps(request).encode())
            assert read_frame(stream) == {"event": "secret_ready", "request_id": request["request_id"]}
            send_frame(stream, b"synthetic-code")
            reply = read_frame(stream)
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
