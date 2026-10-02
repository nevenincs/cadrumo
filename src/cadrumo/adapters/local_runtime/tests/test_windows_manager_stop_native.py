"""Bounded native experiment for per-user Task Scheduler stop behavior."""

from __future__ import annotations

import asyncio
import ctypes
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Generator
from concurrent.futures import Future
from contextlib import contextmanager
from contextvars import ContextVar
from importlib.metadata import version
from pathlib import Path
from threading import Lock, Thread
from typing import Protocol, TypedDict, cast
from uuid import uuid4
from xml.etree import ElementTree

import pytest
from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import fromstring

from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.service_definitions import runtime_service_name, windows_task_xml
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.local_runtime.windows_manager import (
    WindowsTaskManager,
    _task_xml_definition_matches,
    windows_task_binding_matches,
)
from cadrumo.application.runtime.contracts import RuntimeClientHello, RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.management import RuntimeServiceBinding
from cadrumo.application.runtime.owner_control import (
    RuntimeStopAccepted,
    RuntimeStopConfirm,
    RuntimeStopPreview,
    RuntimeStopPreviewRequest,
)
from cadrumo.application.runtime.profile_access import PROFILE_ADMISSION_TIMEOUT_SECONDS
from cadrumo.core.async_cleanup import AsyncResourceCleanupError, close_async_resources

_TASK_NAMESPACE = "{http://schemas.microsoft.com/windows/2004/02/mit/task}"
_TASK_CREATE = 2
_TASK_LOGON_INTERACTIVE_TOKEN = 3
_STOP_OBSERVATION_SECONDS = 67
_TASK_RUNNING = 4
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_SYNCHRONIZE = 0x00100000
_WAIT_TIMEOUT = 0x00000102
_WINDOWS_DLL_LOADER = "WinDLL"


class _Event(TypedDict):
    at_ns: int
    kind: str
    pid: int
    start: str


class _RegisteredTask(Protocol):
    Xml: str
    State: int

    Run: Callable[[object], object]
    Stop: Callable[[int], None]


class _TaskFolder(Protocol):
    GetTask: Callable[[str], _RegisteredTask]
    RegisterTask: Callable[[str, str, int, str, None, int, str], _RegisteredTask]
    DeleteTask: Callable[[str, int], None]


type _XmlShape = tuple[str, str, tuple[tuple[str, str], ...], tuple[_XmlShape, ...]]


class _NativeCall:
    """Retain the actual scheduler thread until its terminal outcome is joined."""

    def __init__(self, operation: Callable[[], None]) -> None:
        self.result: Future[None] = Future()

        def run() -> None:
            try:
                operation()
            except BaseException as error:
                self.result.set_exception(error)
            else:
                self.result.set_result(None)

        self.thread = Thread(target=run, name="managed-stop-com-call", daemon=True)

    def start(self) -> None:
        try:
            self.thread.start()
        except BaseException as error:
            if not self.result.done():
                self.result.set_exception(error)
            raise

    def settle(self, *, timeout: float) -> BaseException | None:
        deadline = time.monotonic() + timeout
        failure: BaseException | None = None
        primary: BaseException | None = None
        try:
            failure = self.result.exception(timeout=max(0.0, deadline - time.monotonic()))
        except BaseException as error:
            primary = error
        try:
            if self.thread.ident is not None:
                self.thread.join(timeout=max(0.0, deadline - time.monotonic()))
            if self.thread.is_alive():
                raise TimeoutError("original scheduler thread has not settled")
        except BaseException as error:
            if primary is None:
                primary = error
            elif error is not primary:
                previous = primary.__dict__.get("cleanup_error")
                diagnostic = AsyncResourceCleanupError(
                    (), (error,), retry_task_name="managed-stop-thread-diagnostics", close_attempts=1
                )
                if isinstance(previous, AsyncResourceCleanupError):
                    diagnostic = previous.merged_with(diagnostic)
                elif isinstance(previous, BaseException):
                    diagnostic = diagnostic.merged_with(
                        AsyncResourceCleanupError(
                            (), (previous,), retry_task_name="managed-stop-thread-diagnostics", close_attempts=1
                        )
                    )
                primary.__dict__["cleanup_error"] = diagnostic
        if primary is not None:
            raise primary
        return failure


class _ProbeTaskCleanup:
    """Own one registered probe and its original scheduler calls across failure."""

    def __init__(self, task_name: str, identity: _XmlShape, root: Path, events_path: Path) -> None:
        self.task_name, self.identity = task_name, identity
        self.root, self.events_path = root, events_path
        self.stop_call: _NativeCall | None = None
        self.cleanup_call: _NativeCall | None = None
        self.retiring = False
        self.released = False
        self.settlement_seconds = 12.0
        self._guard = Lock()

    def start_stop(self) -> None:
        if self.stop_call is not None or self.retiring or self.released:
            raise RuntimeError("probe Stop is already owned or retiring")
        call = _NativeCall(lambda: _stop_task(self.task_name, self.identity))
        self.stop_call = call
        call.start()

    def settle_stop(self) -> None:
        call = self.stop_call
        if call is None:
            return
        failure = call.settle(timeout=self.settlement_seconds)
        self.stop_call = None
        if failure is not None:
            raise failure

    def retain_failure(self, primary: BaseException, *failures: BaseException) -> None:
        retained = AsyncResourceCleanupError(
            (self,), failures, retry_task_name="managed-stop-probe-cleanup", close_attempts=1
        )
        diagnostics = [failure for failure in failures if failure is not primary]
        seen: set[int] = set()
        for name in ("async_cleanup_error", "cleanup_error"):
            previous = primary.__dict__.get(name)
            if isinstance(previous, AsyncResourceCleanupError) and id(previous) not in seen:
                seen.add(id(previous))
                retained = previous.merged_with(retained)
                if previous.__cause__ is not None:
                    diagnostics.append(previous.__cause__)
            elif isinstance(previous, BaseException) and not isinstance(previous, AsyncResourceCleanupError):
                diagnostics.append(previous)
                retained = retained.merged_with(
                    AsyncResourceCleanupError(
                        (), (previous,), retry_task_name="managed-stop-probe-diagnostics", close_attempts=1
                    )
                )
        if diagnostics:
            retained.__cause__ = BaseExceptionGroup("Retained probe cleanup failures", diagnostics)
        primary.__dict__["async_cleanup_error"] = retained
        primary.__dict__["cleanup_error"] = retained

    def _close_now(self) -> None:
        if not self._guard.acquire(timeout=self.settlement_seconds):
            raise TimeoutError("probe cleanup is already settling its original call")
        try:
            if self.released:
                return
            self.settle_stop()
            if self.cleanup_call is None:
                call = _NativeCall(lambda: _cleanup_task(self.task_name, self.identity, self.root, self.events_path))
                self.cleanup_call = call
                call.start()
            failure = self.cleanup_call.settle(timeout=25)
            self.cleanup_call = None
            if failure is not None:
                raise failure
            self.released = True
        finally:
            self._guard.release()

    async def close(self) -> None:
        """Retry owned native settlement without redispatching a pending Stop."""
        await asyncio.to_thread(self._close_now)


_PROBE_TASK_CLEANUP: ContextVar[_ProbeTaskCleanup | None] = ContextVar("managed-stop-probe-cleanup", default=None)


def _scheduler_call[Result](operation: Callable[[_TaskFolder], Result]) -> Result:
    import pythoncom
    import win32com.client

    pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
    service: object | None = None
    folder: object | None = None
    try:
        service = win32com.client.Dispatch("Schedule.Service")
        service.Connect()
        folder = service.GetFolder("\\")
        return operation(cast(_TaskFolder, folder))
    finally:
        folder = None
        service = None
        pythoncom.CoUninitialize()


def _win_library(name: str) -> ctypes.CDLL:
    loader = cast(Callable[..., ctypes.CDLL], getattr(ctypes, _WINDOWS_DLL_LOADER))
    return loader(name, use_last_error=True)


def _shape(element: ElementTree.Element) -> _XmlShape:
    text = (element.text or "").strip() if len(element) else (element.text or "")
    return (
        element.tag,
        text,
        tuple(sorted(element.attrib.items())),
        tuple(_shape(child) for child in element),
    )


def _normalize_registered_xml(xml: str) -> _XmlShape:
    if len(xml) > 256 * 1024:
        raise RuntimeError("registered probe task XML exceeded its bound")
    try:
        return _shape(fromstring(xml, forbid_dtd=True, forbid_entities=True, forbid_external=True))
    except (ElementTree.ParseError, DefusedXmlException) as error:
        raise RuntimeError("registered probe task XML could not be normalized") from error


def _definition_difference(actual_xml: str, expected_xml: str) -> dict[str, object]:
    """Retain bounded structural diagnostics without account or action text."""
    difference: dict[str, object] = {
        "expected_xml_sha256": hashlib.sha256(expected_xml.encode()).hexdigest(),
        "registered_xml_sha256": hashlib.sha256(actual_xml.encode()).hexdigest(),
    }
    if len(actual_xml) > 256 * 1024 or len(expected_xml) > 256 * 1024:
        difference["reason"] = "xml_bound_exceeded"
        return difference
    try:
        actual = fromstring(actual_xml, forbid_dtd=True, forbid_entities=True, forbid_external=True)
        expected = fromstring(expected_xml, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except (ElementTree.ParseError, DefusedXmlException):
        difference["reason"] = "invalid_task_xml"
        return difference
    rows: list[dict[str, object]] = []

    def compare(actual_shape: _XmlShape, expected_shape: _XmlShape, path: str) -> None:
        if len(rows) >= 32:
            return
        for field, found, wanted in (
            ("tag", actual_shape[0], expected_shape[0]),
            ("text", actual_shape[1], expected_shape[1]),
            ("attributes", actual_shape[2], expected_shape[2]),
        ):
            if found != wanted:
                if field == "text" and actual_shape[0].removeprefix(_TASK_NAMESPACE) in {
                    "UserId",
                    "Command",
                    "Arguments",
                    "WorkingDirectory",
                }:
                    rows.append(
                        {
                            "path": path,
                            "field": "text_sha256",
                            "actual": hashlib.sha256(str(found).encode()).hexdigest(),
                            "expected": hashlib.sha256(str(wanted).encode()).hexdigest(),
                        }
                    )
                else:
                    rows.append({"path": path, "field": field, "actual": found, "expected": wanted})
        actual_children, expected_children = actual_shape[3], expected_shape[3]
        if len(actual_children) != len(expected_children):
            rows.append(
                {
                    "path": path,
                    "field": "child_tags",
                    "actual": [child[0] for child in actual_children],
                    "expected": [child[0] for child in expected_children],
                }
            )
        for index, (found_child, wanted_child) in enumerate(zip(actual_children, expected_children, strict=False)):
            compare(
                found_child, wanted_child, path + "/" + wanted_child[0].removeprefix(_TASK_NAMESPACE) + f"[{index}]"
            )

    compare(_shape(actual), _shape(expected), "Task")
    difference["differences"] = rows[:32]
    return difference


def _registered_xml_matches_definition(actual_xml: str, expected_xml: str) -> bool:
    """Use the owning production matcher for the synthetic fixture action."""
    return _task_xml_definition_matches(actual_xml, expected_xml)


def _missing_task(error: BaseException) -> bool:
    args = getattr(error, "args", ())
    if not args or not isinstance(args[0], int):
        return False
    hresult = args[0]
    detail = args[2] if len(args) > 2 else None
    if hresult == -2147352567 and isinstance(detail, tuple) and len(detail) == 6:
        hresult = detail[5]
    return isinstance(hresult, int) and hresult & 0xFFFFFFFF in {0x80070002, 0x8004130F}


def _registered_task_xml(task_name: str, definition_xml: str, owner_sid: str) -> str:
    import pythoncom

    def register(folder: _TaskFolder) -> str:
        try:
            folder.GetTask(task_name)
        except pythoncom.com_error as error:
            if not _missing_task(error):
                raise
        else:
            raise RuntimeError("unique managed-stop task name already exists")
        created = folder.RegisterTask(
            task_name,
            definition_xml,
            _TASK_CREATE,
            owner_sid,
            None,
            _TASK_LOGON_INTERACTIVE_TOKEN,
            "",
        )
        return created.Xml

    return _scheduler_call(register)


def _require_owned_task(folder: _TaskFolder, task_name: str, identity: _XmlShape) -> _RegisteredTask:
    try:
        task = folder.GetTask(task_name)
    except Exception as error:
        if _missing_task(error):
            raise RuntimeError("owned managed-stop task disappeared") from error
        raise
    if _normalize_registered_xml(task.Xml) != identity:
        raise RuntimeError("managed-stop task XML changed; refusing to control it")
    return task


def _start_task(task_name: str, identity: _XmlShape) -> None:
    def start(folder: _TaskFolder) -> None:
        _require_owned_task(folder, task_name, identity).Run(None)

    _scheduler_call(start)


def _stop_task(task_name: str, identity: _XmlShape) -> None:
    def stop(folder: _TaskFolder) -> None:
        # Check the exact normalized XML captured from registration immediately
        # before Stop: never signal a task that was replaced after creation.
        _require_owned_task(folder, task_name, identity).Stop(0)

    _scheduler_call(stop)


def _task_state(task_name: str, identity: _XmlShape) -> int:
    return _scheduler_call(lambda folder: _require_owned_task(folder, task_name, identity).State)


def _delete_task(task_name: str, identity: _XmlShape) -> None:
    def delete(folder: _TaskFolder) -> None:
        # The identity comparison is repeated immediately before deletion.
        _require_owned_task(folder, task_name, identity)
        folder.DeleteTask(task_name, 0)

    _scheduler_call(delete)


def _owned_installed_task_identity(task_name: str, binding: RuntimeServiceBinding) -> _XmlShape | None:
    """Capture only the exact isolated task, including after partial configure."""
    import pythoncom

    def inspect(folder: _TaskFolder) -> _XmlShape | None:
        try:
            task = folder.GetTask(task_name)
        except pythoncom.com_error as error:
            if _missing_task(error):
                return None
            raise
        xml = task.Xml
        if not windows_task_binding_matches(xml, binding, login_autostart=False):
            raise RuntimeError("isolated installed task changed; refusing cleanup")
        return _normalize_registered_xml(xml)

    return _scheduler_call(inspect)


def _process_creation_identity(pid: int) -> str | None:
    from ctypes import wintypes

    kernel = _win_library("kernel32")
    open_process = kernel.OpenProcess
    open_process.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    open_process.restype = wintypes.HANDLE
    handle = open_process(_PROCESS_QUERY_LIMITED_INFORMATION | _SYNCHRONIZE, False, pid)
    if not handle:
        return None
    try:
        wait = kernel.WaitForSingleObject
        wait.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        wait.restype = wintypes.DWORD
        if wait(handle, 0) != _WAIT_TIMEOUT:
            return None
        get_times = kernel.GetProcessTimes
        get_times.argtypes = (
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
        )
        get_times.restype = wintypes.BOOL
        created = wintypes.FILETIME()
        exited = wintypes.FILETIME()
        kernel_time = wintypes.FILETIME()
        user_time = wintypes.FILETIME()
        if not get_times(
            handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel_time), ctypes.byref(user_time)
        ):
            return None
        return str((created.dwHighDateTime << 32) | created.dwLowDateTime)
    finally:
        close_handle = kernel.CloseHandle
        close_handle.argtypes = (wintypes.HANDLE,)
        close_handle.restype = wintypes.BOOL
        close_handle(handle)


def _require_temp_child(root: Path) -> Path:
    temporary = Path(tempfile.gettempdir()).resolve(strict=True)
    resolved = root.resolve(strict=True)
    if root.is_symlink() or resolved != root or not resolved.is_relative_to(temporary):
        raise RuntimeError("managed-stop probe root is not the exact temporary directory")
    return resolved


def _request_fixture_cleanup(root: Path, events_path: Path) -> None:
    """Signal only logged fixture instances whose PID/start pair still matches."""
    root = _require_temp_child(root)
    for event in _read_events(events_path):
        if event["kind"] not in {"started", "window_ready"}:
            continue
        pid, start = event["pid"], event["start"]
        if _process_creation_identity(pid) != start:
            continue
        request = root / f"cleanup-{pid}-{start}.request"
        payload = f"{pid}:{start}\n".encode("ascii")
        try:
            descriptor = os.open(
                request,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
                0o600,
            )
        except FileExistsError:
            continue
        try:
            os.write(descriptor, payload)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _release_drain(root: Path, process: _Event) -> None:
    root = _require_temp_child(root)
    pid, start = process["pid"], process["start"]
    request = root / f"release-drain-{pid}-{start}.request"
    payload = f"{pid}:{start}\n".encode("ascii")
    try:
        descriptor = os.open(
            request,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
            0o600,
        )
    except FileExistsError:
        if request.read_bytes() != payload:
            raise RuntimeError("drain release sentinel identity changed") from None
        return
    try:
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _stop_and_release_drain(
    task_name: str, identity: _XmlShape, root: Path, events_path: Path, process: _Event
) -> tuple[_Event, ...]:
    owner = _PROBE_TASK_CLEANUP.get()
    if owner is None or (owner.task_name, owner.identity, owner.root, owner.events_path) != (
        task_name,
        identity,
        root,
        events_path,
    ):
        raise RuntimeError("drain probe has no exact registered-task cleanup owner")
    primary: BaseException | None = None
    try:
        owner.start_stop()
        try:
            events = _wait_for_event(events_path, "drain_started", timeout=12)
            assert not any(event["kind"] == "drain_completed" for event in events)
        except BaseException as error:
            primary = error
        # Release from the parent thread even if COM Stop waits for the task
        # process to finish; the fixture's own four-second timeout is the bound.
        try:
            _release_drain(root, process)
        except BaseException as error:
            if primary is None:
                primary = error
            else:
                owner.retain_failure(primary, error)
        try:
            owner.settle_stop()
        except BaseException as error:
            if primary is None:
                primary = error
            owner.retain_failure(primary, error)
        if primary is not None:
            raise primary
    except BaseException as error:
        if owner.stop_call is not None:
            owner.retain_failure(error, error)
        raise
    return _wait_for_event(events_path, "drain_completed", timeout=8)


def _wait_fixture_processes_gone(events_path: Path, *, timeout: float = 8) -> None:
    instances = {
        (event["pid"], event["start"])
        for event in _read_events(events_path)
        if event["kind"] in {"started", "window_ready"}
    }
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not any(_process_creation_identity(pid) == start for pid, start in instances):
            return
        time.sleep(0.05)
    raise RuntimeError("a recorded probe process remained live after its identity-bound cleanup request")


def _cleanup_task(task_name: str, identity: _XmlShape, root: Path, events_path: Path) -> None:
    try:
        _task_state(task_name, identity)
    except RuntimeError:
        _request_fixture_cleanup(root, events_path)
        _wait_fixture_processes_gone(events_path)
        raise
    try:
        # Cancel a pending restart too, even if the current instance has already
        # failed and the task has returned to Ready.
        _stop_task(task_name, identity)
    except Exception:
        _request_fixture_cleanup(root, events_path)
        _wait_fixture_processes_gone(events_path)
        raise
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            if _task_state(task_name, identity) != _TASK_RUNNING:
                break
        except RuntimeError:
            _request_fixture_cleanup(root, events_path)
            _wait_fixture_processes_gone(events_path)
            raise
        time.sleep(0.05)
    else:
        _request_fixture_cleanup(root, events_path)
        _wait_fixture_processes_gone(events_path)
        raise RuntimeError("owned managed-stop task did not stop within its cleanup bound")
    # Task state can become Ready before the fixture has finished its own
    # bounded drain. Request only exact logged PID/start instances before the
    # task definition is removed.
    _request_fixture_cleanup(root, events_path)
    _wait_fixture_processes_gone(events_path)
    _delete_task(task_name, identity)


@contextmanager
def _registered_probe_task(
    *, root: Path, scenario: str, pythonw: Path, owner_sid: str
) -> Generator[tuple[str, _XmlShape, Path]]:
    root = _require_temp_child(root)
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    binding = RuntimeServiceBinding(
        executable=str(pythonw),
        storage_root=str(root),
        storage_identity=endpoint.storage_identity,
        os_owner_id=owner_sid,
        product_version="managed-stop-probe",
    )
    task_name = runtime_service_name(binding)
    fixture = Path(__file__).with_name("windows_manager_stop_fixture.py").resolve(strict=True)
    xml_root = fromstring(windows_task_xml(binding, login_autostart=False))
    action = xml_root.find("./" + _TASK_NAMESPACE + "Actions/" + _TASK_NAMESPACE + "Exec")
    if action is None:
        raise RuntimeError("probe task has no exact Exec action")
    command = action.find(_TASK_NAMESPACE + "Command")
    arguments = action.find(_TASK_NAMESPACE + "Arguments")
    if command is None or arguments is None:
        raise RuntimeError("probe task action is incomplete")
    command.text = str(pythonw)
    arguments.text = subprocess.list2cmdline(("-I", str(fixture), "--root", str(root), "--scenario", scenario))
    expected_xml = ElementTree.tostring(xml_root, encoding="unicode")
    registered_xml = _registered_task_xml(task_name, expected_xml, owner_sid)
    # Snapshot the scheduler's registered/canonical XML, not the raw input
    # serialization, then use that identity before both Stop and Delete.
    identity = _normalize_registered_xml(registered_xml)
    events_path = root / "events.jsonl"
    owner = _ProbeTaskCleanup(task_name, identity, root, events_path)
    token = _PROBE_TASK_CLEANUP.set(owner)
    primary_errors: list[BaseException] = []
    try:
        if not _registered_xml_matches_definition(registered_xml, expected_xml):
            diagnostic = _definition_difference(registered_xml, expected_xml)
            (root / "registered-task-difference.json").write_text(
                json.dumps(diagnostic, indent=2) + "\n", encoding="utf-8"
            )
            error = RuntimeError("Task Scheduler changed the managed-stop task definition")
            error.add_note(json.dumps(diagnostic, sort_keys=True))
            raise error
        yield task_name, identity, events_path
    except BaseException as error:
        primary_errors.append(error)
        raise
    finally:
        primary = primary_errors[0] if primary_errors else None
        owner.retiring = True
        try:
            asyncio.run(close_async_resources(owner, task_name="managed-stop-probe-cleanup", primary_error=primary))
        finally:
            _PROBE_TASK_CLEANUP.reset(token)
            if primary is not None:
                if owner.released:
                    for name in ("async_cleanup_error", "cleanup_error"):
                        failure = primary.__dict__.get(name)
                        if isinstance(failure, AsyncResourceCleanupError):
                            failure.discard_released_resources(owner)
                else:
                    owner.retain_failure(primary)


def _read_events(path: Path) -> tuple[_Event, ...]:
    if not path.exists():
        return ()
    events: list[_Event] = []
    for line in path.read_text(encoding="ascii").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if (
            isinstance(value, dict)
            and isinstance(value.get("at_ns"), int)
            and isinstance(value.get("kind"), str)
            and isinstance(value.get("pid"), int)
            and isinstance(value.get("start"), str)
        ):
            events.append(cast(_Event, value))
    return tuple(events)


def _wait_for_event(path: Path, kind: str, *, timeout: float) -> tuple[_Event, ...]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        events = _read_events(path)
        if any(event["kind"] == kind for event in events):
            return events
        time.sleep(0.05)
    raise AssertionError(f"managed-stop fixture did not record {kind}")


def _observe_no_restart(path: Path) -> None:
    deadline = time.monotonic() + _STOP_OBSERVATION_SECONDS
    while time.monotonic() < deadline:
        starts = tuple(event for event in _read_events(path) if event["kind"] == "started")
        assert len(starts) == 1, "Task Scheduler restarted a task after explicit Stop"
        time.sleep(0.25)


def _is_elevated() -> bool | None:
    from ctypes import wintypes

    class _TokenElevation(ctypes.Structure):
        _fields_ = [("TokenIsElevated", wintypes.DWORD)]

    kernel = _win_library("kernel32")
    advapi = _win_library("advapi32")
    current_process = kernel.GetCurrentProcess
    current_process.argtypes = ()
    current_process.restype = wintypes.HANDLE
    open_token = advapi.OpenProcessToken
    open_token.argtypes = (wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE))
    open_token.restype = wintypes.BOOL
    get_information = advapi.GetTokenInformation
    get_information.argtypes = (
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    )
    get_information.restype = wintypes.BOOL
    close_handle = kernel.CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL
    token = wintypes.HANDLE()
    if not open_token(current_process(), 0x0008, ctypes.byref(token)):
        return None
    try:
        elevation = _TokenElevation()
        returned = wintypes.DWORD()
        if not get_information(token, 20, ctypes.byref(elevation), ctypes.sizeof(elevation), ctypes.byref(returned)):
            return None
        return bool(elevation.TokenIsElevated)
    finally:
        close_handle(token)


def _has_interactive_desktop() -> bool:
    from ctypes import wintypes

    kernel = _win_library("kernel32")
    user = _win_library("user32")
    process_id_to_session = kernel.ProcessIdToSessionId
    process_id_to_session.argtypes = (wintypes.DWORD, ctypes.POINTER(wintypes.DWORD))
    process_id_to_session.restype = wintypes.BOOL
    session_id = wintypes.DWORD()
    if not process_id_to_session(os.getpid(), ctypes.byref(session_id)) or session_id.value == 0:
        return False
    user.OpenInputDesktop.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    user.OpenInputDesktop.restype = wintypes.HANDLE
    desktop = user.OpenInputDesktop(0, False, 0x0001)
    if not desktop:
        return False
    close_desktop = user.CloseDesktop
    close_desktop.argtypes = (wintypes.HANDLE,)
    close_desktop.restype = wintypes.BOOL
    close_desktop(desktop)
    return True


def _native_prerequisites() -> tuple[Path, str]:
    if sys.platform != "win32":
        pytest.skip("requires native Windows Task Scheduler")
    if _is_elevated() is not False:
        pytest.skip("requires a verifiably non-elevated process token")
    if not _has_interactive_desktop():
        pytest.skip("requires an active interactive desktop session")
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    if not pythonw.is_file():
        pytest.skip("requires pythonw.exe; a console fallback is prohibited")
    return pythonw.resolve(strict=True), _current_process_owner_sid()


def _current_process_owner_sid() -> str:
    import win32api
    import win32security

    token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), 8)
    try:
        sid, _attributes = win32security.GetTokenInformation(token, win32security.TokenUser)
        owner = win32security.ConvertSidToStringSid(sid)
        if not isinstance(owner, str) or not owner:
            raise RuntimeError("current process owner SID is unavailable")
        return owner
    finally:
        win32api.CloseHandle(token)


def _make_temp_root(tmp_path: Path) -> Path:
    root = tmp_path / f"managed-stop-{uuid4().hex}"
    root.mkdir()
    return _require_temp_child(root)


pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_outbound_adapter,
    pytest.mark.serial,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Task Scheduler and an interactive token"),
]


@pytest.mark.parametrize(
    ("scenario", "terminal_event"),
    (("graceful", "exited_successfully"), ("fail_on_close", "failure_during_stop")),
)
def test_task_stop_delivers_close_and_suppresses_restart(tmp_path: Path, scenario: str, terminal_event: str) -> None:
    """Observe hidden WM_CLOSE drain and intentional-stop restart suppression."""
    pythonw, owner_sid = _native_prerequisites()
    root = _make_temp_root(tmp_path)
    with _registered_probe_task(root=root, scenario=scenario, pythonw=pythonw, owner_sid=owner_sid) as (
        task_name,
        identity,
        events_path,
    ):
        _start_task(task_name, identity)
        events = _wait_for_event(events_path, "window_ready", timeout=12)
        assert len(tuple(event for event in events if event["kind"] == "started")) == 1
        if scenario == "graceful":
            process = next(event for event in events if event["kind"] == "window_ready")
            events = _stop_and_release_drain(task_name, identity, root, events_path, process)
            assert any(event["kind"] == "drain_release_observed" for event in events)
            assert any(event["kind"] == "drain_started" for event in events)
            assert any(event["kind"] == "drain_completed" for event in events)
        else:
            _stop_task(task_name, identity)
        events = _wait_for_event(events_path, terminal_event, timeout=12)
        assert any(event["kind"] == "wm_close" for event in events)
        assert any(event["kind"] == terminal_event for event in events)
        _observe_no_restart(events_path)


def test_task_restart_on_unrequested_failure_remains_active(tmp_path: Path) -> None:
    """Control: a failure without Stop must restart after the configured minute."""
    pythonw, owner_sid = _native_prerequisites()
    root = _make_temp_root(tmp_path)
    with _registered_probe_task(root=root, scenario="fail_start", pythonw=pythonw, owner_sid=owner_sid) as (
        task_name,
        identity,
        events_path,
    ):
        _start_task(task_name, identity)
        _wait_for_event(events_path, "started", timeout=12)
        deadline = time.monotonic() + 90
        starts: tuple[_Event, ...] = ()
        while time.monotonic() < deadline:
            starts = tuple(event for event in _read_events(events_path) if event["kind"] == "started")
            if len(starts) >= 2:
                break
            time.sleep(0.25)
        assert len(starts) >= 2, "Task Scheduler did not retry an unrequested failure within its bound"
        assert starts[1]["at_ns"] - starts[0]["at_ns"] >= 55_000_000_000
        assert starts[1]["pid"] != starts[0]["pid"] or starts[1]["start"] != starts[0]["start"]


@pytest.mark.asyncio
async def test_installed_runtime_owner_stop_preserves_bound_task_and_suppresses_restart(tmp_path: Path) -> None:
    """Exercise the real installed runtime, exact task matcher and owner control."""
    _native_prerequisites()
    import sysconfig

    root = _make_temp_root(tmp_path)
    executable = Path(sysconfig.get_path("scripts")) / "cadrumo-runtime.exe"
    if not executable.is_file():
        pytest.skip("installed runtime executable unavailable")
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    product_version = version("cadrumo")
    binding = RuntimeServiceBinding(
        executable=str(executable.resolve(strict=True)),
        storage_root=str(root),
        storage_identity=endpoint.storage_identity,
        os_owner_id=_current_process_owner_sid(),
        product_version=product_version,
    )
    manager = WindowsTaskManager(binding)
    before = await manager.inspect()
    if not before.available:
        pytest.skip("Task Scheduler unavailable")
    if before.provisioned:
        raise RuntimeError("unique installed-runtime task name already exists")
    task_name = runtime_service_name(binding)
    try:
        configured = await manager.configure(login_autostart=False)
        assert configured.binding_matches and not configured.login_autostart
        if _owned_installed_task_identity(task_name, binding) is None:
            raise RuntimeError("configured installed task disappeared")
        await manager.start()
        # Real cold registry preparation shares the installed admission budget;
        # the short probe deadlines elsewhere do not govern runtime readiness.
        deadline = time.monotonic() + PROFILE_ADMISSION_TIMEOUT_SECONDS
        while True:
            try:
                client = VerifiedRuntimeConnection(
                    endpoint.connect(timeout=1),
                    expected=RuntimeClientHello(
                        product_version=product_version, storage_identity=endpoint.storage_identity
                    ),
                    deadline=time.monotonic() + 3,
                )
                break
            except RuntimeRefusalError as error:
                if error.reason is not RuntimeRefusalCode.ENDPOINT_NOT_READY or time.monotonic() >= deadline:
                    raise
                await asyncio.sleep(0.05)
        try:
            preview = client.owner_control(RuntimeStopPreviewRequest(request_id=uuid4()), deadline=time.monotonic() + 5)
            assert isinstance(preview, RuntimeStopPreview)
            accepted = client.owner_control(
                RuntimeStopConfirm(
                    request_id=uuid4(),
                    runtime_boot_id=preview.runtime_boot_id,
                    preview_id=preview.preview_id,
                    acknowledge_all_profiles_and_work=True,
                ),
                deadline=time.monotonic() + 8,
            )
            assert isinstance(accepted, RuntimeStopAccepted)
        finally:
            client.close()
        deadline = time.monotonic() + 25
        while True:
            current = await manager.inspect()
            assert current.binding_matches and not current.login_autostart
            if current.process_state.name == "STOPPED":
                break
            if time.monotonic() >= deadline:
                raise AssertionError("installed runtime did not stop within its drain bound")
            await asyncio.sleep(0.05)
        observation_deadline = time.monotonic() + _STOP_OBSERVATION_SECONDS
        while time.monotonic() < observation_deadline:
            current = await manager.inspect()
            assert current.binding_matches and not current.login_autostart
            assert current.process_state.name == "STOPPED", "managed runtime restarted after explicit stop"
            await asyncio.sleep(0.25)
    finally:
        identity = _owned_installed_task_identity(task_name, binding)
        if identity is not None:
            # Every cleanup operation rechecks the exact registered XML. A
            # replaced task is left untouched for explicit inspection.
            if _task_state(task_name, identity) == _TASK_RUNNING:
                _stop_task(task_name, identity)
            deadline = time.monotonic() + 25
            while _task_state(task_name, identity) == _TASK_RUNNING:
                if time.monotonic() >= deadline:
                    raise RuntimeError("isolated installed runtime did not stop for cleanup")
                await asyncio.sleep(0.05)
            _delete_task(task_name, identity)
        endpoint.close()
