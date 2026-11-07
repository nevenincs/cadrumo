"""A read of the agent's served catalog is bounded at the desktop's catalog exchange, not the orchestration budget."""

from __future__ import annotations

import contextlib
import json
import threading
from collections.abc import Generator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from typing import cast, override

import pytest

from cadrumo_client.transport.service_client import InstalledServiceClient

from ...service import AgentService
from ...service_support import SERVED_CATALOG_READ_POLICY
from ..controller import (
    AgentGenerations,
    AgentHostController,
    AgentHostError,
    AgentHostRefusal,
    AgentHostState,
    AgentReady,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _Controller:
    def __init__(self, ready: AgentReady) -> None:
        self.ready = ready
        self.state = AgentHostState.READY

    def published(self) -> AgentReady:
        return self.ready

    def cancel_start(self) -> None:
        pass

    def stop(self) -> None:
        pass


@contextlib.contextmanager
def _hung_gateway() -> Generator[int]:
    """Serve a catalog response whose body never arrives until the test ends."""
    release = threading.Event()
    body = json.dumps({"api_version": "v1", "providers": []}).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.flush()
            if release.wait(120):
                with contextlib.suppress(OSError):
                    self.wfile.write(body)

        @override
        def log_message(self, format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    owner = threading.Thread(target=server.serve_forever)
    owner.start()
    try:
        yield server.server_port
    finally:
        release.set()
        server.shutdown()
        owner.join(10)
        server.server_close()


def _service(tmp_path: Path, port: int) -> AgentService:
    client = SimpleNamespace(lease=object(), connection=SimpleNamespace(close=lambda: None))
    service = AgentService(
        client=cast(InstalledServiceClient, client),
        storage_root=tmp_path / "storage",
        gateway_bearer=bytearray(b"synthetic-bearer"),
        emit=lambda _event: None,
    )
    ready = AgentReady(AgentGenerations("synthetic-session", "synthetic-settings"), port, "synthetic-agent", 1)
    service._controller = cast(AgentHostController, _Controller(ready))
    service._workspace = tmp_path
    return service


def test_a_hung_gateway_leaves_the_live_catalog_unread_within_the_exchange_bound(tmp_path: Path) -> None:
    with _hung_gateway() as port:
        service = _service(tmp_path, port)
        answers: list[object] = []
        reader = threading.Thread(target=lambda: answers.append(service._live_catalog()), daemon=True)
        try:
            reader.start()
            reader.join(SERVED_CATALOG_READ_POLICY.timeout_seconds + 5)
            assert not reader.is_alive(), "the served catalog read outlived the desktop's catalog exchange"
            assert answers == [None]
        finally:
            service.close()


def test_a_cancelled_served_catalog_read_is_not_taken_for_an_unread_catalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service(tmp_path, 1)

    def cancelled(_ready: AgentReady) -> dict[str, object]:
        raise AgentHostError(AgentHostRefusal.CANCELLED)

    monkeypatch.setattr(service, "_served_catalog", cancelled)
    try:
        with pytest.raises(AgentHostError) as refused:
            service._live_catalog()
        assert refused.value.reason is AgentHostRefusal.CANCELLED
    finally:
        service.close()
