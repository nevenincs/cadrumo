"""A catalog read that arrives right after the agent is ready is served, not told the service is busy.

A read asked while the agent starts reads the declared catalog. When the agent
becomes ready the start forgets the kept reads, so that read's result is
withdrawn while it is still running. A request that arrives then, and the
request that was waiting for the withdrawn read, both wait for it to end within
their bound and are served the ready agent's catalog.
"""

from __future__ import annotations

import contextlib
import json
import threading
import time
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast, override

import pytest

from cadrumo_client.transport.service_client import InstalledServiceClient

from ... import service_administration as administration_module
from ...adapters.provider_catalog_metadata import declared_catalog_envelope
from ...providers.application.service import ProviderSettingsService
from ...providers.application.tests.memory_store import MemoryProviderSettingsStore
from ...providers.application.tests.synthetic_catalog import StaticCatalogSource
from ...service import AgentService
from ...service_support import ADMIN_READ_SECONDS
from ..controller import AgentGenerations, AgentHostController, AgentHostState, AgentReady

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SERVED: dict[str, Any] = {"api_version": "v1", "providers": []}
_DECLARED = declared_catalog_envelope({"providers": []})


class _Controller:
    """The agent tree, starting until the test makes it ready."""

    def __init__(self, ready: AgentReady) -> None:
        self.ready = ready
        self.state = AgentHostState.STARTING

    def published(self) -> AgentReady | None:
        return self.ready if self.state is AgentHostState.READY else None

    def cancel_start(self) -> None:
        pass

    def stop(self) -> None:
        pass


@contextlib.contextmanager
def _gateway(reads: list[float]) -> Generator[int]:
    """Serve the ready agent's catalog, noting each read."""
    body = json.dumps(_SERVED).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            reads.append(time.monotonic())
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
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
        server.shutdown()
        owner.join(10)
        server.server_close()


def test_a_catalog_read_right_after_ready_is_served_while_the_starting_read_ends(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entered = threading.Event()
    release = threading.Event()

    def declared() -> dict[str, Any]:
        # The read asked while the agent starts is still running when it becomes ready.
        entered.set()
        assert release.wait(10)
        return _DECLARED

    monkeypatch.setattr(administration_module, "declared_provider_catalog_response", declared)
    gateway_reads: list[float] = []
    with _gateway(gateway_reads) as port:
        client = SimpleNamespace(lease=object(), connection=SimpleNamespace(close=lambda: None))
        service = AgentService(
            client=cast(InstalledServiceClient, client),
            storage_root=tmp_path / "storage",
            gateway_bearer=bytearray(b"synthetic-bearer"),
            emit=lambda _event: None,
        )
        service._providers = ProviderSettingsService(
            store=MemoryProviderSettingsStore(), catalog_source=StaticCatalogSource()
        )
        controller = _Controller(
            AgentReady(AgentGenerations("synthetic-session", "synthetic-settings"), port, "synthetic-agent", 1)
        )
        service._controller = cast(AgentHostController, controller)
        service._workspace = tmp_path
        try:
            with ThreadPoolExecutor(max_workers=2) as callers:
                starting = callers.submit(service.admin, "catalog")
                assert entered.wait(5)
                # The agent becomes ready: the start forgets the kept reads before it reports ready.
                controller.state = AgentHostState.READY
                service._forget_reads()
                ready_at = time.monotonic()
                after_ready = callers.submit(service.admin, "catalog")
                time.sleep(0.2)
                assert not after_ready.done(), "a read right after ready was refused while the starting read ran"
                release.set()
                assert after_ready.result(timeout=ADMIN_READ_SECONDS + 5) == _SERVED
                assert starting.result(timeout=ADMIN_READ_SECONDS + 5) == _SERVED
            # One fresh read of the ready agent served both requests.
            assert len(gateway_reads) == 1
            assert gateway_reads[0] >= ready_at
        finally:
            service.close()
