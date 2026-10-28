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

# Bounds the service's reaction to an ending, from the ending to its final
# "stopped" event. Interpreter start, imports and teardown fall outside it:
# they measure the host, not the lifetime contract.
_STOP_SECONDS = 10


async def _read_through_event(stdout: asyncio.StreamReader, event: bytes) -> bytes:
    """Return the published lines up to and including the first one carrying ``event``."""
    published = bytearray()
    while True:
        line = await stdout.readline()
        if not line:
            pytest.fail(f"service exited before publishing {event!r}: {bytes(published)!r}")
        published.extend(line)
        if event in line:
            return bytes(published)


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


@pytest.mark.parametrize("ending", ("runtime_revocation", "extra_input", "eof", "idle_then_eof"))
@pytest.mark.asyncio
async def test_service_stops_cleanly_for_parent_lifetime_endings(ending: str, tmp_path: Path) -> None:
    """Each ending stops the service; while nothing is pushed, it never claims again."""
    source_root = Path(__file__).resolve().parents[3]
    environment = os.environ.copy()
    existing_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = os.pathsep.join(
        value for value in (str(source_root), existing_pythonpath) if value is not None and value != ""
    )
    script = r"""
import asyncio
import sys
import threading
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
        self.changed = None

    def subscribe_changes(self, changed):
        self.changed = changed
        return lambda: None

    def subscribe_model_runs(self, requested):
        return lambda: None

    def claim(self):
        self.claims += 1
        if self.claims > 1:
            return None
        if WITHDRAW_LEASE:
            # The runtime later withdraws the lease and pushes that change on the connection.
            threading.Timer(0.2, self.changed).start()
        return object()

    async def close(self):
        pass

client = FakeClient()

async def open_client(**_kwargs):
    return client

class FakeService:
    def __init__(self, *, emit, **_kwargs):
        self.emit = emit

    def start(self):
        # Published after the first claim, so the parent can observe an idle, admitted loop.
        self.emit({"event": "test_agent_started"})
        return {"event": "agent_ready"}

    def hold_for_recovery(self):
        return None

    def observe(self):
        return True

    def runtime_changed(self):
        pass

    def model_runs(self):
        return None

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
# The real entrypoint configures logging at the process boundary, before the startup frame.
service_main.main()
print(f"claims={client.claims}", file=sys.stderr)
""".replace("WITHDRAW_LEASE", repr(ending == "runtime_revocation"))
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
            # EOF may arrive before the lifetime watcher exists; the service must still observe it.
            process.stdin.close()
        if ending == "idle_then_eof":
            published = await _read_through_event(process.stdout, b'"event":"test_agent_started"')
            # Measured from the first claim: long enough for a timed loop to have claimed several times.
            await asyncio.sleep(1.5)
            process.stdin.close()
        else:
            published = await _read_through_event(process.stdout, b'"event":"service_ready"')
        try:
            published += await asyncio.wait_for(
                _read_through_event(process.stdout, b'"event":"stopped"'), timeout=_STOP_SECONDS
            )
        except TimeoutError:
            process.kill()
            await process.wait()
            unread, errors = await asyncio.gather(process.stdout.read(), process.stderr.read())
            pytest.fail(f"service did not stop after its parent lifetime ended: {published + unread!r} {errors!r}")
        exit_code = await process.wait()
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
        if not process.stdin.is_closing():
            process.stdin.close()

    remaining, errors = await asyncio.wait_for(asyncio.gather(process.stdout.read(), process.stderr.read()), timeout=5)
    output = published + remaining
    assert exit_code == 0, (output, errors)
    assert b'"event":"stopped"' in output
    assert b"Fatal Python error" not in errors
    assert b"A" * 32 not in output + errors
    assert b"B" * 32 not in output + errors
    if ending == "idle_then_eof":
        assert b"claims=1" in errors, errors


@pytest.mark.parametrize("connection_closed", (False, True))
@pytest.mark.asyncio
async def test_overrun_lease_claim_keeps_the_tree_only_while_its_connection_stays_open(
    connection_closed: bool, tmp_path: Path
) -> None:
    """A slow runtime is not a lost one; a claim that closed the connection still ends the service."""
    source_root = Path(__file__).resolve().parents[3]
    environment = os.environ.copy()
    existing_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = os.pathsep.join(
        value for value in (str(source_root), existing_pythonpath) if value is not None and value != ""
    )
    script = r"""
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import cadrumo_agent_service.main as service_main
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError

profile_id = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")

class FakeClient:
    connected = SimpleNamespace(
        runtime_boot_id=UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
        connection_id=UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc"),
        profile_id=profile_id,
    )
    connection = SimpleNamespace(closed=CONNECTION_CLOSED)

    def __init__(self):
        self.claims = 0
        self.changed = None

    def subscribe_changes(self, changed):
        self.changed = changed
        return lambda: None

    def subscribe_model_runs(self, requested):
        return lambda: None

    def claim(self):
        self.claims += 1
        if self.claims == 2:
            # The runtime retired the lease's session and is slow to re-attend it.
            raise RefusalError(RefusalCode.TIMEOUT)
        if self.claims == 4:
            return None
        # A pushed frame wakes the next claim.
        threading.Timer(0.1, self.changed).start()
        return object()

    async def close(self):
        pass

client = FakeClient()

async def open_client(**_kwargs):
    return client

class FakeService:
    stops = 0
    observes = 0

    def __init__(self, **_kwargs):
        pass

    def start(self):
        return {"event": "agent_ready"}

    def hold_for_recovery(self):
        return None

    def observe(self):
        FakeService.observes += 1
        return True

    def runtime_changed(self):
        pass

    def model_runs(self):
        return None

    def stop(self):
        FakeService.stops += 1

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
# The real entrypoint configures logging at the process boundary, before the startup frame.
service_main.main()
print(f"claims={client.claims} observes={FakeService.observes} stops={FakeService.stops}", file=sys.stderr)
""".replace("CONNECTION_CLOSED", repr(connection_closed))
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
        process.stdin.write(startup)
        await process.stdin.drain()
        published = await _read_through_event(process.stdout, b'"event":"service_ready"')
        try:
            published += await asyncio.wait_for(
                _read_through_event(process.stdout, b'"event":"stopped"'), timeout=_STOP_SECONDS
            )
        except TimeoutError:
            process.kill()
            await process.wait()
            unread, errors = await asyncio.gather(process.stdout.read(), process.stderr.read())
            pytest.fail(f"service did not end once its lease was withdrawn: {published + unread!r} {errors!r}")
        exit_code = await process.wait()
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
        if not process.stdin.is_closing():
            process.stdin.close()

    remaining, errors = await asyncio.wait_for(asyncio.gather(process.stdout.read(), process.stderr.read()), timeout=5)
    output = published + remaining
    assert exit_code == 0, (output, errors)
    assert b'"event":"stopped"' in output
    if connection_closed:
        assert b'"event":"refused","code":"agent_timeout"' in output
        assert b"claims=2 observes=0 stops=0" in errors
    else:
        assert b'"event":"refused"' not in output
        # The tree was observed after the retried claim and never retired by the loop.
        assert b"claims=4 observes=1 stops=0" in errors
