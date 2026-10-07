"""A supervised runtime answers its launching supervisor over the standard streams.

Synthetic roots contain no taxpayer profiles. Each test owns its runtime or
fixture process and kills it during teardown, including on assertion failure.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import os
import signal
import sys
import sysconfig
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from importlib.metadata import version
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import TypeAdapter

from cadrumo.adapters.local_runtime.boot_record import (
    RuntimeBootRecord,
    RuntimeBootRecordPublication,
    RuntimeBootRecordUnavailable,
    read_runtime_boot_record,
)
from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.posix_endpoint import PosixRuntimeEndpoint
from cadrumo.adapters.local_runtime.tests.process_support import fixture_arguments, launch_fixture, native_python
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.application.runtime.contracts import RuntimeClientHello, RuntimeExitReason
from cadrumo.application.runtime.profile_access import RuntimeSessionRequest

from ..supervised_protocol import (
    MAX_LINE_BYTES,
    RuntimeAnnouncement,
    RuntimeHeartbeat,
    RuntimeReady,
    RuntimeRefused,
    RuntimeStopping,
    SupervisorLineRefusal,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.skipif(
        sys.platform not in {"win32", "linux", "darwin"}, reason="requires supported native installed runtime transport"
    ),
]

type _Endpoint = WindowsRuntimeEndpoint | PosixRuntimeEndpoint

# Cold bootstrap includes imports and public registry preparation before IPC.
_STARTUP_TIMEOUT_SECONDS = 60
_ANNOUNCEMENTS: TypeAdapter[RuntimeAnnouncement] = TypeAdapter(RuntimeAnnouncement)
_STREAMS_FIXTURE = "cadrumo.entrypoints.runtime.tests.supervised_streams_fixture"
_STILL_ACTIVE = 259


def _endpoint(root: Path) -> _Endpoint:
    if sys.platform == "win32":
        return WindowsRuntimeEndpoint(storage_root=root)
    return PosixRuntimeEndpoint(storage_root=root)


def _runtime_command(arguments: tuple[str, ...]) -> tuple[str, ...]:
    if sys.platform == "win32":
        # A development console launcher on Windows relaunches through
        # subprocess.run, which does not pass inherited pipes on. The packaged
        # host runs the isolated interpreter in one process; start that directly.
        return (str(native_python()), "-I", *fixture_arguments("cadrumo.entrypoints.runtime", *arguments))
    executable = Path(sysconfig.get_path("scripts")) / "cadrumo-runtime"
    assert executable.is_file(), "install the current project entrypoints before supervised acceptance"
    return (str(executable), *arguments)


async def _reap(process: asyncio.subprocess.Process) -> None:
    if process.returncode is None:
        if sys.platform == "win32":
            process.kill()
        else:
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
    await asyncio.wait_for(process.wait(), timeout=10)


@asynccontextmanager
async def _supervised(
    root: Path, identity: str, *, announcements: int | None = None
) -> AsyncIterator[asyncio.subprocess.Process]:
    environment = os.environ.copy()
    # Native IPC acceptance is independent of the test runner's desktop session.
    environment["CADRUMO_DEV_RUNTIME_SESSION_OVERRIDE"] = "1"
    environment["CADRUMO_LOG_DIR"] = str(root / "logs")
    arguments = (
        "--storage-root",
        str(root),
        "--storage-identity",
        identity,
        "--expected-version",
        version("cadrumo"),
        "--supervised",
    )
    process = await asyncio.create_subprocess_exec(
        *_runtime_command(arguments),
        cwd=root,
        env=environment,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE if announcements is None else announcements,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=sys.platform != "win32",
    )
    try:
        yield process
    finally:
        await _reap(process)


def _parse(line: bytes) -> RuntimeAnnouncement:
    assert line.endswith(b"\n") and len(line) <= MAX_LINE_BYTES, line
    return _ANNOUNCEMENTS.validate_json(line[:-1], strict=True)


async def _announcement(process: asyncio.subprocess.Process, *, timeout: float = 10) -> RuntimeAnnouncement:
    assert process.stdout is not None and process.stderr is not None
    line = await asyncio.wait_for(process.stdout.readline(), timeout=timeout)
    if not line:
        # Only text written before the streams were rewired can appear here.
        startup = await asyncio.wait_for(process.stderr.read(), timeout=timeout)
        pytest.fail(f"the runtime ended its announcements early; startup stderr: {startup[-4000:]!r}")
    return _parse(line)


async def _ready(process: asyncio.subprocess.Process) -> RuntimeReady:
    ready = await _announcement(process, timeout=_STARTUP_TIMEOUT_SECONDS)
    assert isinstance(ready, RuntimeReady)
    return ready


async def _send(process: asyncio.subprocess.Process, line: bytes) -> None:
    assert process.stdin is not None
    process.stdin.write(line)
    await process.stdin.drain()


async def _exit_code(process: asyncio.subprocess.Process) -> int:
    return await asyncio.wait_for(process.wait(), timeout=_STARTUP_TIMEOUT_SECONDS)


async def _remaining_output(process: asyncio.subprocess.Process) -> tuple[bytes, bytes]:
    assert process.stdout is not None and process.stderr is not None
    output, errors = await asyncio.wait_for(
        asyncio.gather(process.stdout.read(), process.stderr.read()), timeout=_STARTUP_TIMEOUT_SECONDS
    )
    return output, errors


def _connect(endpoint: _Endpoint) -> VerifiedRuntimeConnection:
    return VerifiedRuntimeConnection(
        endpoint.connect(timeout=2),
        expected=RuntimeClientHello(product_version=version("cadrumo"), storage_identity=endpoint.storage_identity),
        deadline=time.monotonic() + 5,
    )


def _boot_of(client: VerifiedRuntimeConnection) -> UUID:
    request = RuntimeSessionRequest(action="session_status", request_id=uuid4(), profile_id=uuid4(), session_id=uuid4())
    return client.session(request, deadline=time.monotonic() + 3).runtime_boot_id


def _windows_creation_milliseconds(pid: int) -> int:
    """Read a live process's creation time through pywin32 as whole milliseconds of FILETIME ticks."""
    import win32api
    import win32process

    # PROCESS_QUERY_LIMITED_INFORMATION observes without a termination right.
    handle = win32api.OpenProcess(0x1000, False, pid)
    try:
        created = win32process.GetProcessTimes(handle)["CreationTime"]
    finally:
        win32api.CloseHandle(handle)
    assert isinstance(created, datetime.datetime)
    elapsed = created - datetime.datetime(1601, 1, 1, tzinfo=datetime.UTC)
    return ((elapsed.days * 86_400 + elapsed.seconds) * 10_000_000 + elapsed.microseconds * 10) // 10_000


def _assert_boot_record_names(root: Path, ready: RuntimeReady) -> None:
    record = read_runtime_boot_record(storage_root=root)
    assert isinstance(record, RuntimeBootRecord)
    assert (record.boot_id, record.pid, record.version, record.admission) == (
        ready.boot_id,
        ready.pid,
        ready.version,
        ready.admission,
    )
    # A source checkout is not a versioned package.
    assert record.package_directory is None
    if sys.platform == "win32":
        # pywin32 truncates the kernel creation time to milliseconds.
        assert record.process_created // 10_000 == _windows_creation_milliseconds(ready.pid)


@pytest.mark.asyncio
async def test_ready_heartbeat_and_stop_reach_only_the_supervisor(tmp_path: Path) -> None:
    endpoint = _endpoint(tmp_path)
    earlier = RuntimeBootRecord(
        boot_id=uuid4(),
        pid=1,
        process_created=1,
        version=version("cadrumo"),
        package_directory=None,
        admission="native",
    )
    # An earlier boot that ended without cleanup left its record behind.
    assert RuntimeBootRecordPublication(storage_root=tmp_path, record=earlier).publish()
    try:
        async with _supervised(tmp_path, endpoint.storage_identity) as process:
            ready = await _ready(process)
            assert ready.pid == process.pid
            assert ready.version == version("cadrumo")
            assert ready.storage_identity == endpoint.storage_identity
            assert ready.admission == "development"
            # The record is in place, and replaced, when ready is observed.
            _assert_boot_record_names(tmp_path, ready)
            client = _connect(endpoint)
            try:
                assert _boot_of(client) == ready.boot_id
                await _send(process, b'{"type":"ping","seq":7}\n')
                heartbeat = await _announcement(process)
                assert isinstance(heartbeat, RuntimeHeartbeat)
                assert heartbeat.seq == 7
                assert heartbeat.tick_age_ms is not None and heartbeat.tick_age_ms < 5000
                assert heartbeat.frontends == 1
                assert heartbeat.in_flight_operations == 0
            finally:
                client.close()
            await _send(process, b'{"type":"stop"}\n')
            assert await _announcement(process) == RuntimeStopping(reason=RuntimeExitReason.SUPERVISOR_STOP)
            assert await _exit_code(process) == RuntimeExitReason.SUPERVISOR_STOP
            # Diagnostics went to the redacted log; the launcher received none.
            assert await _remaining_output(process) == (b"", b"")
            # A clean exit removes the record.
            assert read_runtime_boot_record(storage_root=tmp_path) is RuntimeBootRecordUnavailable.ABSENT
    finally:
        endpoint.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("command", "reason"),
    [
        (b'{"type":"stop-if-idle"}\n', RuntimeExitReason.SUPERVISOR_STOP),
        (b'{"type":"session-end"}\n', RuntimeExitReason.SESSION_END_SETTLE),
    ],
)
async def test_an_idle_runtime_stops_for_stop_if_idle_and_session_end(
    tmp_path: Path, command: bytes, reason: RuntimeExitReason
) -> None:
    endpoint = _endpoint(tmp_path)
    try:
        async with _supervised(tmp_path, endpoint.storage_identity) as process:
            _assert_boot_record_names(tmp_path, await _ready(process))
            await _send(process, command)
            assert await _announcement(process) == RuntimeStopping(reason=reason)
            assert await _exit_code(process) == reason
            assert await _remaining_output(process) == (b"", b"")
            assert read_runtime_boot_record(storage_root=tmp_path) is RuntimeBootRecordUnavailable.ABSENT
    finally:
        endpoint.close()


@pytest.mark.asyncio
async def test_lines_outside_the_grammar_are_refused_and_the_channel_stays_open(tmp_path: Path) -> None:
    endpoint = _endpoint(tmp_path)
    malformed = (
        b"not json\n",
        b'{"type":"ping","seq":1,"extra":true}\n',
        b'{"type":"ping","seq":1,"seq":2}\n',
        b'{"type":"ping","seq":true}\n',
        b'{"type":"reboot"}\n',
        b"\n",
    )
    try:
        async with _supervised(tmp_path, endpoint.storage_identity) as process:
            await _ready(process)
            for line in malformed:
                await _send(process, line)
                assert await _announcement(process) == RuntimeRefused(code=SupervisorLineRefusal.MALFORMED)
            await _send(process, b'{"type":"ping","seq":1' + b" " * (4 * MAX_LINE_BYTES) + b"}\n")
            assert await _announcement(process) == RuntimeRefused(code=SupervisorLineRefusal.OVERSIZED)
            await _send(process, b'{"type":"ping","seq":9}\n')
            heartbeat = await _announcement(process)
            assert isinstance(heartbeat, RuntimeHeartbeat) and heartbeat.seq == 9
            await _send(process, b'{"type":"stop"}\n')
            assert await _announcement(process) == RuntimeStopping(reason=RuntimeExitReason.SUPERVISOR_STOP)
            assert await _exit_code(process) == RuntimeExitReason.SUPERVISOR_STOP
    finally:
        endpoint.close()


@pytest.mark.asyncio
async def test_end_of_input_keeps_the_runtime_serving(tmp_path: Path) -> None:
    endpoint = _endpoint(tmp_path)
    try:
        async with _supervised(tmp_path, endpoint.storage_identity) as process:
            ready = await _ready(process)
            assert process.stdin is not None
            process.stdin.close()
            await asyncio.sleep(1)
            assert process.returncode is None
            client = _connect(endpoint)
            try:
                assert _boot_of(client) == ready.boot_id
            finally:
                client.close()
            assert process.returncode is None
            if sys.platform != "win32":
                # OS stop signals still reach the drain after the supervisor left.
                process.send_signal(signal.SIGTERM)
                assert await _announcement(process) == RuntimeStopping(reason=RuntimeExitReason.SIGNAL_STOP)
                assert await _exit_code(process) == RuntimeExitReason.SIGNAL_STOP
    finally:
        endpoint.close()


def _read_line(descriptor: int) -> bytes:
    line = b""
    while not line.endswith(b"\n"):
        chunk = os.read(descriptor, 1)
        if not chunk:
            break
        line += chunk
    return line


@pytest.mark.asyncio
async def test_a_lost_announcement_reader_changes_no_exit_code(tmp_path: Path) -> None:
    endpoint = _endpoint(tmp_path)
    reader, writer = os.pipe()
    try:
        async with _supervised(tmp_path, endpoint.storage_identity, announcements=writer) as process:
            os.close(writer)
            writer = -1
            line = await asyncio.wait_for(asyncio.to_thread(_read_line, reader), timeout=_STARTUP_TIMEOUT_SECONDS)
            assert isinstance(_parse(line), RuntimeReady)
            # The supervisor stops reading; each later announcement meets a broken pipe.
            os.close(reader)
            reader = -1
            for seq in range(3):
                await _send(process, b'{"type":"ping","seq":%d}\n' % seq)
            await asyncio.sleep(0.5)
            await _send(process, b'{"type":"stop"}\n')
            assert await _exit_code(process) == RuntimeExitReason.SUPERVISOR_STOP
    finally:
        for descriptor in (reader, writer):
            if descriptor >= 0:
                os.close(descriptor)
        endpoint.close()


def _alive(pid: int) -> bool:
    if sys.platform == "win32":
        import pywintypes
        import win32api
        import win32process

        try:
            # PROCESS_QUERY_LIMITED_INFORMATION observes without a termination right.
            handle = win32api.OpenProcess(0x1000, False, pid)
        except pywintypes.error:
            return False
        try:
            return win32process.GetExitCodeProcess(handle) == _STILL_ACTIVE
        finally:
            win32api.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _log_text(root: Path) -> str:
    return "".join(path.read_text(encoding="utf-8") for path in (root / "logs").rglob("*") if path.is_file())


async def _published_result(root: Path) -> dict[str, object]:
    deadline = time.monotonic() + 10
    while not (root / "result.json").exists():
        assert time.monotonic() < deadline, "the stream fixture did not publish its result"
        await asyncio.sleep(0.02)
    loaded: object = json.loads((root / "result.json").read_text(encoding="ascii"))
    assert isinstance(loaded, dict)
    return {str(key): value for key, value in loaded.items()}


async def _end(process: asyncio.subprocess.Process) -> None:
    if process.returncode is None:
        process.kill()
    await asyncio.wait_for(process.wait(), timeout=10)


def _end_descendants(pids: list[int]) -> None:
    for pid in pids:
        if _alive(pid):
            os.kill(pid, signal.SIGTERM)


@pytest.mark.asyncio
async def test_descendants_and_stray_writes_cannot_reach_the_protocol_streams(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CADRUMO_LOG_DIR", str(tmp_path / "logs"))
    process = await launch_fixture(_STREAMS_FIXTURE, "streams", str(tmp_path))
    grandchildren: list[int] = []
    try:
        # End of file arrives while the fixture waits for release and its
        # grandchild still runs, so no descendant holds either pipe.
        output, errors = await _remaining_output(process)
        result = await _published_result(tmp_path)
        grandchild = int(str(result["grandchild"]))
        grandchildren.append(grandchild)
        assert process.returncode is None and _alive(grandchild)
        assert output == b'{"type":"busy"}\n'
        assert errors == b""
        assert result["inheritable"] == [False] * (4 if sys.platform == "win32" else 2)
        (tmp_path / "release").write_text("go", encoding="ascii")
        assert await asyncio.wait_for(process.wait(), timeout=20) == 0
        log = _log_text(tmp_path)
        assert "ZeroDivisionError" in log and "synthetic-failing-thread" in log
        assert "synthetic stray warning" in log
    finally:
        await _end(process)
        _end_descendants(grandchildren)


@pytest.mark.asyncio
async def test_an_unexpected_failure_reports_only_its_reason_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CADRUMO_LOG_DIR", str(tmp_path / "logs"))
    arguments = ("--storage-root", str(tmp_path), "--storage-identity", "0" * 64, "--expected-version", "synthetic")
    process = await launch_fixture(_STREAMS_FIXTURE, "failure", str(tmp_path), *arguments, "--supervised")
    try:
        output, errors = await _remaining_output(process)
        exit_code = await asyncio.wait_for(process.wait(), timeout=_STARTUP_TIMEOUT_SECONDS)
        assert exit_code == RuntimeExitReason.UNEXPECTED_FAILURE
        assert output == b'{"type":"stopping","reason":73}\n'
        assert errors == b""
        assert "LookupError" in _log_text(tmp_path)
    finally:
        await _end(process)


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform != "win32", reason="only a Windows token carries a UAC elevation type")
async def test_a_fully_elevated_token_is_refused_before_the_runtime_owner_starts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CADRUMO_LOG_DIR", str(tmp_path / "logs"))
    arguments = ("--storage-root", str(tmp_path), "--storage-identity", "0" * 64, "--expected-version", "synthetic")
    process = await launch_fixture(_STREAMS_FIXTURE, "elevated", str(tmp_path), *arguments, "--supervised")
    try:
        output, errors = await _remaining_output(process)
        exit_code = await asyncio.wait_for(process.wait(), timeout=_STARTUP_TIMEOUT_SECONDS)
        assert exit_code == RuntimeExitReason.ELEVATED_TOKEN_REFUSED
        assert output == b'{"type":"stopping","reason":72}\n'
        assert errors == b""
        # The owner that claims the endpoint was never reached.
        assert not (tmp_path / "owner-reached").exists()
        assert "refused a full UAC-elevated token" in _log_text(tmp_path)
    finally:
        await _end(process)
