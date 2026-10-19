"""The quick check of every setup item answers inside its bound, with no network and no model load.

Startup, the status indicator and every surface's status row use the quick
check, so it must answer every item within 2 s whether the storage root is
clean or already provisioned. The registry here is the composed one, with
every item's real adapters. A recording proxy stands in for the network and a
recording endpoint for the local AI program, so a quick check that reached
either, or that asked the program to load or pull a model, is caught by what
those two observed rather than by trusting the code under test.

The provisioned case reads the browser builds this checkout already set up
for its own browser tests, read-only. Without them that case fails and names
the missing builds: a red that reports the host rather than the code.
"""

from __future__ import annotations

import asyncio
import json
import socket
import threading
import time
from collections.abc import Generator, Iterable
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Final, override

import pytest

from ...adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ...application.dependency_contracts import (
    DEPENDENCY_QUICK_CHECK_BUDGET_S,
    DependencyCheckMode,
    DependencyItemKind,
    DependencyState,
    DependencyStatusRow,
)
from ...application.dependency_registry import dependency_item_declarations
from ...application.dependency_setup_operation import (
    DEPENDENCIES_OPERATION_SUBJECT,
    DEPENDENCIES_STATUS_OPERATION_DEFINITION_ID,
)
from ...application.operations.models import OperationIdentity
from ...core.config import override_settings
from ...tests.env_scope import scoped_env_var
from ..dependency_operation_composition import build_dependency_registry_factory

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[4]
_PROVISIONED_BROWSERS: Final = _REPOSITORY_ROOT / "var" / "storage" / "components" / "playwright"
#: Requests that would make the local AI program load, run or download a model.
_MODEL_WORK_PATHS: Final = ("/api/generate", "/api/chat", "/api/pull", "/api/embed", "/api/create")


def bound_findings(rows: Iterable[DependencyStatusRow], *, elapsed_s: float, expected_items: int) -> list[str]:
    """Name every way a quick check broke its bound: too slow, an item missing, or an item that did not answer.

    The registry turns a probe that has not answered in time into ``unknown``,
    so an unknown row in a quick check is a late probe as often as an
    unreadable one; either breaks the promise that status answers at once.
    """
    answered = list(rows)
    findings: list[str] = []
    if elapsed_s >= DEPENDENCY_QUICK_CHECK_BUDGET_S:
        findings.append(f"the quick check took {elapsed_s:.2f} s, over its {DEPENDENCY_QUICK_CHECK_BUDGET_S} s bound")
    if len(answered) != expected_items:
        findings.append(f"the quick check answered {len(answered)} of {expected_items} items")
    findings.extend(f"{row.item_id} did not answer" for row in answered if row.state is DependencyState.UNKNOWN)
    findings.extend(
        f"{row.item_id} answered in {row.mode} mode" for row in answered if row.mode is not DependencyCheckMode.QUICK
    )
    return findings


@dataclass(slots=True)
class _Observed:
    proxy_connections: int = 0
    program_paths: list[str] = field(default_factory=list)


class _ProgramEndpoint(BaseHTTPRequestHandler):
    """A local AI program that is running, has no models, and records every request."""

    protocol_version = "HTTP/1.1"

    @override
    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:
        self._answer()

    def do_POST(self) -> None:
        self._answer()

    def do_HEAD(self) -> None:
        self._answer()

    def _answer(self) -> None:
        server = self.server
        assert isinstance(server, _RecordingServer)
        server.observed.program_paths.append(self.path)
        bodies = {"/api/version": {"version": "0.12.6"}, "/api/tags": {"models": []}, "/api/ps": {"models": []}}
        body = json.dumps(bodies.get(self.path, {})).encode()
        self.send_response(200 if self.path in bodies else 404)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)


class _RecordingServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, observed: _Observed) -> None:
        super().__init__(("127.0.0.1", 0), _ProgramEndpoint)
        self.observed = observed


@contextmanager
def _observed_boundaries() -> Generator[tuple[_Observed, str, str]]:
    """Start a recording proxy and a recording program endpoint; yield what they saw and their addresses."""
    observed = _Observed()
    proxy = socket.create_server(("127.0.0.1", 0))
    proxy.settimeout(0.1)
    stopping = threading.Event()

    def accept() -> None:
        while not stopping.is_set():
            try:
                connection, _ = proxy.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            observed.proxy_connections += 1
            connection.close()

    program = _RecordingServer(observed)
    threads = [
        threading.Thread(target=accept, daemon=True),
        threading.Thread(target=program.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True),
    ]
    for thread in threads:
        thread.start()
    host, port = program.server_address[:2]
    try:
        yield observed, f"http://127.0.0.1:{proxy.getsockname()[1]}", f"http://{host!s}:{port}/api/chat"
    finally:
        stopping.set()
        program.shutdown()
        program.server_close()
        proxy.close()
        for thread in threads:
            thread.join(5)


def _quick_rows(
    storage: Path, *, browsers: Path, proxy_url: str, program_url: str
) -> tuple[list[DependencyStatusRow], float]:
    identity = OperationIdentity(
        operation_id="0" * 64,
        definition_id=DEPENDENCIES_STATUS_OPERATION_DEFINITION_ID,
        subject_ref=DEPENDENCIES_OPERATION_SUBJECT,
    )

    async def read() -> tuple[list[DependencyStatusRow], float]:
        registry = build_dependency_registry_factory()(identity, asyncio.get_running_loop())
        started = time.monotonic()
        rows = await registry.read_rows(DependencyCheckMode.QUICK)
        return list(rows), time.monotonic() - started

    with (
        scoped_env_var("CADRUMO_PLAYWRIGHT_BROWSERS_DIR", str(browsers)),
        override_settings(
            cadrumo_local_storage_root=storage,
            cadrumo_proxy_url=proxy_url,
            cadrumo_llm_ollama_chat_url=program_url,
        ),
    ):
        return asyncio.run(read())


def _row(state: DependencyState, item_id: str = "browser") -> DependencyStatusRow:
    return DependencyStatusRow(
        item_id=item_id,
        kind=DependencyItemKind.BROWSER if item_id == "browser" else DependencyItemKind.LOCAL_AI,
        mode=DependencyCheckMode.QUICK,
        state=state,
    )


def test_the_bound_check_names_a_slow_check_a_missing_item_and_a_late_probe() -> None:
    """Each way of breaking the bound is caught on its own."""
    answered = [_row(DependencyState.READY), _row(DependencyState.ABSENT, "local_ai")]
    assert bound_findings(answered, elapsed_s=0.3, expected_items=2) == []
    assert bound_findings(answered, elapsed_s=2.0, expected_items=2) == [
        "the quick check took 2.00 s, over its 2.0 s bound"
    ]
    assert bound_findings(answered[:1], elapsed_s=0.3, expected_items=2) == ["the quick check answered 1 of 2 items"]
    late = [_row(DependencyState.UNKNOWN), answered[1]]
    assert bound_findings(late, elapsed_s=1.99, expected_items=2) == ["browser did not answer"]


@pytest.fixture
def storage(tmp_path: Path) -> Generator[Path]:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        yield profile.storage_root


def test_quick_check_on_a_clean_root_answers_every_item_inside_the_bound(storage: Path) -> None:
    """A clean root answers every item at once, with no network traffic and no model work."""
    with _observed_boundaries() as (observed, proxy_url, program_url):
        rows, elapsed = _quick_rows(
            storage, browsers=storage / "components" / "playwright", proxy_url=proxy_url, program_url=program_url
        )
    findings = bound_findings(rows, elapsed_s=elapsed, expected_items=len(dependency_item_declarations()))
    assert not findings, "\n".join(findings)
    assert next(row for row in rows if row.item_id == "browser").state is DependencyState.ABSENT
    assert observed.proxy_connections == 0
    assert not [path for path in observed.program_paths if path.startswith(_MODEL_WORK_PATHS)]


def test_quick_check_on_a_provisioned_root_answers_every_item_inside_the_bound(storage: Path) -> None:
    """With the browser builds in place the browser reads usable, still inside the bound and offline."""
    assert _PROVISIONED_BROWSERS.is_dir(), f"no provisioned browser builds at {_PROVISIONED_BROWSERS}"
    with _observed_boundaries() as (observed, proxy_url, program_url):
        rows, elapsed = _quick_rows(
            storage, browsers=_PROVISIONED_BROWSERS, proxy_url=proxy_url, program_url=program_url
        )
    findings = bound_findings(rows, elapsed_s=elapsed, expected_items=len(dependency_item_declarations()))
    assert not findings, "\n".join(findings)
    browser = next(row for row in rows if row.item_id == "browser")
    assert browser.state in {DependencyState.READY, DependencyState.STALE}, browser
    assert observed.proxy_connections == 0
    assert not [path for path in observed.program_paths if path.startswith(_MODEL_WORK_PATHS)]
