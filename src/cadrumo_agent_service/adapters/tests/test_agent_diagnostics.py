"""Agent diagnostics, the hosted worker's relayed among them, reach the real scrubbed log through the agent's pipes."""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import override

import pytest

from cadrumo.core import logging as project_logging
from cadrumo.core.config import override_settings

from ..agent_diagnostics import AgentDiagnosticLines, AgentDiagnosticSink
from ..agent_process import _StandardErrorTail

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


@pytest.fixture
def log_file(tmp_path: Path) -> Iterator[Path]:
    """Use real formatters, disk handlers and privacy filters."""
    project_logging.register_first_party_logger("cadrumo_agent_service")
    project_logging.register_first_party_logger("cadrumo_agent")
    configured = project_logging._configured
    try:
        project_logging._configured = False
        with override_settings(
            cadrumo_log_dir=tmp_path / "logs", cadrumo_log_root_level="DEBUG", cadrumo_log_file_level="DEBUG"
        ):
            project_logging.configure_logging()
            yield tmp_path / "logs" / "cadrumo.log"
    finally:
        project_logging._configured = False
        project_logging.configure_logging()
        project_logging._configured = configured or True


def _line(sequence: int, *, service: str = "worker", level: str = "DEBUG", message: str = "worker diagnostic") -> bytes:
    return (
        json.dumps(
            {
                "schema": "cadrumo-agent.log/1",
                "pid": 4321,
                "seq": sequence,
                "timestamp": "2026-10-14T12:30:15.123+00:00",
                "level": level,
                "service": service,
                "name": "cadrumo_agent.worker.executor",
                "message": message,
                "worker_port": 54321,
                "tool_arguments": {"private": "PRIVATE-TOOL-CANARY"},
            }
        )
        + "\n"
    ).encode()


def _read(path: Path) -> str:
    assert project_logging.flush_logging(timeout=5)
    for handler in logging.getLogger().handlers:
        handler.flush()
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize("level", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
def test_original_level_identity_timestamp_and_operational_context(log_file: Path, level: str) -> None:
    """No INFO wrapper replaces the producer's level or process."""
    sink = AgentDiagnosticSink()
    line = _line(1, level=level)
    framing = AgentDiagnosticLines(sink, pid=999)
    framing.feed(line[:37])
    framing.feed(line[37:])
    sink.line(line.rstrip(), pid=999)  # The rotating file contains the same record.
    written = _read(log_file)
    assert written.count("worker diagnostic") == 1
    assert f"[{level}]" in written
    assert "2026-10-14T12:30:15.123Z" in written
    assert '"process_id":4321' in written
    assert '"process_role":"extension_service"' in written
    assert '"worker_port":54321' in written
    assert "PRIVATE-TOOL-CANARY" not in written


def test_scrubbing_and_third_party_debug_containment(log_file: Path) -> None:
    """First-party agent DEBUG survives, secrets and SDK DEBUG do not."""
    sink = AgentDiagnosticSink()
    sink.line(_line(1, message="Authorization: Bearer PRIVATE-BEARER-CANARY").rstrip(), pid=0)
    sdk = json.loads(_line(2))
    sdk["name"] = "anthropic._base_client"
    sdk["message"] = "PRIVATE-SDK-PAYLOAD-CANARY"
    sink.line(json.dumps(sdk).encode(), pid=0)
    written = _read(log_file)
    assert "[DEBUG] cadrumo_agent.worker.executor" in written
    assert "<redacted>" in written
    assert "PRIVATE-BEARER-CANARY" not in written
    assert "PRIVATE-SDK-PAYLOAD-CANARY" not in written


def test_protocol_unknown_bytes_malformed_and_oversized_records(log_file: Path) -> None:
    """Failures report loss without copying arbitrary process bytes into the log."""
    framing = AgentDiagnosticLines(AgentDiagnosticSink(), pid=77)
    framing.feed(b'{"event":"agent_ready","bearer":"PRIVATE-PROTOCOL-CANARY"}\n')
    framing.feed(b"PRIVATE-RAW-CANARY\n")
    framing.feed(b'{"schema":"cadrumo-agent.log/1","schema":"bad"}\n')
    framing.feed(b"x" * (65 * 1024) + b"\n")
    framing.feed(_line(2))
    written = _read(log_file)
    assert "PRIVATE-" not in written
    assert "agent_diagnostic_record_rejected" in written
    assert "agent_diagnostic_line_too_large" in written
    assert "worker diagnostic" in written


def test_successful_local_health_polls_are_quiet_but_failures_and_other_requests_survive(log_file: Path) -> None:
    """Filter only the successful local probe, before URL scrubbing removes its purpose."""
    sink = AgentDiagnosticSink()
    for sequence, (level, url, status, exception) in enumerate(
        [
            ("INFO", "http://127.0.0.1:54321/health", "200 OK", None),
            ("INFO", "http://localhost:54321/health", "200 OK", None),
            ("INFO", "http://[::1]:54321/health", "200 OK", None),
            ("INFO", "http://127.0.0.1:54321/health", "503 Service Unavailable", None),
            ("WARNING", "http://127.0.0.1:54321/health", "200 OK", None),
            ("INFO", "http://127.0.0.1:54321/v1/runs", "200 OK", None),
            ("INFO", "https://provider.example/health", "200 OK", None),
            ("INFO", "http://127.0.0.1:54321/health", "200 OK", "RuntimeError: probe decode failed"),
        ],
        start=1,
    ):
        record = json.loads(_line(sequence, level=level))
        record.update(name="httpx", message=f'HTTP Request: GET {url} "HTTP/1.1 {status}"', exception=exception)
        sink.line(json.dumps(record).encode(), pid=0)
    written = _read(log_file)
    assert written.count("HTTP Request:") == 5
    assert "503 Service Unavailable" in written
    assert "[WARNING] httpx:" in written
    assert "probe decode failed" in written


def test_real_pipe_is_forwarded_before_writer_closes(log_file: Path) -> None:
    """The drain must read a small live write without waiting for a 4KiB buffer."""
    import os
    import time

    reader, writer = os.pipe()
    stream = os.fdopen(reader, "rb")
    tail = _StandardErrorTail(
        stream, limit=8192, diagnostics=AgentDiagnosticLines(AgentDiagnosticSink(), pid=os.getpid())
    )
    try:
        os.write(writer, _line(1, service="gateway", message="live gateway"))
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if log_file.is_file() and "live gateway" in _read(log_file):
                break
            time.sleep(0.01)
        assert "live gateway" in _read(log_file)
        assert '"process_role":"extension_service"' in _read(log_file)
    finally:
        os.close(writer)
        tail.release(timeout=2)
    assert b"live gateway" in tail.settled(timeout=0)


def test_cli_diagnostics_keep_launcher_pid_and_severity(log_file: Path) -> None:
    """Store/setup command diagnostics join the feed without logging their stdout."""
    framing = AgentDiagnosticLines(AgentDiagnosticSink(), pid=8765, cli=True)
    framing.feed(b"ERROR cadrumo_agent.control: store setup failed\n")
    framing.feed(b'Traceback (most recent call last):\n  File "fixture.py", line 1\nRuntimeError: store locked\n')
    framing.finish()
    written = _read(log_file)
    assert "[ERROR]" in written
    assert '"process_id":8765' in written
    assert '"process_role":"extension_service"' in written
    assert "RuntimeError: store locked" in written


def test_a_relayed_worker_record_keeps_its_exception_detail(log_file: Path) -> None:
    """A worker record the agent relays on its standard error keeps its exception text through scrubbing."""
    record = json.loads(_line(2, message="relayed probe"))
    record["exception"] = "Traceback\nRuntimeError: diagnostic failure"
    lines = AgentDiagnosticLines(AgentDiagnosticSink(), pid=9876)
    lines.feed((json.dumps(record) + "\n").encode())
    lines.finish()
    written = _read(log_file)
    assert written.count("relayed probe") == 1
    assert "RuntimeError: diagnostic failure" in written
    assert "PRIVATE-TOOL-CANARY" not in written


class _StalledLog(logging.Handler):
    """A log destination whose writes wait until it is released, as a file on a saturated disk does."""

    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.entered = threading.Event()
        self.released = threading.Event()

    @override
    def emit(self, record: logging.LogRecord) -> None:
        self.entered.set()
        self.released.wait(30)


def test_an_agent_keeps_writing_while_the_application_log_is_stalled(log_file: Path) -> None:
    """A stalled log never stops the drain: the agent's writes complete and the loss is reported.

    Before the drain handed lines to their own thread, the first write into a
    stalled log stopped all reading and the writer blocked on the full pipe
    for as long as the log stalled.
    """
    import os
    import time

    stalled = _StalledLog()
    logger = logging.getLogger("cadrumo_agent.worker.executor")
    logger.addHandler(stalled)
    reader, writer = os.pipe()
    stream = os.fdopen(reader, "rb")
    tail = _StandardErrorTail(
        stream, limit=8192, diagnostics=AgentDiagnosticLines(AgentDiagnosticSink(), pid=os.getpid())
    )
    try:
        os.write(writer, _line(1))
        assert stalled.entered.wait(10)
        # Twice the backlog the log may fall behind by, far past what the pipe holds.
        record = _line(2, message="x" * 900)
        started = time.monotonic()
        for _ in range(2 * 1024 * 1024 // len(record)):
            os.write(writer, record)
        assert time.monotonic() - started < 10
    finally:
        stalled.released.set()
        os.close(writer)
        tail.release(timeout=10)
        logger.removeHandler(stalled)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and "agent_diagnostic_output_dropped" not in _read(log_file):
        time.sleep(0.05)
    assert "agent_diagnostic_output_dropped" in _read(log_file)
