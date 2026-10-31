"""Every administration exchange is answered, however many arrive at once."""

from __future__ import annotations

import json
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock
from uuid import uuid4

import pytest
from pydantic import JsonValue

from ...admin import ADMIN_EXCHANGES, AdminServer
from ..credential_frame import wipe
from .admin_wire_support import read_frame, send_frame

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_BEARER = b"a" * 64


class _HeldTarget:
    """Holds each served exchange until released, as slow tree work would."""

    def __init__(self) -> None:
        self.release = Event()
        self.entered = 0
        self._lock = Lock()

    def admin(self, action: str, **metadata: object) -> dict[str, JsonValue]:
        with self._lock:
            self.entered += 1
        self.release.wait(10)
        return {"kind": "served", "action": action}


def _exchange(port: int, request_id: str) -> dict[str, object]:
    with socket.create_connection(("127.0.0.1", port), timeout=15) as stream:
        send_frame(stream, _BEARER)
        send_frame(stream, json.dumps({"version": 1, "request_id": request_id, "action": "catalog"}).encode())
        return read_frame(stream)


def test_exchanges_past_the_served_ones_are_answered_busy_and_the_served_ones_complete() -> None:
    target = _HeldTarget()
    bearer = bytearray(_BEARER)
    server = AdminServer(target, bearer=bearer)
    extra = 6
    try:
        with ThreadPoolExecutor(max_workers=ADMIN_EXCHANGES + extra) as pool:
            held_ids = [str(uuid4()) for _ in range(ADMIN_EXCHANGES)]
            held = [pool.submit(_exchange, server.port, request_id) for request_id in held_ids]
            deadline = time.monotonic() + 10
            while target.entered < ADMIN_EXCHANGES and time.monotonic() < deadline:
                time.sleep(0.01)
            assert target.entered == ADMIN_EXCHANGES

            extra_ids = [str(uuid4()) for _ in range(extra)]
            started = time.monotonic()
            answers = [pool.submit(_exchange, server.port, request_id).result(10) for request_id in extra_ids]
            assert time.monotonic() - started < 5
            assert answers == [
                {"version": 1, "request_id": request_id, "result": {"kind": "refused", "code": "busy"}}
                for request_id in extra_ids
            ]
            # None of them reached the service.
            assert target.entered == ADMIN_EXCHANGES

            target.release.set()
            assert [future.result(10) for future in held] == [
                {"version": 1, "request_id": request_id, "result": {"kind": "served", "action": "catalog"}}
                for request_id in held_ids
            ]
        # Every slot is free again.
        assert _exchange(server.port, request_id := str(uuid4())) == {
            "version": 1,
            "request_id": request_id,
            "result": {"kind": "served", "action": "catalog"},
        }
    finally:
        target.release.set()
        server.close()
        wipe(bearer)
