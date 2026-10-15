"""Session holder input framing and authority retirement with stdin still open."""

from __future__ import annotations

import asyncio
import os
import struct
import sys
from pathlib import Path
from threading import Thread

import pytest

from ..session_hold import (
    _MAXIMUM_PASSWORD_BYTES,
    _MAXIMUM_REQUEST_LINE_BYTES,
    _read_stdin_bytes,
    _read_stdin_line,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_password_and_correlated_command_frames_are_read_without_overconsuming() -> None:
    reader, writer = os.pipe()
    password = b"synthetic-password"
    first = b'{"request_id":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa","action":"status"}\n'
    second = b'{"request_id":"bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb","action":"close"}\n'
    os.write(writer, struct.pack("!I", len(password)) + password + first + second)
    os.close(writer)
    try:
        header = _read_stdin_bytes(reader, 4)
        assert len(header) == 4
        password_size = struct.unpack("!I", header)[0]
        assert 0 < password_size <= _MAXIMUM_PASSWORD_BYTES
        secret = _read_stdin_bytes(reader, password_size)
        try:
            assert secret == password
        finally:
            secret[:] = bytes(len(secret))
        assert _read_stdin_line(reader, _MAXIMUM_REQUEST_LINE_BYTES) == first
        assert _read_stdin_line(reader, _MAXIMUM_REQUEST_LINE_BYTES) == second
    finally:
        os.close(reader)


def test_request_line_reader_stops_at_the_existing_maximum_plus_one() -> None:
    reader, writer = os.pipe()
    payload = b"x" * (_MAXIMUM_REQUEST_LINE_BYTES + 2) + b"\n"

    def write_payload() -> None:
        try:
            remaining = memoryview(payload)
            while remaining:
                written = os.write(writer, remaining)
                remaining = remaining[written:]
        finally:
            os.close(writer)

    writer_thread = Thread(target=write_payload)
    writer_thread.start()
    try:
        assert _read_stdin_line(reader, _MAXIMUM_REQUEST_LINE_BYTES) == b"x" * (_MAXIMUM_REQUEST_LINE_BYTES + 1)
        assert _read_stdin_line(reader, _MAXIMUM_REQUEST_LINE_BYTES) == b"x\n"
        writer_thread.join(timeout=5)
        assert not writer_thread.is_alive()
    finally:
        os.close(reader)
        if writer_thread.is_alive():
            writer_thread.join(timeout=1)


@pytest.mark.asyncio
async def test_authority_retirement_exits_while_parent_keeps_stdin_open(tmp_path: Path) -> None:
    source_root = Path(__file__).resolve().parents[3]
    environment = os.environ.copy()
    existing_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = os.pathsep.join(
        value for value in (str(source_root), existing_pythonpath) if value is not None and value != ""
    )
    script = r"""
import contextlib
import sys
import threading
from types import SimpleNamespace
from uuid import UUID

from cadrumo_runtime.host import session_hold

profile_id = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")

class FakeClient:
    def __init__(self):
        self.status_snapshot = SimpleNamespace(
            status=SimpleNamespace(session_id=UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")),
            runtime_boot_id=UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc"),
            connection_id=UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd"),
        )

    def resume_receipt(self):
        return self.status_snapshot

    def subscribe_session_retirement(self, callback):
        timer = threading.Timer(1.0, callback)
        timer.daemon = True
        timer.start()

    def close(self):
        pass

client = FakeClient()

async def open_client(**_kwargs):
    return client

session_hold.open_installed_client = open_client
session_hold.composed_profile_persistence_ports = contextlib.nullcontext
sys.exit(session_hold.main(["--profile-id", str(profile_id)]))
"""
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        script,
        cwd=tmp_path,
        env=environment,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    assert process.stderr is not None
    try:
        held = await asyncio.wait_for(process.stdout.readline(), timeout=5)
        assert b'"kind":"session_held"' in held
        await asyncio.sleep(0.2)
        exit_before_retirement = process.returncode
        assert exit_before_retirement is None
        assert not process.stdin.is_closing()
        try:
            exit_code = await asyncio.wait_for(process.wait(), timeout=10)
        except TimeoutError:
            process.kill()
            await process.wait()
            pytest.fail("session holder did not stop after authority retirement")
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
        if not process.stdin.is_closing():
            process.stdin.close()

    output, errors = await asyncio.wait_for(asyncio.gather(process.stdout.read(), process.stderr.read()), timeout=5)
    assert exit_code == 0, (output, errors)
    assert b'"kind":"session_retired"' in output
    assert b"Fatal Python error" not in errors
