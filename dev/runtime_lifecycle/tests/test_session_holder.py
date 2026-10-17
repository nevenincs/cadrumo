"""Exercise bounded holder pipes and both process-lifecycle owners."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import BinaryIO, Literal, cast
from uuid import UUID

import pytest

from .. import session_holder
from ..caller_owned_root import AcceptanceError
from ..session_holder import AsyncRuntimeSessionHolder, WindowsRuntimeSessionHolder, _AsyncPipeOwner

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("23f5ef9e-0a14-48c4-83f1-50cb8e96d9e4")
_SESSION = "ce137879-4c2c-477a-96a6-034c8d7d9d10"
_BOOT = "ab12599e-ce53-4d72-a0cc-e177ed7415a0"
_CONNECTION = "709c2e1f-0482-42d7-94be-bec9ce38be49"
_PASSWORD = b"holder-test-password"


def _protocol_child(
    *, identity_profile: str | None = None, wait_forever: bool = False, wait_before_identity: bool = False
) -> str:
    profile = str(_PROFILE) if identity_profile is None else identity_profile
    finish = "time.sleep(30)" if wait_forever else ""
    startup = "time.sleep(30)" if wait_before_identity else ""
    return f"""
import json, struct, sys, time
profile = {profile!r}
session = {_SESSION!r}
boot = {_BOOT!r}
connection = {_CONNECTION!r}
sys.stderr.buffer.write(b'x' * 262144)
sys.stderr.flush()
if 'with-password' in sys.argv[1:]:
    length = struct.unpack('!I', sys.stdin.buffer.read(4))[0]
    password = sys.stdin.buffer.read(length)
    if length != {len(_PASSWORD)} or password != {_PASSWORD!r}:
        raise SystemExit(19)
{startup}
def send(document):
    sys.stdout.buffer.write(json.dumps(document, separators=(',', ':')).encode() + b'\\n')
    sys.stdout.buffer.flush()
send({{'kind': 'session_held', 'profile_id': profile, 'session_id': session,
      'runtime_boot_id': boot, 'connection_id': connection,
      'frontend_mode': 'cli' if sys.argv[-2:] == ['--frontend', 'cli'] else 'desktop'}})
{finish}
for frame in sys.stdin.buffer:
    request = json.loads(frame)
    action = request['action']
    reply = {{'request_id': request['request_id'], 'runtime_boot_id': boot, 'connection_id': connection}}
    if action == 'attendance_inventory':
        reply.update(kind='attendance_inventory', profile_id=profile, candidates=[])
    elif action == 'close':
        reply['kind'] = 'session_closed'
        send(reply)
        break
    else:
        reply['kind'] = 'command_acknowledged'
    send(reply)
"""


def _patch_launcher(
    monkeypatch: pytest.MonkeyPatch,
    *,
    identity_profile: str | None = None,
    wait_forever: bool = False,
    wait_before_identity: bool = False,
) -> None:
    script = _protocol_child(
        identity_profile=identity_profile,
        wait_forever=wait_forever,
        wait_before_identity=wait_before_identity,
    )

    def launch(
        _runtime: Path, _profile_id: UUID, _environment: dict[str, str], password: bytearray | None
    ) -> tuple[Path, tuple[str, ...]]:
        arguments = ("-u", "-c", script, *(("with-password",) if password is not None else ()))
        return Path(sys.executable).resolve(strict=True), arguments

    monkeypatch.setattr(session_holder, "_holder_launch", launch)


def _test_environment() -> dict[str, str]:
    return {
        name: value for name in ("PATH", "SYSTEMROOT", "TEMP", "TMP") if (value := os.environ.get(name)) is not None
    }


@pytest.mark.asyncio
async def test_async_holder_correlates_real_pipe_replies_and_drains_stderr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_launcher(monkeypatch)
    password = bytearray(_PASSWORD)
    holder = await AsyncRuntimeSessionHolder.start(
        Path(sys.executable), profile_id=_PROFILE, environment=_test_environment(), password=password
    )

    assert password == bytearray(len(_PASSWORD))
    assert holder.identity["kind"] == "session_held"
    assert holder.identity["profile_id"] == str(_PROFILE)
    inventory = await holder.command("attendance_inventory")
    assert inventory == {
        "kind": "attendance_inventory",
        "profile_id": str(_PROFILE),
        "candidates": [],
        "request_id": inventory["request_id"],
        "runtime_boot_id": _BOOT,
        "connection_id": _CONNECTION,
    }
    assert inventory["request_id"]
    closed = await holder.command("close")
    assert closed["kind"] == "session_closed"
    owner = holder._owner
    await holder.close()

    assert owner is not None
    assert owner.process.returncode == 0
    assert owner._stderr_task.done()


@pytest.mark.asyncio
async def test_async_startup_refusal_reaps_the_exact_child(monkeypatch: pytest.MonkeyPatch) -> None:
    wrong_profile = "a9f239ad-e202-49d9-bf2a-e20a4be0ea15"
    _patch_launcher(monkeypatch, identity_profile=wrong_profile)
    owners: list[_AsyncPipeOwner] = []
    original_launch = _AsyncPipeOwner.launch

    async def observe_launch(
        cls: type[_AsyncPipeOwner], executable: Path, arguments: tuple[str, ...], environment: dict[str, str]
    ) -> _AsyncPipeOwner:
        owner = await original_launch(executable, arguments, environment)
        owners.append(owner)
        return owner

    monkeypatch.setattr(_AsyncPipeOwner, "launch", classmethod(observe_launch))

    with pytest.raises(AcceptanceError, match="holder profile identity differs"):
        await AsyncRuntimeSessionHolder.start(
            Path(sys.executable), profile_id=_PROFILE, environment=_test_environment()
        )

    assert len(owners) == 1
    assert owners[0].process.returncode == 0
    assert owners[0]._stderr_task.done()


@pytest.mark.asyncio
async def test_async_close_terminates_a_child_that_ignores_stdin_eof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(session_holder, "_CLOSE_SECONDS", 0.05)
    owner = await _AsyncPipeOwner.launch(
        Path(sys.executable).resolve(strict=True),
        ("-u", "-c", "import time; time.sleep(30)"),
        os.environ,
    )

    await owner.close()

    assert owner.process.returncode is not None
    assert owner._stderr_task.done()


@pytest.mark.asyncio
async def test_async_close_retries_stdin_wait_while_stream_is_already_closing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(session_holder, "_CLOSE_SECONDS", 0.05)
    owner = await _AsyncPipeOwner.launch(
        Path(sys.executable).resolve(strict=True),
        ("-u", "-c", "import sys; sys.stdin.buffer.read()"),
        os.environ,
    )
    stream = owner.process.stdin
    assert stream is not None
    original_wait_closed = stream.wait_closed
    calls = 0

    async def fail_once() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            await asyncio.sleep(0.1)
        await original_wait_closed()

    monkeypatch.setattr(stream, "wait_closed", fail_once)

    with pytest.raises(BaseExceptionGroup) as stdin_failure:
        await owner.close()

    assert any("stdin did not close" in str(error) for error in stdin_failure.value.exceptions)
    assert stream.is_closing()
    assert not owner._closed
    await owner.close()

    assert calls == 2
    assert owner._closed
    assert owner.process.returncode is not None


@pytest.mark.asyncio
async def test_async_close_retains_owner_until_stderr_drainer_finishes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(session_holder, "_CLOSE_SECONDS", 0.05)
    owner = await _AsyncPipeOwner.launch(
        Path(sys.executable).resolve(strict=True),
        ("-u", "-c", "import sys; sys.stdin.buffer.read()"),
        os.environ,
    )
    original_stderr_task = owner._stderr_task
    gate = asyncio.Event()

    async def wait_for_stderr_release() -> None:
        await gate.wait()

    delayed_stderr_task = asyncio.create_task(wait_for_stderr_release())
    owner._stderr_task = delayed_stderr_task

    with pytest.raises(BaseExceptionGroup) as stderr_failure:
        await owner.close()

    assert any("stderr drainer did not stop" in str(error) for error in stderr_failure.value.exceptions)
    assert owner.process.returncode is not None
    assert not owner._closed
    gate.set()
    await original_stderr_task
    await delayed_stderr_task
    await owner.close()

    assert owner._closed


@pytest.mark.asyncio
async def test_cancelling_start_waits_for_spawn_then_reaps_the_child(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(session_holder, "_CLOSE_SECONDS", 0.05)
    _patch_launcher(monkeypatch, wait_before_identity=True)
    launched = asyncio.Event()
    owners: list[_AsyncPipeOwner] = []
    original_launch = _AsyncPipeOwner.launch

    async def observe_launch(
        cls: type[_AsyncPipeOwner], executable: Path, arguments: tuple[str, ...], environment: dict[str, str]
    ) -> _AsyncPipeOwner:
        owner = await original_launch(executable, arguments, environment)
        owners.append(owner)
        launched.set()
        return owner

    monkeypatch.setattr(_AsyncPipeOwner, "launch", classmethod(observe_launch))
    starting = asyncio.create_task(
        AsyncRuntimeSessionHolder.start(Path(sys.executable), profile_id=_PROFILE, environment=_test_environment())
    )
    await asyncio.wait_for(launched.wait(), timeout=5)
    starting.cancel()

    with pytest.raises(asyncio.CancelledError):
        await starting

    assert len(owners) == 1
    assert owners[0].process.returncode is not None
    assert owners[0]._stderr_task.done()


@pytest.mark.windows_only
@pytest.mark.parametrize("frontend", ["desktop", "cli"])
def test_windows_holder_owns_correlated_pipe_session_and_cleans_threads(
    monkeypatch: pytest.MonkeyPatch, frontend: Literal["desktop", "cli"]
) -> None:
    _patch_launcher(monkeypatch)
    password = bytearray(_PASSWORD)
    holder = WindowsRuntimeSessionHolder(
        Path(sys.executable),
        profile_id=_PROFILE,
        environment=_test_environment(),
        password=password,
        frontend=frontend,
    )

    assert password == bytearray(len(_PASSWORD))
    assert holder.identity["kind"] == "session_held"
    assert holder.identity["frontend_mode"] == frontend
    inventory = holder.command("attendance_inventory")
    assert inventory["kind"] == "attendance_inventory"
    assert inventory["profile_id"] == str(_PROFILE)
    assert inventory["runtime_boot_id"] == _BOOT
    closed = holder.command("close")
    assert closed["kind"] == "session_closed"
    holder.close()

    assert holder._closed
    assert holder._stdout_thread is not None and not holder._stdout_thread.is_alive()
    assert holder._stderr_thread is not None and not holder._stderr_thread.is_alive()


@pytest.mark.windows_only
def test_windows_holder_job_terminates_and_reaps_an_unresponsive_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(session_holder, "_CLOSE_SECONDS", 0.05)
    _patch_launcher(monkeypatch, wait_forever=True)
    holder = WindowsRuntimeSessionHolder(Path(sys.executable), profile_id=_PROFILE, environment=_test_environment())

    holder.close()

    assert holder._closed
    assert holder._process is not None
    assert holder._stdout_thread is not None and not holder._stdout_thread.is_alive()
    assert holder._stderr_thread is not None and not holder._stderr_thread.is_alive()


@pytest.mark.windows_only
def test_windows_holder_times_out_blocked_write_by_terminating_job_before_pipe_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(session_holder, "_WRITE_SECONDS", 0.05)
    monkeypatch.setattr(session_holder, "_CLOSE_SECONDS", 0.05)
    _patch_launcher(monkeypatch, wait_forever=True)
    holder = WindowsRuntimeSessionHolder(Path(sys.executable), profile_id=_PROFILE, environment=_test_environment())
    scope = holder._scope
    assert scope is not None

    with pytest.raises(AcceptanceError, match="runtime holder input timed out"):
        holder.command("unread", payload="x" * 15_000)

    assert holder._closed
    assert scope._terminated
    assert scope._job is None
    assert holder._writer_thread is None
    assert holder._stdin is not None and holder._stdin.closed
    assert holder._stdout_thread is not None and not holder._stdout_thread.is_alive()
    assert holder._stderr_thread is not None and not holder._stderr_thread.is_alive()


@pytest.mark.windows_only
def test_windows_holder_retries_a_failed_stdin_close(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(session_holder, "_CLOSE_SECONDS", 0.05)
    _patch_launcher(monkeypatch)
    holder = WindowsRuntimeSessionHolder(Path(sys.executable), profile_id=_PROFILE, environment=_test_environment())
    stream = holder._stdin
    assert stream is not None

    class FailOnceClose:
        def __init__(self, owned: BinaryIO) -> None:
            self.owned = owned
            self.failed = False

        @property
        def closed(self) -> bool:
            return bool(self.owned.closed)

        def close(self) -> None:
            if not self.failed:
                self.failed = True
                raise OSError("controlled first close failure")
            self.owned.close()

    retryable_stream = FailOnceClose(stream)
    holder._stdin = cast("BinaryIO", retryable_stream)

    with pytest.raises(OSError, match="controlled first close failure"):
        holder.close()

    assert not holder._closed
    assert not retryable_stream.closed
    holder.close()

    assert holder._closed
    assert retryable_stream.closed
