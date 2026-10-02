"""Exact Windows task lifetimes shared by native management acceptance tests."""

from __future__ import annotations

import asyncio
import ctypes
import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
import time
from collections.abc import AsyncIterator, Callable, Generator
from concurrent.futures import Future
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from ctypes import wintypes
from importlib.metadata import version
from pathlib import Path
from threading import Lock, Thread
from typing import Protocol, TypedDict, cast
from uuid import UUID, uuid4
from xml.etree import ElementTree

import pytest
from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import fromstring

from cadrumo.adapters.local_runtime.framing import RuntimeTransportCleanup, VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.service_definitions import runtime_service_name, windows_task_xml
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.local_runtime.windows_manager import (
    WindowsTaskManager,
    _task_xml_definition_matches,
    windows_task_binding_matches,
)
from cadrumo.adapters.local_runtime.windows_process import WindowsOwnedProcess
from cadrumo.adapters.local_runtime.windows_task_process import task_engine_owns_process
from cadrumo.application.runtime.contracts import RuntimeClientHello, RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.management import RuntimeServiceBinding
from cadrumo.application.runtime.owner_control import (
    RuntimeStopAccepted,
    RuntimeStopConfirm,
    RuntimeStopPreview,
    RuntimeStopPreviewRequest,
)
from cadrumo.application.runtime.profile_access import PROFILE_ADMISSION_TIMEOUT_SECONDS
from cadrumo.core.async_cleanup import (
    AsyncResourceCleanupError,
    async_cleanup_failures,
    await_cancellation_complete,
    close_async_resources,
    has_async_cleanup_failure,
)

_TASK_NAMESPACE = "{http://schemas.microsoft.com/windows/2004/02/mit/task}"
_TASK_CREATE = 2
_TASK_LOGON_INTERACTIVE_TOKEN = 3
WINDOWS_STOP_OBSERVATION_SECONDS = 67
WINDOWS_TASK_RUNNING = 4
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_SYNCHRONIZE = 0x00100000
_WAIT_TIMEOUT = 0x00000102
_WINDOWS_DLL_LOADER = "WinDLL"


class WindowsFixtureEvent(TypedDict):
    at_ns: int
    kind: str
    pid: int
    start: str


class WindowsRegisteredTask(Protocol):
    Xml: str
    State: int

    Run: Callable[[object], object]
    Stop: Callable[[int], None]


class WindowsTaskFolder(Protocol):
    GetTask: Callable[[str], WindowsRegisteredTask]
    RegisterTask: Callable[[str, str, int, str, None, int, str], WindowsRegisteredTask]
    DeleteTask: Callable[[str, int], None]


type WindowsTaskXmlShape = tuple[str, str, tuple[tuple[str, str], ...], tuple[WindowsTaskXmlShape, ...]]


class WindowsSchedulerCall:
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


class WindowsProbeTaskCleanup:
    """Own one registered probe and its original scheduler calls across failure."""

    def __init__(self, task_name: str, identity: WindowsTaskXmlShape, root: Path, events_path: Path) -> None:
        self.task_name, self.identity = task_name, identity
        self.root, self.events_path = root, events_path
        self.stop_call: WindowsSchedulerCall | None = None
        self.cleanup_call: WindowsSchedulerCall | None = None
        self.retiring = False
        self.released = False
        self.settlement_seconds = 12.0
        self._guard = Lock()

    def start_stop(self) -> None:
        if self.stop_call is not None or self.retiring or self.released:
            raise RuntimeError("probe Stop is already owned or retiring")
        call = WindowsSchedulerCall(lambda: stop_exact_windows_task(self.task_name, self.identity))
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
                call = WindowsSchedulerCall(
                    lambda: cleanup_windows_probe_task(self.task_name, self.identity, self.root, self.events_path)
                )
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


WINDOWS_PROBE_TASK_CLEANUP: ContextVar[WindowsProbeTaskCleanup | None] = ContextVar(
    "managed-stop-probe-cleanup", default=None
)


def windows_scheduler_call[Result](operation: Callable[[WindowsTaskFolder], Result]) -> Result:
    import pythoncom
    import win32com.client

    pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
    service: object | None = None
    folder: object | None = None
    try:
        service = win32com.client.Dispatch("Schedule.Service")
        service.Connect()
        folder = service.GetFolder("\\")
        return operation(cast(WindowsTaskFolder, folder))
    finally:
        folder = None
        service = None
        pythoncom.CoUninitialize()


def windows_native_library(name: str) -> ctypes.CDLL:
    loader = cast(Callable[..., ctypes.CDLL], getattr(ctypes, _WINDOWS_DLL_LOADER))
    return loader(name, use_last_error=True)


def windows_task_shape(element: ElementTree.Element) -> WindowsTaskXmlShape:
    text = (element.text or "").strip() if len(element) else (element.text or "")
    return (
        element.tag,
        text,
        tuple(sorted(element.attrib.items())),
        tuple(windows_task_shape(child) for child in element),
    )


def normalize_windows_task_xml(xml: str) -> WindowsTaskXmlShape:
    if len(xml) > 256 * 1024:
        raise RuntimeError("registered probe task XML exceeded its bound")
    try:
        return windows_task_shape(fromstring(xml, forbid_dtd=True, forbid_entities=True, forbid_external=True))
    except (ElementTree.ParseError, DefusedXmlException) as error:
        raise RuntimeError("registered probe task XML could not be normalized") from error


def windows_task_definition_difference(actual_xml: str, expected_xml: str) -> dict[str, object]:
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

    def compare(actual_shape: WindowsTaskXmlShape, expected_shape: WindowsTaskXmlShape, path: str) -> None:
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

    compare(windows_task_shape(actual), windows_task_shape(expected), "Task")
    difference["differences"] = rows[:32]
    return difference


def windows_registered_definition_matches(actual_xml: str, expected_xml: str) -> bool:
    """Use the owning production matcher for the synthetic fixture action."""
    return _task_xml_definition_matches(actual_xml, expected_xml)


def windows_task_missing(error: BaseException) -> bool:
    args = getattr(error, "args", ())
    if not args or not isinstance(args[0], int):
        return False
    hresult = args[0]
    detail = args[2] if len(args) > 2 else None
    if hresult == -2147352567 and isinstance(detail, tuple) and len(detail) == 6:
        hresult = detail[5]
    return isinstance(hresult, int) and hresult & 0xFFFFFFFF in {0x80070002, 0x8004130F}


def register_windows_probe_task(task_name: str, definition_xml: str, owner_sid: str) -> str:
    import pythoncom

    def register(folder: WindowsTaskFolder) -> str:
        try:
            folder.GetTask(task_name)
        except pythoncom.com_error as error:
            if not windows_task_missing(error):
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

    return windows_scheduler_call(register)


def require_exact_windows_task(
    folder: WindowsTaskFolder, task_name: str, identity: WindowsTaskXmlShape
) -> WindowsRegisteredTask:
    try:
        task = folder.GetTask(task_name)
    except Exception as error:
        if windows_task_missing(error):
            raise RuntimeError("owned managed-stop task disappeared") from error
        raise
    if normalize_windows_task_xml(task.Xml) != identity:
        raise RuntimeError("managed-stop task XML changed; refusing to control it")
    return task


def start_exact_windows_task(task_name: str, identity: WindowsTaskXmlShape) -> None:
    def start(folder: WindowsTaskFolder) -> None:
        require_exact_windows_task(folder, task_name, identity).Run(None)

    windows_scheduler_call(start)


def stop_exact_windows_task(task_name: str, identity: WindowsTaskXmlShape) -> None:
    def stop(folder: WindowsTaskFolder) -> None:
        # Check the exact normalized XML captured from registration immediately
        # before Stop: never signal a task that was replaced after creation.
        require_exact_windows_task(folder, task_name, identity).Stop(0)

    windows_scheduler_call(stop)


def exact_windows_task_state(task_name: str, identity: WindowsTaskXmlShape) -> int:
    return windows_scheduler_call(lambda folder: require_exact_windows_task(folder, task_name, identity).State)


def delete_exact_windows_task(task_name: str, identity: WindowsTaskXmlShape) -> None:
    def delete(folder: WindowsTaskFolder) -> None:
        # The identity comparison is repeated immediately before deletion.
        require_exact_windows_task(folder, task_name, identity)
        folder.DeleteTask(task_name, 0)

    windows_scheduler_call(delete)


def installed_windows_task_identity(
    task_name: str, binding: RuntimeServiceBinding, *, login_autostart: bool | None = False
) -> WindowsTaskXmlShape | None:
    """Capture only the exact isolated task, including after partial configure."""
    import pythoncom

    def inspect(folder: WindowsTaskFolder) -> WindowsTaskXmlShape | None:
        try:
            task = folder.GetTask(task_name)
        except pythoncom.com_error as error:
            if windows_task_missing(error):
                return None
            raise
        xml = task.Xml
        if not any(
            windows_task_binding_matches(xml, binding, login_autostart=enabled)
            for enabled in ((False, True) if login_autostart is None else (login_autostart,))
        ):
            raise RuntimeError("isolated installed task changed; refusing cleanup")
        return normalize_windows_task_xml(xml)

    return windows_scheduler_call(inspect)


def windows_process_creation_identity(pid: int) -> str | None:
    from ctypes import wintypes

    kernel = windows_native_library("kernel32")
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


def require_windows_fixture_root(root: Path) -> Path:
    temporary = Path(tempfile.gettempdir()).resolve(strict=True)
    resolved = root.resolve(strict=True)
    if root.is_symlink() or resolved != root or not resolved.is_relative_to(temporary):
        raise RuntimeError("managed-stop probe root is not the exact temporary directory")
    return resolved


def request_windows_probe_cleanup(root: Path, events_path: Path) -> None:
    """Signal only logged fixture instances whose PID/start pair still matches."""
    root = require_windows_fixture_root(root)
    for event in read_windows_probe_events(events_path):
        if event["kind"] not in {"started", "window_ready"}:
            continue
        pid, start = event["pid"], event["start"]
        if windows_process_creation_identity(pid) != start:
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


def release_windows_probe_drain(root: Path, process: WindowsFixtureEvent) -> None:
    root = require_windows_fixture_root(root)
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


def stop_windows_probe_and_release_drain(
    task_name: str, identity: WindowsTaskXmlShape, root: Path, events_path: Path, process: WindowsFixtureEvent
) -> tuple[WindowsFixtureEvent, ...]:
    owner = WINDOWS_PROBE_TASK_CLEANUP.get()
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
            events = wait_windows_probe_event(events_path, "drain_started", timeout=12)
            assert not any(event["kind"] == "drain_completed" for event in events)
        except BaseException as error:
            primary = error
        # Release from the parent thread even if COM Stop waits for the task
        # process to finish; the fixture's own four-second timeout is the bound.
        try:
            release_windows_probe_drain(root, process)
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
    return wait_windows_probe_event(events_path, "drain_completed", timeout=8)


def wait_windows_probe_processes_gone(events_path: Path, *, timeout: float = 8) -> None:
    instances = {
        (event["pid"], event["start"])
        for event in read_windows_probe_events(events_path)
        if event["kind"] in {"started", "window_ready"}
    }
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not any(windows_process_creation_identity(pid) == start for pid, start in instances):
            return
        time.sleep(0.05)
    raise RuntimeError("a recorded probe process remained live after its identity-bound cleanup request")


def cleanup_windows_probe_task(task_name: str, identity: WindowsTaskXmlShape, root: Path, events_path: Path) -> None:
    try:
        exact_windows_task_state(task_name, identity)
    except RuntimeError:
        request_windows_probe_cleanup(root, events_path)
        wait_windows_probe_processes_gone(events_path)
        raise
    try:
        # Cancel a pending restart too, even if the current instance has already
        # failed and the task has returned to Ready.
        stop_exact_windows_task(task_name, identity)
    except Exception:
        request_windows_probe_cleanup(root, events_path)
        wait_windows_probe_processes_gone(events_path)
        raise
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            if exact_windows_task_state(task_name, identity) != WINDOWS_TASK_RUNNING:
                break
        except RuntimeError:
            request_windows_probe_cleanup(root, events_path)
            wait_windows_probe_processes_gone(events_path)
            raise
        time.sleep(0.05)
    else:
        request_windows_probe_cleanup(root, events_path)
        wait_windows_probe_processes_gone(events_path)
        raise RuntimeError("owned managed-stop task did not stop within its cleanup bound")
    # Task state can become Ready before the fixture has finished its own
    # bounded drain. Request only exact logged PID/start instances before the
    # task definition is removed.
    request_windows_probe_cleanup(root, events_path)
    wait_windows_probe_processes_gone(events_path)
    delete_exact_windows_task(task_name, identity)


@contextmanager
def registered_windows_probe_task(
    *, root: Path, scenario: str, pythonw: Path, owner_sid: str
) -> Generator[tuple[str, WindowsTaskXmlShape, Path]]:
    root = require_windows_fixture_root(root)
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
    registered_xml = register_windows_probe_task(task_name, expected_xml, owner_sid)
    # Snapshot the scheduler's registered/canonical XML, not the raw input
    # serialization, then use that identity before both Stop and Delete.
    identity = normalize_windows_task_xml(registered_xml)
    events_path = root / "events.jsonl"
    owner = WindowsProbeTaskCleanup(task_name, identity, root, events_path)
    token = WINDOWS_PROBE_TASK_CLEANUP.set(owner)
    primary_errors: list[BaseException] = []
    try:
        if not windows_registered_definition_matches(registered_xml, expected_xml):
            diagnostic = windows_task_definition_difference(registered_xml, expected_xml)
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
            WINDOWS_PROBE_TASK_CLEANUP.reset(token)
            if primary is not None:
                if owner.released:
                    for name in ("async_cleanup_error", "cleanup_error"):
                        failure = primary.__dict__.get(name)
                        if isinstance(failure, AsyncResourceCleanupError):
                            failure.discard_released_resources(owner)
                else:
                    owner.retain_failure(primary)


def read_windows_probe_events(path: Path) -> tuple[WindowsFixtureEvent, ...]:
    if not path.exists():
        return ()
    events: list[WindowsFixtureEvent] = []
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
            events.append(cast(WindowsFixtureEvent, value))
    return tuple(events)


def wait_windows_probe_event(path: Path, kind: str, *, timeout: float) -> tuple[WindowsFixtureEvent, ...]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        events = read_windows_probe_events(path)
        if any(event["kind"] == kind for event in events):
            return events
        time.sleep(0.05)
    raise AssertionError(f"managed-stop fixture did not record {kind}")


def observe_windows_probe_no_restart(path: Path) -> None:
    deadline = time.monotonic() + WINDOWS_STOP_OBSERVATION_SECONDS
    while time.monotonic() < deadline:
        starts = tuple(event for event in read_windows_probe_events(path) if event["kind"] == "started")
        assert len(starts) == 1, "Task Scheduler restarted a task after explicit Stop"
        time.sleep(0.25)


def windows_fixture_is_elevated() -> bool | None:
    from ctypes import wintypes

    class _TokenElevation(ctypes.Structure):
        _fields_ = [("TokenIsElevated", wintypes.DWORD)]

    kernel = windows_native_library("kernel32")
    advapi = windows_native_library("advapi32")
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


def windows_fixture_has_desktop() -> bool:
    from ctypes import wintypes

    kernel = windows_native_library("kernel32")
    user = windows_native_library("user32")
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


def require_windows_manager_desktop() -> tuple[Path, str]:
    if sys.platform != "win32":
        pytest.skip("requires native Windows Task Scheduler")
    if windows_fixture_is_elevated() is not False:
        pytest.skip("requires a verifiably non-elevated process token")
    if not windows_fixture_has_desktop():
        pytest.skip("requires an active interactive desktop session")
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    if not pythonw.is_file():
        pytest.skip("requires pythonw.exe; a console fallback is prohibited")
    return pythonw.resolve(strict=True), windows_fixture_owner_sid()


def windows_fixture_owner_sid() -> str:
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


def make_windows_fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / f"managed-stop-{uuid4().hex}"
    root.mkdir()
    return require_windows_fixture_root(root)


class _RecoveryTask(Protocol):
    Xml: str
    Path: str


class _RecoveryTaskFolder(Protocol):
    GetTask: Callable[[str], _RecoveryTask]


class _RecoveryRunningTask(Protocol):
    Path: str
    InstanceGuid: str
    EnginePID: int
    Refresh: Callable[[], None]


class _RecoveryRunningTasks(Protocol):
    Count: int
    Item: Callable[[int], _RecoveryRunningTask]


class _RecoveryScheduler(Protocol):
    Connect: Callable[[], None]
    GetFolder: Callable[[str], _RecoveryTaskFolder]
    GetRunningTasks: Callable[[int], _RecoveryRunningTasks]


class WindowsRetainedProcess:
    """Retain one live process incarnation before any crash or cleanup action."""

    def __init__(self, pid: int, *, allow_terminate: bool = False) -> None:
        """Open an ancestry-selected live PID and verify its unchanged birth."""
        self.pid, self.allow_terminate = pid, allow_terminate
        self.kernel = windows_native_library("kernel32")
        self.kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        self.kernel.CloseHandle.restype = wintypes.BOOL
        self.kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        self.kernel.WaitForSingleObject.restype = wintypes.DWORD
        self.kernel.TerminateProcess.argtypes = (wintypes.HANDLE, wintypes.UINT)
        self.kernel.TerminateProcess.restype = wintypes.BOOL
        before = windows_process_creation_identity(pid)
        assert before is not None, "owned process was not live before handle capture"
        handle = cast(int, self.kernel.OpenProcess(0x1000 | 0x100000 | (0x1 if allow_terminate else 0), False, pid))
        assert handle, "owned process could not be retained"
        self.handle: int | None = handle
        try:
            self.kernel.GetProcessTimes.argtypes = (
                wintypes.HANDLE,
                ctypes.POINTER(wintypes.FILETIME),
                ctypes.POINTER(wintypes.FILETIME),
                ctypes.POINTER(wintypes.FILETIME),
                ctypes.POINTER(wintypes.FILETIME),
            )
            self.kernel.GetProcessTimes.restype = wintypes.BOOL
            created, exited, kernel_time, user_time = (wintypes.FILETIME() for _ in range(4))
            assert self.kernel.GetProcessTimes(
                handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel_time), ctypes.byref(user_time)
            )
            self.birth = str((created.dwHighDateTime << 32) | created.dwLowDateTime)
            assert self.birth == before == windows_process_creation_identity(pid)
            assert self.alive()
        except BaseException as error:
            asyncio.run(
                close_async_resources(
                    RuntimeTransportCleanup(self), task_name="recovery-process-constructor-close", primary_error=error
                )
            )
            raise

    def alive(self) -> bool:
        """Check the retained handle, without reopening a possibly reused PID."""
        handle = self.handle
        assert handle is not None
        result: object = self.kernel.WaitForSingleObject(handle, 0)
        assert isinstance(result, int), "native process wait did not return an integer"
        assert result in {0, 0x102}, "retained process wait failed"
        return result == 0x102

    def terminate(self) -> None:
        """Crash only the already retained process incarnation."""
        if not self.allow_terminate:
            raise RuntimeError("retained observation handle has no termination authority")
        if sys.platform != "win32":
            raise RuntimeError("native process termination requires Windows")
        handle = self.handle
        assert handle is not None
        if self.alive():
            terminated: object = self.kernel.TerminateProcess(handle, 0x80004005)
            assert isinstance(terminated, int), "native termination did not return an integer"
            if terminated == 0:
                error_code = ctypes.get_last_error()
                # Another exact-owner shutdown may win between the preceding
                # wait and TerminateProcess. Require actual retained-handle
                # termination; a cached PID or optimistic liveness is invalid.
                settled: object = self.kernel.WaitForSingleObject(handle, 1000)
                assert isinstance(settled, int), "native termination settlement did not return an integer"
                assert settled == 0, f"exact retained process remains unsettled; native error {error_code}"

    def wait(self, *, timeout: float) -> int:
        """Wait for the retained native object under the caller's remaining bound."""
        if not math.isfinite(timeout) or timeout < 0:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        assert self.handle is not None
        result = self.kernel.WaitForSingleObject(self.handle, min(0xFFFFFFFE, math.ceil(timeout * 1000)))
        if result == 0x102:
            raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
        assert result == 0
        exit_code = wintypes.DWORD()
        self.kernel.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        self.kernel.GetExitCodeProcess.restype = wintypes.BOOL
        assert self.kernel.GetExitCodeProcess(self.handle, ctypes.byref(exit_code))
        return exit_code.value

    def close(self) -> None:
        """Retire the handle only after native close succeeds."""
        handle = self.handle
        if handle is not None:
            assert self.kernel.CloseHandle(handle)
            self.handle = None


def installed_windows_task_instance(
    binding: RuntimeServiceBinding, task_name: str, identity: WindowsTaskXmlShape, runtime_pid: int | None
) -> tuple[UUID, int]:
    """Inspect public native hidden-task identity between canonical XML bookends."""
    import pythoncom
    import win32com.client

    def inspect() -> tuple[UUID, int] | None:
        service = cast(_RecoveryScheduler, win32com.client.Dispatch("Schedule.Service"))
        service.Connect()
        folder = service.GetFolder("\\")
        task = folder.GetTask(task_name)
        expected_path = "\\" + task_name
        if (
            task.Path != expected_path
            or not windows_task_binding_matches(task.Xml, binding, login_autostart=False)
            or normalize_windows_task_xml(task.Xml) != identity
        ):
            return None
        instances = service.GetRunningTasks(1)
        if not 0 <= instances.Count <= 4096:
            return None
        selected: tuple[UUID, int] | None = None
        for index in range(1, instances.Count + 1):
            candidate = instances.Item(index)
            if candidate.Path != expected_path:
                continue
            candidate.Refresh()
            if candidate.Path != expected_path or selected is not None:
                return None
            raw_guid = candidate.InstanceGuid
            try:
                guid = UUID(raw_guid)
            except ValueError:
                return None
            if not guid.int or raw_guid.lower() not in {str(guid), "{" + str(guid) + "}"}:
                return None
            engine_pid = candidate.EnginePID
            if engine_pid <= 0 or not task_engine_owns_process(
                engine_pid, runtime_pid if runtime_pid is not None else engine_pid
            ):
                return None
            selected = guid, engine_pid
        verified = folder.GetTask(task_name)
        if (
            verified.Path != expected_path
            or not windows_task_binding_matches(verified.Xml, binding, login_autostart=False)
            or normalize_windows_task_xml(verified.Xml) != identity
        ):
            return None
        return selected

    initialize = cast(Callable[[int], None], pythoncom.CoInitializeEx)
    initialize(pythoncom.COINIT_APARTMENTTHREADED)
    selected: tuple[UUID, int] | None = None
    unavailable = False
    try:
        try:
            selected = inspect()
        except pythoncom.com_error:
            unavailable = True
    finally:
        # Native wrappers and handled COM-error frames have left inspect's
        # scope before the calling thread releases its COM apartment.
        pythoncom.CoUninitialize()
    assert not unavailable, "native scheduler identity inspection unavailable"
    assert selected is not None, "native exact task/process identity was not proven"
    return selected


def retain_windows_runtime_tree(
    runtime_pid: int, owner: WindowsInstalledTaskCleanup, *, engine_pid: int | None = None, require_worker: bool = True
) -> tuple[WindowsRetainedProcess, ...]:
    """Retain only native ancestry members of the verified task/runtime."""
    kernel = windows_native_library("kernel32")
    enumerate_processes = kernel.K32EnumProcesses
    enumerate_processes.argtypes = (ctypes.POINTER(wintypes.DWORD), wintypes.DWORD, ctypes.POINTER(wintypes.DWORD))
    enumerate_processes.restype = wintypes.BOOL
    buffer = (wintypes.DWORD * 4096)()
    used = wintypes.DWORD()
    assert enumerate_processes(buffer, ctypes.sizeof(buffer), ctypes.byref(used))
    assert used.value < ctypes.sizeof(buffer), "native process snapshot exceeded its fixed bound"
    owned: list[WindowsRetainedProcess] = []
    for pid in buffer[: used.value // ctypes.sizeof(wintypes.DWORD)]:
        if pid > 0 and (
            task_engine_owns_process(runtime_pid, pid)
            or (engine_pid is not None and task_engine_owns_process(engine_pid, pid))
        ):
            process = WindowsRetainedProcess(pid, allow_terminate=pid == runtime_pid)
            owner.processes.append(process)
            owner.transports.append(RuntimeTransportCleanup(process))
            assert task_engine_owns_process(runtime_pid, pid) or (
                engine_pid is not None and task_engine_owns_process(engine_pid, pid)
            )
            owned.append(process)
    assert any(process.pid == runtime_pid for process in owned)
    if require_worker:
        assert any(
            process.pid != runtime_pid and task_engine_owns_process(runtime_pid, process.pid) for process in owned
        ), "private admission did not expose a live owned worker descendant"
    return tuple(owned)


def retain_windows_task_engine(engine_pid: int, owner: WindowsInstalledTaskCleanup) -> WindowsRetainedProcess:
    """Keep the Task's native engine incarnation independently of each host attempt."""
    process = WindowsRetainedProcess(engine_pid)
    owner.processes.append(process)
    owner.transports.append(RuntimeTransportCleanup(process))
    return process


async def wait_windows_recovery_processes_gone(
    processes: tuple[WindowsRetainedProcess, ...], *, timeout: float
) -> None:
    deadline = time.monotonic() + timeout
    while any(process.alive() for process in processes):
        assert time.monotonic() < deadline, "exact retained runtime/worker processes remained live"
        await asyncio.sleep(0.05)


class WindowsInstalledTaskCleanup:
    """Own only this new exact installed task and retained native observation handles."""

    def __init__(self, task_name: str, binding: RuntimeServiceBinding) -> None:
        self.task_name, self.binding = task_name, binding
        self.adopted = False
        self.released = False
        self._native_retired = False
        self.pending_stop: WindowsSchedulerCall | None = None
        self.launch_possible = False
        self.runtime: InstalledWindowsRuntimeTask | None = None
        self.processes: list[WindowsOwnedProcess | WindowsRetainedProcess] = []
        self.transports: list[RuntimeTransportCleanup] = []
        self._lock = asyncio.Lock()

    async def close(self) -> None:
        """Join the original Stop, prove native exit, then delete the exact task."""
        async with self._lock:
            if self.released:
                return
            deadline = time.monotonic() + 25
            if self.adopted and not self._native_retired:
                if self.pending_stop is not None:
                    pending = self.pending_stop

                    async def settle_stop() -> BaseException | None:
                        failure = await asyncio.to_thread(pending.settle, timeout=max(0.0, deadline - time.monotonic()))
                        # An absent task row never retires its original thread.
                        self.pending_stop = None
                        return failure

                    failure = await await_cancellation_complete(settle_stop(), task_name="installed-task-cleanup-stop")
                    if failure is not None:
                        raise failure
                if self.launch_possible:
                    if self.runtime is None:
                        raise RuntimeError("possible runtime launch has no physical observation owner")
                    await self.runtime.prepare_physical_cleanup()
                    deadline = time.monotonic() + 25
                identity = await await_cancellation_complete(
                    asyncio.to_thread(
                        installed_windows_task_identity, self.task_name, self.binding, login_autostart=None
                    ),
                    task_name="installed-task-cleanup-identity",
                )
                if identity is not None:
                    while True:
                        state = await await_cancellation_complete(
                            asyncio.to_thread(exact_windows_task_state, self.task_name, identity),
                            task_name="installed-task-cleanup-stopped",
                        )
                        if state in (1, 3):
                            break
                        if state not in (2, WINDOWS_TASK_RUNNING):
                            raise RuntimeError("isolated installed task stop state is unknown")
                        if not self.launch_possible:
                            raise RuntimeError("installed task is active without a tracked launch")
                        if time.monotonic() >= deadline:
                            raise TimeoutError("isolated installed task has not stopped")
                        await asyncio.sleep(0.05)
                # Retain exact process handles until native exit is established,
                # including if task registration disappeared unexpectedly.
                for process in self.processes:
                    await await_cancellation_complete(
                        asyncio.to_thread(process.wait, timeout=max(0.0, deadline - time.monotonic())),
                        task_name="installed-task-cleanup-process-exit",
                    )
                if identity is not None:
                    await await_cancellation_complete(
                        asyncio.to_thread(delete_exact_windows_task, self.task_name, identity),
                        task_name="installed-task-cleanup-delete",
                    )
                # Physical death and exact task retirement are already proven.
                # Failed transport release cannot make this phase live again.
                self._native_retired = True
            await close_async_resources(
                *self.transports, task_name="installed-task-cleanup-handles", primary_error=None
            )
            self.released = True


class InstalledWindowsRuntimeTask:
    """Exact installed binding; CLI/TUI actions remain the real production callbacks."""

    def __init__(self, root: Path, endpoint: WindowsRuntimeEndpoint, binding: RuntimeServiceBinding) -> None:
        self.root, self.endpoint, self.binding = root, endpoint, binding
        self.product_version = binding.product_version
        self.task_name = runtime_service_name(binding)
        self.manager = WindowsTaskManager(binding)
        self.cleanup = WindowsInstalledTaskCleanup(self.task_name, binding)
        self.cleanup.runtime = self
        self.endpoint_owner = RuntimeTransportCleanup(endpoint)
        self.control: VerifiedRuntimeConnection | None = None
        self.runtime_boot: UUID | None = None
        self.stop_dispatched = False
        self.stop_accepted: RuntimeStopAccepted | None = None
        self.stop_failure: BaseException | None = None

    def mark_launch_possible(self) -> None:
        """Fence cleanup before dispatch without starting or warming the runtime."""
        self.cleanup.launch_possible = True

    def retain_transport_cleanup(self, error: BaseException) -> None:
        """Transfer actual framing owners, including an unreturned failed handshake."""
        for failure in async_cleanup_failures(error):
            for resource in failure.resources:
                if not isinstance(resource, RuntimeTransportCleanup):
                    continue
                for index, previous in enumerate(self.cleanup.transports):
                    if previous.resource is resource.resource:
                        self.cleanup.transports[index] = resource
                        break
                else:
                    self.cleanup.transports.append(resource)

    async def observe_live_process(self, *, deadline: float | None = None) -> tuple[WindowsOwnedProcess, UUID]:
        """Hold the kernel process that answers the verified original pipe twice."""
        from ctypes import wintypes

        import win32process

        deadline = time.monotonic() + 5 if deadline is None else deadline

        def capture() -> tuple[WindowsOwnedProcess, UUID]:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
            channel = self.endpoint.connect(timeout=min(3, remaining))
            connection = VerifiedRuntimeConnection(
                channel,
                expected=RuntimeClientHello(
                    product_version=self.product_version, storage_identity=self.endpoint.storage_identity
                ),
                deadline=deadline,
            )
            self.cleanup.transports.append(RuntimeTransportCleanup(connection))
            preview = connection.owner_control(RuntimeStopPreviewRequest(request_id=uuid4()), deadline=deadline)
            if not isinstance(preview, RuntimeStopPreview):
                raise RuntimeError("verified runtime did not return owner-control preview")
            if self.runtime_boot is not None and preview.runtime_boot_id != self.runtime_boot:
                raise RuntimeError("runtime incarnation changed before physical cleanup")
            self.runtime_boot = preview.runtime_boot_id
            pid = channel.peer.process_id
            if pid is None or pid <= 0:
                raise RuntimeError("verified runtime peer has no process identity")
            kernel = windows_native_library("kernel32")
            open_process = kernel.OpenProcess
            open_process.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
            open_process.restype = wintypes.HANDLE
            handle = open_process(_PROCESS_QUERY_LIMITED_INFORMATION | _SYNCHRONIZE, False, pid)
            if not handle:
                raise RuntimeError("verified runtime process handle could not be retained")
            raw_handle = int(handle)
            process = WindowsOwnedProcess(handle=raw_handle, pid=pid)
            self.cleanup.processes.append(process)
            self.cleanup.transports.append(RuntimeTransportCleanup(process))
            created = win32process.GetProcessTimes(raw_handle)["CreationTime"]
            after = connection.owner_control(RuntimeStopPreviewRequest(request_id=uuid4()), deadline=deadline)
            if not isinstance(after, RuntimeStopPreview) or after.runtime_boot_id != preview.runtime_boot_id:
                raise RuntimeError("runtime incarnation changed while retaining its process")
            if win32process.GetProcessTimes(raw_handle)["CreationTime"] != created:
                raise RuntimeError("retained runtime creation identity changed")
            self.control, self.runtime_boot = connection, preview.runtime_boot_id
            return process, preview.runtime_boot_id

        try:
            return await await_cancellation_complete(
                asyncio.to_thread(capture), task_name="installed-runtime-peer-observation"
            )
        except BaseException as error:
            self.retain_transport_cleanup(error)
            raise

    async def observe_replacement_process(
        self, previous: WindowsRetainedProcess, previous_boot: UUID, *, deadline: float
    ) -> tuple[WindowsOwnedProcess, UUID]:
        """Observe a fresh boot only after the exact retained old host has died."""
        if not any(process is previous for process in self.cleanup.processes):
            raise RuntimeError("old host has no retained task cleanup owner")
        if self.runtime_boot != previous_boot or previous.alive():
            raise RuntimeError("old runtime incarnation has not physically retired")
        self.control, self.runtime_boot = None, None
        while True:
            try:
                process, boot = await self.observe_live_process(deadline=deadline)
                if boot == previous_boot:
                    raise RuntimeError("replacement runtime retained the old boot identity")
                return process, boot
            except RuntimeRefusalError as error:
                if (
                    error.reason is not RuntimeRefusalCode.ENDPOINT_NOT_READY
                    or has_async_cleanup_failure(error)
                    or time.monotonic() >= deadline
                ):
                    raise
                await asyncio.sleep(min(0.05, max(0.0, deadline - time.monotonic())))

    async def prepare_physical_cleanup(self) -> None:
        """Pin a possible cold launch, then request its exact single-use owner stop."""
        # Configuration cannot start this task. Disable the exact owned login
        # trigger even when physical readiness cannot be established below.
        identity = await await_cancellation_complete(
            asyncio.to_thread(installed_windows_task_identity, self.task_name, self.binding, login_autostart=None),
            task_name="installed-task-physical-binding",
        )
        if identity is not None:
            await await_cancellation_complete(
                self.manager.configure(login_autostart=False), task_name="installed-task-disable-for-cleanup"
            )
        if not self.cleanup.processes or self.control is None:
            readiness_deadline = time.monotonic() + PROFILE_ADMISSION_TIMEOUT_SECONDS
            while True:
                try:
                    await self.observe_live_process(deadline=readiness_deadline)
                    break
                except RuntimeRefusalError as error:
                    if (
                        error.reason is not RuntimeRefusalCode.ENDPOINT_NOT_READY
                        or has_async_cleanup_failure(error)
                        or time.monotonic() >= readiness_deadline
                    ):
                        raise
                    await asyncio.sleep(min(0.05, max(0.0, readiness_deadline - time.monotonic())))
        alive = False
        for process in self.cleanup.processes:
            try:
                process.wait(timeout=0)
            except RuntimeRefusalError as error:
                if error.reason is not RuntimeRefusalCode.DEADLINE_EXCEEDED:
                    raise
                alive = True
        if not alive or self.stop_dispatched:
            # An uncertain dispatched stop is never repeated. The retained
            # process death wait below remains the only completion oracle.
            return
        connection, boot = self.control, self.runtime_boot
        if connection is None or boot is None:
            raise RuntimeError("runtime physical identity was not fully established")

        def request_stop() -> None:
            try:
                stop_deadline = time.monotonic() + 8
                preview = connection.owner_control(
                    RuntimeStopPreviewRequest(request_id=uuid4()), deadline=stop_deadline
                )
                if not isinstance(preview, RuntimeStopPreview) or preview.runtime_boot_id != boot:
                    raise RuntimeError("cleanup preview did not match the retained runtime")
                self.stop_dispatched = True
                accepted = connection.owner_control(
                    RuntimeStopConfirm(
                        request_id=uuid4(),
                        runtime_boot_id=boot,
                        preview_id=preview.preview_id,
                        acknowledge_all_profiles_and_work=True,
                    ),
                    deadline=stop_deadline,
                )
                if not isinstance(accepted, RuntimeStopAccepted) or accepted.runtime_boot_id != boot:
                    raise RuntimeError("cleanup stop acknowledgement did not match the retained runtime")
                self.stop_accepted = accepted
            except BaseException as error:
                self.retain_transport_cleanup(error)
                self.stop_failure = error

        try:
            await await_cancellation_complete(
                asyncio.to_thread(request_stop), task_name="installed-runtime-physical-stop"
            )
        except BaseException as error:
            if self.stop_failure is not None and self.stop_failure is not error:
                error.__dict__["installed_runtime_stop_error"] = self.stop_failure
            raise
        if self.stop_failure is not None:
            raise self.stop_failure


@asynccontextmanager
async def installed_windows_runtime_task(
    tmp_path: Path, *, storage_root: Path | None = None
) -> AsyncIterator[InstalledWindowsRuntimeTask]:
    """Reserve one new isolated task; retain partial configure/start failures canonically."""
    require_windows_manager_desktop()
    import sysconfig

    root = make_windows_fixture_root(tmp_path) if storage_root is None else require_windows_fixture_root(storage_root)
    executable = Path(sysconfig.get_path("scripts")) / "cadrumo-runtime.exe"
    if not executable.is_file():
        pytest.skip("installed runtime executable unavailable")
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    binding = RuntimeServiceBinding(
        executable=str(executable.resolve(strict=True)),
        storage_root=str(root),
        storage_identity=endpoint.storage_identity,
        os_owner_id=windows_fixture_owner_sid(),
        product_version=version("cadrumo"),
    )
    task = InstalledWindowsRuntimeTask(root, endpoint, binding)
    primary_errors: list[BaseException] = []
    try:
        before = await task.manager.inspect()
        if not before.available:
            pytest.skip("Task Scheduler unavailable")
        if before.provisioned:
            raise RuntimeError("unique installed-runtime task name already exists")
        # Mark adoption before yielding: a configure call can commit and lose
        # its acknowledgement. Pre-existing tasks never enter this ownership.
        task.cleanup.adopted = True
        configured = await await_cancellation_complete(
            task.manager.configure(login_autostart=False), task_name="installed-task-fixture-configure"
        )
        if not configured.binding_matches or configured.login_autostart:
            raise RuntimeError("isolated installed task did not retain its on-demand binding")
        yield task
    except BaseException as error:
        primary_errors.append(error)
        raise
    finally:
        await close_async_resources(
            task.cleanup,
            task.endpoint_owner,
            task_name="installed-windows-runtime-task-close",
            primary_error=primary_errors[0] if primary_errors else None,
        )
