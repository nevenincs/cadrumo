"""The service stdin frame is bounded and its lifetime reader cannot pin a buffered lock."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from threading import Thread

import pytest

from ...main import _MAX_STARTUP_FRAME_BYTES, _read_startup_frame

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_startup_frame_reader_leaves_bytes_after_its_newline_for_lifetime_monitor() -> None:
    reader, writer = os.pipe()
    frame = b'{"bearer":"synthetic-admin","gateway_bearer":"synthetic-gateway"}\n'
    try:
        os.write(writer, frame + b"extra")
        os.close(writer)
        assert _read_startup_frame(reader) == frame
        assert os.read(reader, 1) == b"e"
    finally:
        os.close(reader)


def test_startup_frame_reader_stops_at_the_existing_size_limit() -> None:
    reader, writer = os.pipe()
    payload = b"x" * (_MAX_STARTUP_FRAME_BYTES + 2) + b"\n"
    errors: list[OSError] = []

    def write_frame() -> None:
        try:
            remaining = memoryview(payload)
            while remaining:
                written = os.write(writer, remaining)
                remaining = remaining[written:]
        except OSError as error:
            errors.append(error)
        finally:
            os.close(writer)

    writer_thread = Thread(target=write_frame)
    writer_thread.start()
    try:
        line = _read_startup_frame(reader)
        writer_thread.join(timeout=5)
        assert not writer_thread.is_alive()
        assert not errors
        assert len(line) == _MAX_STARTUP_FRAME_BYTES + 1
        assert not line.endswith(b"\n")
    finally:
        os.close(reader)
        if writer_thread.is_alive():
            writer_thread.join(timeout=1)


@pytest.mark.parametrize("ending", ("runtime_revocation", "extra_input", "eof"))
@pytest.mark.asyncio
async def test_service_stops_cleanly_for_parent_lifetime_endings(ending: str, tmp_path: Path) -> None:
    source_root = Path(__file__).resolve().parents[3]
    environment = os.environ.copy()
    existing_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = os.pathsep.join(value for value in (str(source_root), existing_pythonpath) if value)
    script = r"""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import cadrumo_agent_service.main as service_main

profile_id = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")

class FakeClient:
    connected = SimpleNamespace(
        runtime_boot_id=UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
        connection_id=UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc"),
        profile_id=profile_id,
    )

    def __init__(self):
        self.claims = 0

    def claim(self):
        self.claims += 1
        return object() if self.claims == 1 else None

    async def close(self):
        pass

client = FakeClient()

async def open_client(**_kwargs):
    return client

class FakeService:
    def __init__(self, **_kwargs):
        pass

    def start(self):
        return {"event": "agent_ready"}

    def observe(self):
        return True

    def stop(self):
        pass

    def request_close(self):
        pass

    def close(self):
        pass

class FakeAdminServer:
    port = 32123

    def __init__(self, *_args, **_kwargs):
        pass

    def close(self):
        pass

service_main.open_service_client = open_client
service_main.AgentService = FakeService
service_main.AdminServer = FakeAdminServer
service_main.effective_storage_root = lambda: Path(".")
sys.argv = ["cadrumo-agent-service", "serve", "--profile-id", str(profile_id)]
service_main._serve()
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
        startup = json.dumps({"bearer": "A" * 32, "gateway_bearer": "B" * 32}).encode("ascii") + b"\n"
        process.stdin.write(startup + (b"unexpected" if ending == "extra_input" else b""))
        await process.stdin.drain()
        if ending == "eof":
            process.stdin.close()
        try:
            exit_code = await asyncio.wait_for(process.wait(), timeout=10)
        except TimeoutError:
            process.kill()
            await process.wait()
            pytest.fail("service did not stop after runtime revocation")
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
        if not process.stdin.is_closing():
            process.stdin.close()

    output, errors = await asyncio.wait_for(asyncio.gather(process.stdout.read(), process.stderr.read()), timeout=5)
    assert exit_code == 0, (output, errors)
    assert b'"event":"stopped"' in output
    assert b"Fatal Python error" not in errors
    assert b"A" * 32 not in output + errors
    assert b"B" * 32 not in output + errors
