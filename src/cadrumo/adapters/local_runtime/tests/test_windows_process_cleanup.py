"""Actual Windows owners retain native fault-port handles and exact primaries."""

from __future__ import annotations

import asyncio
import ctypes.wintypes
import sys
from collections import Counter
from pathlib import Path
from threading import Event
from types import ModuleType, SimpleNamespace

import pytest

from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.core.async_cleanup import AsyncResourceCleanupError

from .. import windows_process
from ..windows_process import WindowsOwnedProcess, WindowsProcessScope, unreturned_windows_process_scope

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


class _NativeError(Exception):
    """An exact synthetic pywintypes failure, without requiring Windows."""


class _CreateJob:
    def __call__(self, *args: object) -> int:
        return 7


class _Native:
    def __init__(self) -> None:
        self.closed: Counter[int] = Counter()
        self.attempts: Counter[int] = Counter()
        self.close_failures: dict[int, int] = {}
        self.close_errors: dict[int, BaseException] = {}
        self.close_error = _NativeError("synthetic native handle release")
        self.terminate_error: BaseException | None = None
        self.setup_error: BaseException | None = None
        self.terminations = 0
        self.active = 0
        self.launches = 0
        self.entered = Event()
        self.finish = Event()
        self.block_termination = False

    def close(self, handle: int) -> None:
        self.attempts[handle] += 1
        if self.close_failures.get(handle, 0):
            self.close_failures[handle] -= 1
            raise self.close_errors.get(handle, self.close_error)
        self.closed[handle] += 1

    def set_handle_information(self, *args: object) -> None:
        if self.setup_error is not None:
            raise self.setup_error

    def query(self, handle: int, information: int) -> object:
        assert handle == 7
        if information == 1:
            return {"BasicLimitInformation": {"LimitFlags": 8192}}
        if information == 2:
            return {"ActiveProcesses": self.active}
        return (101, 102, 103) if self.active else ()

    def terminate(self, handle: int, code: int) -> None:
        assert handle == 7 and code == 1
        self.terminations += 1
        if self.block_termination:
            self.entered.set()
            if not self.finish.wait(timeout=5):
                raise AssertionError("native fault boundary was not released")
        if self.terminate_error is not None:
            raise self.terminate_error

    def launch(self, *args: object, **kwargs: object) -> tuple[int, int, int]:
        self.launches += 1
        return 100 + self.launches, 200 + self.launches, 1000 + self.launches


@pytest.fixture
def native(monkeypatch: pytest.MonkeyPatch) -> _Native:
    """Inject explicit C/native ports, never the actual global platform."""
    port = _Native()
    api = ModuleType("win32api")
    api.__dict__.update(CloseHandle=port.close, SetHandleInformation=port.set_handle_information)
    job = ModuleType("win32job")
    job.__dict__.update(
        QueryInformationJobObject=port.query,
        SetInformationJobObject=lambda *args: None,
        TerminateJobObject=port.terminate,
        JobObjectExtendedLimitInformation=1,
        JobObjectBasicAccountingInformation=2,
        JobObjectBasicProcessIdList=3,
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE=8192,
    )
    monkeypatch.setitem(sys.modules, "win32api", api)
    monkeypatch.setitem(sys.modules, "win32job", job)
    errors = ModuleType("pywintypes")
    errors.__dict__["error"] = _NativeError
    monkeypatch.setitem(sys.modules, "pywintypes", errors)
    monkeypatch.setattr(windows_process, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(windows_process, "wintypes", ctypes.wintypes, raising=False)
    monkeypatch.setattr(
        windows_process,
        "ctypes",
        SimpleNamespace(
            c_void_p=ctypes.c_void_p,
            WinDLL=lambda *args, **kwargs: SimpleNamespace(CreateJobObjectW=_CreateJob()),
        ),
    )
    monkeypatch.setattr(windows_process, "_launch_in_job", port.launch)
    return port


def _children(scope: WindowsProcessScope, tmp_path: Path, count: int = 3) -> list[WindowsOwnedProcess]:
    return [
        scope.launch(executable=Path(sys.executable), arguments=(), directory=tmp_path, environment={})
        for _ in range(count)
    ]


def _cleanup(error: BaseException) -> AsyncResourceCleanupError:
    attached = error.__dict__.get("async_cleanup_error")
    assert isinstance(attached, AsyncResourceCleanupError)
    return attached


def _assert_fenced(scope: WindowsProcessScope, tmp_path: Path, native: _Native) -> None:
    calls = native.launches
    with pytest.raises(RuntimeRefusalError) as refused:
        scope.launch(executable=Path(sys.executable), arguments=(), directory=tmp_path, environment={})
    assert refused.value.reason is RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE
    assert native.launches == calls


@pytest.mark.asyncio
@pytest.mark.parametrize("failures", [1, 2])
async def test_failed_job_release_attempts_each_child_and_retries_only_retained_handles(
    native: _Native, tmp_path: Path, failures: int
) -> None:
    scope = WindowsProcessScope()
    _children(scope, tmp_path)
    native.close_failures = {7: failures, 102: failures}
    with pytest.raises(AsyncResourceCleanupError) as caught:
        scope.terminate()
    assert caught.value.resources == (scope,)
    assert native.attempts == Counter({7: 1, 101: 1, 102: 1, 103: 1, 201: 1, 202: 1, 203: 1})
    assert native.closed == Counter({101: 1, 103: 1, 201: 1, 202: 1, 203: 1})
    assert scope.active_process_ids() == ()
    _assert_fenced(scope, tmp_path, native)
    if failures == 2:
        with pytest.raises(AsyncResourceCleanupError):
            await caught.value.retry_cleanup()
        assert native.closed == Counter({101: 1, 103: 1, 201: 1, 202: 1, 203: 1})
        _assert_fenced(scope, tmp_path, native)
    await caught.value.retry_cleanup()
    assert native.terminations == 1
    assert native.closed == Counter({7: 1, 101: 1, 102: 1, 103: 1, 201: 1, 202: 1, 203: 1})
    assert native.attempts[101] == native.attempts[103] == 1
    scope.terminate()
    await scope.close()
    assert native.closed == Counter({7: 1, 101: 1, 102: 1, 103: 1, 201: 1, 202: 1, 203: 1})
    _assert_fenced(scope, tmp_path, native)


@pytest.mark.asyncio
@pytest.mark.parametrize("primary_kind", ["typed", "native", "cancel", "timeout"])
async def test_unproven_termination_retains_job_and_exact_primary_until_proven_retry(
    native: _Native, tmp_path: Path, primary_kind: str
) -> None:
    scope = WindowsProcessScope()
    _children(scope, tmp_path)
    primary: BaseException | None = (
        RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        if primary_kind == "typed"
        else _NativeError("original native termination")
        if primary_kind == "native"
        else asyncio.CancelledError("original termination cancellation")
        if primary_kind == "cancel"
        else None
    )
    native.terminate_error = primary
    native.active = 3
    native.close_failures = {102: 1}
    with pytest.raises((RuntimeRefusalError, asyncio.CancelledError)) as caught:
        scope.terminate(timeout=0)
    if primary_kind == "native":
        assert isinstance(caught.value, RuntimeRefusalError)
        assert caught.value.reason is RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE
        assert caught.value.__cause__ is primary
    elif primary is not None:
        assert caught.value is primary
    else:
        assert isinstance(caught.value, RuntimeRefusalError)
        assert caught.value.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED
    retained = _cleanup(caught.value)
    assert retained.resources == (scope,)
    if primary_kind == "cancel":
        assert caught.value.__dict__["cleanup_error"] is retained
    assert native.attempts[7] == 0 and native.closed == Counter({101: 1, 103: 1, 201: 1, 202: 1, 203: 1})
    _assert_fenced(scope, tmp_path, native)
    with pytest.raises(RuntimeRefusalError):
        scope.active_process_ids()
    native.terminate_error = None
    native.active = 0
    await retained.retry_cleanup()
    assert native.terminations == 2
    assert native.closed == Counter({7: 1, 101: 1, 102: 1, 103: 1, 201: 1, 202: 1, 203: 1})
    assert native.attempts[101] == native.attempts[103] == 1
    assert scope.active_process_ids() == ()
    scope.terminate()
    assert native.terminations == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("primary_kind", ["typed", "native", "cancel"])
async def test_constructor_failure_preserves_primary_and_acquired_job_retry(native: _Native, primary_kind: str) -> None:
    primary = (
        RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        if primary_kind == "typed"
        else asyncio.CancelledError("constructor cancellation")
        if primary_kind == "cancel"
        else _NativeError("constructor failure")
    )
    native.setup_error = primary
    native.close_failures = {7: 1}
    with pytest.raises((RuntimeRefusalError, asyncio.CancelledError)) as caught:
        WindowsProcessScope()
    if primary_kind == "native":
        assert isinstance(caught.value, RuntimeRefusalError)
        assert caught.value.reason is RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE
        assert caught.value.__cause__ is primary
    else:
        assert caught.value is primary
    retained = _cleanup(caught.value)
    assert len(retained.resources) == 1 and isinstance(retained.resources[0], WindowsProcessScope)
    assert unreturned_windows_process_scope(caught.value) is retained.resources[0]
    assert native.terminations == 1 and native.attempts[7] == 1 and native.closed[7] == 0
    await retained.retry_cleanup()
    assert native.terminations == 1 and native.attempts[7] == 2 and native.closed[7] == 1
    await retained.resources[0].close()
    assert native.attempts[7] == 2


@pytest.mark.parametrize("primary_kind", ["typed", "native", "cancel"])
def test_constructor_failure_with_successful_release_exposes_no_unreturned_scope(
    native: _Native, primary_kind: str
) -> None:
    primary = (
        RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        if primary_kind == "typed"
        else asyncio.CancelledError("released constructor cancellation")
        if primary_kind == "cancel"
        else _NativeError("released constructor failure")
    )
    native.setup_error = primary
    with pytest.raises((RuntimeRefusalError, asyncio.CancelledError)) as caught:
        WindowsProcessScope()
    if primary_kind == "native":
        assert isinstance(caught.value, RuntimeRefusalError)
        assert caught.value.reason is RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE
        assert caught.value.__cause__ is primary
    else:
        assert caught.value is primary
    assert unreturned_windows_process_scope(caught.value) is None
    assert caught.value.__dict__.get("async_cleanup_error") is None
    assert native.terminations == 1 and native.attempts == native.closed == Counter({7: 1})


@pytest.mark.asyncio
async def test_async_close_preserves_original_native_cancellation_and_retry_owner(native: _Native) -> None:
    scope = WindowsProcessScope()
    primary = asyncio.CancelledError("native termination cancellation")
    native.terminate_error = primary
    with pytest.raises(asyncio.CancelledError) as caught:
        await scope.close()
    assert caught.value is primary
    retained = _cleanup(primary)
    assert retained.resources == (scope,)
    assert primary.__dict__["cleanup_error"] is retained
    assert native.attempts[7] == 0
    native.terminate_error = None
    await retained.retry_cleanup()
    assert native.closed[7] == 1


@pytest.mark.asyncio
async def test_caller_cancellation_settles_native_attempt_and_retains_original_scope(
    native: _Native, tmp_path: Path
) -> None:
    scope = WindowsProcessScope()
    _children(scope, tmp_path)
    native.block_termination = True
    native.terminate_error = _NativeError("unproven native termination while caller cancels")
    closing = asyncio.create_task(scope.close())
    try:
        assert await asyncio.to_thread(native.entered.wait, 2)
        closing.cancel("caller cancellation")
        native.finish.set()
        with pytest.raises(asyncio.CancelledError) as caught:
            await closing
        assert caught.value.args == ("caller cancellation",)
        retained = _cleanup(caught.value)
        assert caught.value.__dict__["cleanup_error"] is retained
        assert retained.resources == (scope,)
        assert native.attempts[7] == 0
        assert native.closed == Counter({101: 1, 102: 1, 103: 1, 201: 1, 202: 1, 203: 1})
        _assert_fenced(scope, tmp_path, native)
        native.block_termination = False
        native.terminate_error = None
        await retained.retry_cleanup()
        assert native.closed == Counter({7: 1, 101: 1, 102: 1, 103: 1, 201: 1, 202: 1, 203: 1})
        assert all(count == 1 for count in native.attempts.values())
    finally:
        native.finish.set()
        if not closing.done():
            await asyncio.gather(closing, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("process_also_fails", [False, True])
async def test_child_thread_release_failure_attempts_process_and_retains_only_failed_handles(
    native: _Native, tmp_path: Path, process_also_fails: bool
) -> None:
    scope = WindowsProcessScope()
    child = _children(scope, tmp_path, count=1)[0]
    native.close_errors[101] = _NativeError("distinct process release failure")
    native.close_failures = {201: 1, **({101: 1} if process_also_fails else {})}
    with pytest.raises(_NativeError) as original:
        child.close()
    assert original.value is native.close_error
    assert native.attempts == Counter({201: 1, 101: 1})
    assert native.closed == (Counter() if process_also_fails else Counter({101: 1}))
    # Persist the same failure at the scope boundary to expose its actual
    # canonical retry owner, without losing the child handles on either path.
    native.close_failures = {201: 1, **({101: 1} if process_also_fails else {})}
    with pytest.raises(AsyncResourceCleanupError) as retained:
        scope.terminate()
    assert retained.value.resources == (scope,)
    assert native.closed[7] == 1 and native.closed[201] == 0
    assert native.attempts[101] == (2 if process_also_fails else 1)
    _assert_fenced(scope, tmp_path, native)
    await retained.value.retry_cleanup()
    assert native.closed == Counter({7: 1, 101: 1, 201: 1})
    assert native.attempts == Counter({7: 1, 101: 3 if process_also_fails else 1, 201: 3})
    child.close()
    await scope.close()
    assert native.closed == Counter({7: 1, 101: 1, 201: 1})
