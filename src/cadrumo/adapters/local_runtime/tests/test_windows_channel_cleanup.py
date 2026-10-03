"""Portable native-port faults exercise Windows channel release ownership."""

from __future__ import annotations

import sys
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path
from threading import Event, Lock
from types import ModuleType

import pytest

from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.core.async_cleanup import AsyncResourceCleanupError

from .. import windows_channel, windows_login
from ..runtime_transport_cleanup import RuntimeTransportCleanup

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


class _Handle:
    def __init__(self, value: int) -> None:
        self.value = value
        self.released = False
        self.failures: list[OSError] = []
        self.entered: Event | None = None
        self.release: Event | None = None
        self.attempts = 0
        self._lock = Lock()
        self._closing = False
        self.Close: Callable[[], None] = self.close

    def __int__(self) -> int:
        return self.value

    def close(self) -> None:
        with self._lock:
            if self.released or self._closing:
                raise AssertionError("native owner was released twice or concurrently")
            self._closing = True
            self.attempts += 1
        try:
            if self.entered is not None:
                self.entered.set()
            if self.release is not None:
                assert self.release.wait(5), "native release was not allowed to finish"
            if self.failures:
                raise self.failures.pop(0)
            self.released = True
        finally:
            with self._lock:
                self._closing = False


class _KernelPort(ModuleType):
    def __init__(self, pipe: _Handle, peer: _Handle) -> None:
        super().__init__("win32api")
        self.pipe = pipe
        self.peer = peer
        self.OpenProcess = self.open_process
        self.CloseHandle = self.close_handle

    def open_process(self, flags: int, inherit: bool, pid: int) -> _Handle:
        assert flags > 0 and not inherit and pid == 71
        return self.peer

    def close_handle(self, value: int) -> None:
        assert value == int(self.pipe)
        self.pipe.Close()


class _PipePort(ModuleType):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.GetNamedPipeClientProcessId = self.client_process_id

    def client_process_id(self, handle: int) -> int:
        assert handle == 41
        return 71


class _EventPort(ModuleType):
    WAIT_TIMEOUT = 258

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.WaitForSingleObject = self.wait_for_single_object

    def wait_for_single_object(self, handle: int, timeout: int) -> int:
        assert handle == 51 and timeout == 0
        return self.WAIT_TIMEOUT


class _KernelError(Exception):
    pass


class _WinTypes(ModuleType):
    error = _KernelError


def _channel(
    monkeypatch: pytest.MonkeyPatch, *, integer_pipe: bool = False
) -> tuple[windows_channel.WindowsRuntimeChannel, _Handle, _Handle]:
    pipe, peer = _Handle(41), _Handle(51)
    for name, module in (
        ("win32api", _KernelPort(pipe, peer)),
        ("win32pipe", _PipePort("win32pipe")),
        ("win32event", _EventPort("win32event")),
        ("pywintypes", _WinTypes("pywintypes")),
    ):
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr(windows_channel, "require_windows", lambda: None)
    monkeypatch.setattr(windows_channel, "windows_owner_sid", lambda process: "fixture-owner")
    monkeypatch.setattr(windows_channel, "current_windows_owner_sid", lambda: "fixture-owner")
    monkeypatch.setattr(windows_channel, "windows_image_path", lambda process: Path("fixture-image"))
    return windows_channel.WindowsRuntimeChannel(int(pipe) if integer_pipe else pipe, server=True), pipe, peer


@pytest.mark.parametrize("integer_pipe", [False, True])
def test_concurrent_closers_release_each_native_owner_once(monkeypatch: pytest.MonkeyPatch, integer_pipe: bool) -> None:
    channel, pipe, peer = _channel(monkeypatch, integer_pipe=integer_pipe)
    pipe.entered, pipe.release = Event(), Event()
    second_started = Event()

    def second_close() -> None:
        second_started.set()
        channel.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(channel.close)
        try:
            assert pipe.entered.wait(5)
            second = executor.submit(second_close)
            assert second_started.wait(5)
            with pytest.raises(TimeoutError):
                second.result(timeout=0.1)
        finally:
            pipe.release.set()
        first.result(timeout=5)
        second.result(timeout=5)
    assert pipe.released and peer.released
    channel.close()
    assert pipe.attempts == peer.attempts == 1


@pytest.mark.parametrize("failure", ["pipe", "peer", "both"])
def test_failed_release_retries_only_unreleased_native_owners(monkeypatch: pytest.MonkeyPatch, failure: str) -> None:
    channel, pipe, peer = _channel(monkeypatch)
    pipe_error, peer_error = OSError("synthetic pipe refusal"), OSError("synthetic peer refusal")
    if failure in {"pipe", "both"}:
        pipe.failures.append(pipe_error)
    if failure in {"peer", "both"}:
        peer.failures.append(peer_error)
    with pytest.raises(OSError) as caught:
        channel.close()
    assert caught.value is (peer_error if failure == "peer" else pipe_error)
    assert pipe.released is (failure == "peer")
    assert peer.released is (failure == "pipe")
    assert pipe.attempts == peer.attempts == 1
    channel.close()
    assert pipe.released and peer.released
    channel.close()
    assert pipe.attempts == (1 if failure == "peer" else 2)
    assert peer.attempts == (1 if failure == "pipe" else 2)


def test_login_capture_keeps_peer_alive_until_capture_finishes(monkeypatch: pytest.MonkeyPatch) -> None:
    channel, pipe, peer = _channel(monkeypatch)
    entered, release, close_started = Event(), Event(), Event()
    binding = windows_login.WindowsLoginBinding("fixture-owner", 1, 2, 3)

    def capture(process: int, *, expected_owner: str) -> windows_login.WindowsLoginBinding:
        assert process == int(peer) and expected_owner == binding.os_owner_id
        assert not peer.released
        entered.set()
        assert release.wait(5)
        assert not peer.released
        return binding

    def close() -> None:
        close_started.set()
        channel.close()

    monkeypatch.setattr(windows_login, "capture_windows_login", capture)
    with ThreadPoolExecutor(max_workers=2) as executor:
        captured = executor.submit(channel.capture_login)
        try:
            assert entered.wait(5)
            closed = executor.submit(close)
            assert close_started.wait(5)
            with pytest.raises(TimeoutError):
                closed.result(timeout=0.1)
        finally:
            release.set()
        assert captured.result(timeout=5) is binding
        closed.result(timeout=5)
    assert pipe.released and peer.released
    with pytest.raises(RuntimeRefusalError) as caught:
        channel.capture_login()
    assert caught.value.reason is RuntimeRefusalCode.CONNECTION_CLOSED


def test_constructor_refusal_releases_pipe_and_retained_peer(monkeypatch: pytest.MonkeyPatch) -> None:
    channel, _, _ = _channel(monkeypatch)
    channel.close()
    pipe, peer = _Handle(41), _Handle(51)
    monkeypatch.setitem(sys.modules, "win32api", _KernelPort(pipe, peer))
    monkeypatch.setattr(windows_channel, "current_windows_owner_sid", lambda: "different-owner")
    with pytest.raises(RuntimeRefusalError) as caught:
        windows_channel.WindowsRuntimeChannel(pipe, server=True)
    assert caught.value.reason is RuntimeRefusalCode.PEER_UNTRUSTED
    assert pipe.released and peer.released


@pytest.mark.parametrize("admission", ["native", "typed", "body"])
@pytest.mark.parametrize("failure", ["pipe", "peer", "both"])
@pytest.mark.parametrize("persistent", [False, True])
@pytest.mark.asyncio
async def test_unreturned_channel_preserves_admission_error_and_retry_owner(
    monkeypatch: pytest.MonkeyPatch, admission: str, failure: str, persistent: bool
) -> None:
    channel, _, _ = _channel(monkeypatch)
    channel.close()
    pipe, peer = _Handle(41), _Handle(51)
    monkeypatch.setitem(sys.modules, "win32api", _KernelPort(pipe, peer))
    primary: BaseException
    if admission == "native":
        primary = _KernelError("synthetic native admission failure")
    elif admission == "typed":
        primary = RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
    else:
        primary = OSError("synthetic admission body failure")

    def refuse(process: object) -> str:
        raise primary

    monkeypatch.setattr(windows_channel, "windows_owner_sid", refuse)
    attempts = 2 if persistent else 1
    if failure in {"pipe", "both"}:
        pipe.failures.extend(OSError("synthetic pipe release failure") for _ in range(attempts))
    if failure in {"peer", "both"}:
        peer.failures.extend(OSError("synthetic peer release failure") for _ in range(attempts))
    with pytest.raises((RuntimeRefusalError, OSError)) as caught:
        windows_channel.WindowsRuntimeChannel(pipe, server=True)
    if admission == "native":
        assert isinstance(caught.value, RuntimeRefusalError)
        assert caught.value.reason is RuntimeRefusalCode.PEER_UNTRUSTED
        assert str(primary) not in str(caught.value)
        assert caught.value.__suppress_context__
    else:
        assert caught.value is primary
    cleanup = caught.value.__dict__.get("async_cleanup_error")
    assert isinstance(cleanup, AsyncResourceCleanupError)
    owner = caught.value.__dict__.get("_runtime_transport_cleanup")
    assert isinstance(owner, RuntimeTransportCleanup)
    retained_channel = owner.resource
    assert isinstance(retained_channel, windows_channel.WindowsRuntimeChannel)
    assert pipe.released is (failure == "peer")
    assert peer.released is (failure == "pipe")
    assert pipe.attempts == peer.attempts == 1
    if persistent:
        with pytest.raises(AsyncResourceCleanupError) as failed_retry:
            await cleanup.retry_cleanup()
        assert pipe.released is (failure == "peer")
        assert peer.released is (failure == "pipe")
        cleanup = failed_retry.value
    await cleanup.retry_cleanup()
    assert pipe.released and peer.released
    retained_channel.close()
    await cleanup.retry_cleanup()
    assert pipe.attempts == (1 if failure == "peer" else attempts + 1)
    assert peer.attempts == (1 if failure == "pipe" else attempts + 1)
