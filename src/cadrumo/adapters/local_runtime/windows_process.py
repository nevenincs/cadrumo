"""Creation-time Windows Job membership for operation-owned child resources."""

from __future__ import annotations

import asyncio
import ctypes
import math
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from threading import Lock
from typing import cast

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.async_cleanup import AsyncResourceCleanupError, await_cancellation_complete

if sys.platform == "win32":
    from ctypes import wintypes

    class _StartupInfo(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("lpReserved", wintypes.LPWSTR),
            ("lpDesktop", wintypes.LPWSTR),
            ("lpTitle", wintypes.LPWSTR),
            ("dwX", wintypes.DWORD),
            ("dwY", wintypes.DWORD),
            ("dwXSize", wintypes.DWORD),
            ("dwYSize", wintypes.DWORD),
            ("dwXCountChars", wintypes.DWORD),
            ("dwYCountChars", wintypes.DWORD),
            ("dwFillAttribute", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("wShowWindow", wintypes.WORD),
            ("cbReserved2", wintypes.WORD),
            ("lpReserved2", ctypes.c_void_p),
            ("hStdInput", wintypes.HANDLE),
            ("hStdOutput", wintypes.HANDLE),
            ("hStdError", wintypes.HANDLE),
        ]

    class _StartupInfoEx(ctypes.Structure):
        _fields_ = [("startup", _StartupInfo), ("attributes", ctypes.c_void_p)]

    class _ProcessInformation(ctypes.Structure):
        _fields_ = [
            ("process", wintypes.HANDLE),
            ("thread", wintypes.HANDLE),
            ("pid", wintypes.DWORD),
            ("tid", wintypes.DWORD),
        ]


def _launch_in_job(
    job: int, *, executable: Path, arguments: Sequence[str], directory: Path, environment: Mapping[str, str]
) -> tuple[int, int, int]:
    if sys.platform != "win32":
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    initialize = kernel.InitializeProcThreadAttributeList
    initialize.argtypes = (ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.c_size_t))
    initialize.restype = wintypes.BOOL
    update = kernel.UpdateProcThreadAttribute
    update.argtypes = (
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.c_size_t,
        ctypes.c_void_p,
        ctypes.c_size_t,
        ctypes.c_void_p,
        ctypes.c_void_p,
    )
    update.restype = wintypes.BOOL
    destroy = kernel.DeleteProcThreadAttributeList
    destroy.argtypes = (ctypes.c_void_p,)
    destroy.restype = None
    create = kernel.CreateProcessW
    create.argtypes = (
        wintypes.LPCWSTR,
        wintypes.LPWSTR,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.BOOL,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.LPCWSTR,
        ctypes.POINTER(_StartupInfoEx),
        ctypes.POINTER(_ProcessInformation),
    )
    create.restype = wintypes.BOOL
    size = ctypes.c_size_t()
    initialize(None, 1, 0, ctypes.byref(size))
    if size.value == 0:
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    attributes = ctypes.create_string_buffer(size.value)
    if not initialize(attributes, 1, 0, ctypes.byref(size)):
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    try:
        jobs = (wintypes.HANDLE * 1)(job)
        # PROC_THREAD_ATTRIBUTE_JOB_LIST: the kernel assigns before any child
        # code runs. No create-then-assign or suspended unowned orphan window.
        if not update(attributes, 0, 0x0002000D, jobs, ctypes.sizeof(jobs), None, None):
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        startup = _StartupInfoEx()
        startup.startup.cb = ctypes.sizeof(startup)
        startup.attributes = ctypes.addressof(attributes)
        information = _ProcessInformation()
        command = ctypes.create_unicode_buffer(subprocess.list2cmdline((str(executable), *arguments)))
        block = ctypes.create_unicode_buffer(
            "\0".join(f"{key}={value}" for key, value in sorted(environment.items(), key=lambda item: item[0].upper()))
            + "\0\0"
        )
        # EXTENDED_STARTUPINFO_PRESENT | CREATE_UNICODE_ENVIRONMENT |
        # CREATE_NO_WINDOW. Inherit no handles, including this job handle.
        if not create(
            str(executable),
            command,
            None,
            None,
            False,
            0x08080400,
            block,
            str(directory),
            ctypes.byref(startup),
            ctypes.byref(information),
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        return int(information.process), int(information.thread), int(information.pid)
    finally:
        destroy(attributes)


class WindowsOwnedProcess:
    """Retained child handles; closing them does not dispose of the owning job."""

    def __init__(self, *, handle: int, pid: int, thread_handle: int | None = None) -> None:
        """Take ownership of the process and initial thread handles at launch."""
        self._handle: int | None = handle
        self._thread_handle = thread_handle
        self.pid = pid

    def wait(self, *, timeout: float) -> int:
        """Wait for this exact child, without reopening a possibly reused PID."""
        import win32event
        import win32process

        if self._handle is None or not math.isfinite(timeout) or timeout < 0:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        result = win32event.WaitForSingleObject(self._handle, min(0xFFFFFFFE, math.ceil(timeout * 1000)))
        if result == win32event.WAIT_TIMEOUT:
            raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
        if result != win32event.WAIT_OBJECT_0:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        # pywin32 reports the DWORD as a signed C long, so NTSTATUS-style
        # crash codes such as 0xC0000005 would otherwise read as negative.
        return win32process.GetExitCodeProcess(self._handle) & 0xFFFFFFFF

    def close(self) -> None:
        """Attempt both handles, retaining each until its native release succeeds."""
        import win32api

        failures: list[BaseException] = []
        if self._thread_handle is not None:
            try:
                win32api.CloseHandle(self._thread_handle)
            except BaseException as error:
                failures.append(error)
            else:
                self._thread_handle = None
        if self._handle is not None:
            try:
                win32api.CloseHandle(self._handle)
            except BaseException as error:
                failures.append(error)
            else:
                self._handle = None
        if failures:
            raise failures[0]


def unreturned_windows_process_scope(error: BaseException) -> WindowsProcessScope | None:
    """Return the exact unreturned scope retained after failed native cleanup."""
    candidate = error.__dict__.get("_windows_process_scope_candidate")
    return candidate if isinstance(candidate, WindowsProcessScope) else None


class WindowsProcessScope:
    """Kill-on-close job usable by the existing operation cleanup owner.

    Ordinary child creation inherits this job even with a new process group.
    Breakaway is disabled. Processes created by external brokers are outside
    this primitive's guarantee and require separate capability evidence.
    """

    _lock: Lock

    def __init__(self) -> None:
        """Create a noninherited job and verify its kill and breakaway policy."""
        if sys.platform != "win32":
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        import pywintypes
        import win32api
        import win32job

        self._lock = Lock()
        self._children: list[WindowsOwnedProcess] = []
        self._job: int | None = None
        self._launch_fenced = False
        self._terminated = False
        self._termination_failure: RuntimeRefusalCode | None = None
        try:
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            create_job = kernel.CreateJobObjectW
            create_job.argtypes = (ctypes.c_void_p, wintypes.LPCWSTR)
            create_job.restype = wintypes.HANDLE
            job = create_job(None, None)
            if not job:
                raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
            self._job = int(job)
            set_handle_flags = cast("Callable[[int, int, int], None]", win32api.SetHandleInformation)
            query_job = cast("Callable[[int, int], object]", win32job.QueryInformationJobObject)
            set_job = cast("Callable[[int, int, object], None]", win32job.SetInformationJobObject)
            set_handle_flags(self._job, 1, 0)
            information = cast("dict[str, object]", query_job(self._job, win32job.JobObjectExtendedLimitInformation))
            basic_limits = cast("dict[str, object]", information["BasicLimitInformation"])
            basic_limits["LimitFlags"] = win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            set_job(self._job, win32job.JobObjectExtendedLimitInformation, information)
            actual = cast("dict[str, object]", query_job(self._job, win32job.JobObjectExtendedLimitInformation))
            actual_limits = cast("dict[str, object]", actual["BasicLimitInformation"])
            if actual_limits["LimitFlags"] != win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE:
                raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        except BaseException as error:
            primary = (
                RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
                if isinstance(error, pywintypes.error)
                else error
            )
            try:
                self.terminate()
            except BaseException as cleanup:
                self._retain_cleanup(primary, (error, cleanup))
                if self._job is not None:
                    primary.__dict__["_windows_process_scope_candidate"] = self
            if primary is error:
                raise
            raise primary from error

    def launch(
        self, *, executable: Path, arguments: Sequence[str], directory: Path, environment: Mapping[str, str]
    ) -> WindowsOwnedProcess:
        """Launch an absolute executable into the job with an explicit environment.

        Credentials must travel through separately authenticated IPC, never
        these arguments or environment values. No parent environment is merged.
        """
        if not executable.is_absolute() or not directory.is_absolute():
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        if any("\0" in argument for argument in arguments) or any(
            not key or "=" in key or "\0" in key or "\0" in value for key, value in environment.items()
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        if len({key.upper() for key in environment}) != len(environment):
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        try:
            executable = executable.resolve(strict=True)
            directory = directory.resolve(strict=True)
        except (OSError, ValueError):
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE) from None
        with self._lock:
            if self._launch_fenced or self._job is None:
                raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
            handle, thread_handle, pid = _launch_in_job(
                self._job,
                executable=executable,
                arguments=arguments,
                directory=directory,
                environment=environment,
            )
            process = WindowsOwnedProcess(handle=handle, thread_handle=thread_handle, pid=pid)
            self._children.append(process)
            return process

    def terminate(self, *, timeout: float = 2.0) -> None:
        """Fence launch, terminate this job and verify no active members to a bound."""
        import pywintypes
        import win32api
        import win32job

        if not math.isfinite(timeout) or timeout < 0:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        with self._lock:
            self._launch_fenced = True
            deadline = time.monotonic() + timeout
            primary: BaseException | None = None
            native_cause: BaseException | None = None
            failures: list[BaseException] = []
            if self._job is not None and not self._terminated:
                try:
                    terminate_job = cast("Callable[[int, int], None]", win32job.TerminateJobObject)
                    query_job = cast("Callable[[int, int], object]", win32job.QueryInformationJobObject)
                    terminate_job(self._job, 1)
                    while cast("dict[str, object]", query_job(self._job, win32job.JobObjectBasicAccountingInformation))[
                        "ActiveProcesses"
                    ]:
                        if time.monotonic() >= deadline:
                            raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
                        time.sleep(min(0.01, max(0, deadline - time.monotonic())))
                    self._terminated = True
                    self._termination_failure = None
                except BaseException as error:
                    if isinstance(error, pywintypes.error):
                        primary = RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
                        native_cause = error
                    else:
                        primary = error
                    self._termination_failure = (
                        error.reason
                        if isinstance(error, RuntimeRefusalError)
                        else RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE
                    )
            # Preserve the observation handle when termination is unproven.
            # Kill-on-close alone cannot prove that independently grouped
            # descendants have stopped; a later retry must observe this job.
            if self._job is not None and self._terminated:
                try:
                    win32api.CloseHandle(self._job)
                except BaseException as error:
                    failures.append(error)
                else:
                    self._job = None
            retained_children: list[WindowsOwnedProcess] = []
            for child in self._children:
                try:
                    child.close()
                except BaseException as error:
                    failures.append(error)
                    retained_children.append(child)
            self._children = retained_children
            if primary is not None:
                self._retain_cleanup(primary, (native_cause or primary, *failures))
                if native_cause is not None:
                    raise primary from native_cause
                raise primary
            if failures:
                raise AsyncResourceCleanupError(
                    (self,), tuple(failures), retry_task_name="windows-process-scope-release", close_attempts=1
                ) from failures[0]

    def _retain_cleanup(self, primary: BaseException, failures: tuple[BaseException, ...]) -> None:
        """Keep one original scope as the retry authority on the exact primary."""
        cleanup = AsyncResourceCleanupError(
            (self,), failures, retry_task_name="windows-process-scope-release", close_attempts=1
        )
        seen: set[int] = set()
        for error in (primary, *failures):
            attachments: list[object] = [error] if isinstance(error, AsyncResourceCleanupError) else []
            attachments.extend(error.__dict__.get(name) for name in ("async_cleanup_error", "cleanup_error"))
            for previous in attachments:
                if isinstance(previous, AsyncResourceCleanupError) and id(previous) not in seen:
                    seen.add(id(previous))
                    cleanup = previous.merged_with(cleanup)
        primary.__dict__["async_cleanup_error"] = cleanup
        if "cleanup_error" in primary.__dict__ or isinstance(primary, asyncio.CancelledError):
            primary.__dict__["cleanup_error"] = cleanup

    def active_process_ids(self) -> tuple[int, ...]:
        """Snapshot current job members for health; PIDs confer no authority."""
        import win32job

        with self._lock:
            if self._termination_failure is not None:
                raise RuntimeRefusalError(self._termination_failure)
            if self._job is None:
                return ()
            query_job = cast("Callable[[int, int], object]", win32job.QueryInformationJobObject)
            members: object = query_job(self._job, win32job.JobObjectBasicProcessIdList)
            if not isinstance(members, tuple):
                raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
            values = cast("tuple[object, ...]", members)
            if any(not isinstance(pid, int) or pid <= 0 for pid in values):
                raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
            validated = cast("tuple[int, ...]", values)
            return tuple(int(pid) for pid in validated)

    def contains_process(self, process_handle: int) -> bool:
        """Corroborate a retained live native process against this exact Job."""
        if sys.platform != "win32":
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        import win32event

        with self._lock:
            if self._launch_fenced or self._job is None or self._termination_failure is not None:
                return False
            if win32event.WaitForSingleObject(process_handle, 0) != win32event.WAIT_TIMEOUT:
                return False
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            observe = kernel.IsProcessInJob
            observe.argtypes = (wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL))
            observe.restype = wintypes.BOOL
            belongs = wintypes.BOOL()
            if not observe(process_handle, self._job, ctypes.byref(belongs)):
                raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
            return bool(belongs.value)

    async def close(self) -> None:
        """Settle through OperationCleanupOwner without blocking its event loop."""
        failures: list[BaseException] = []

        def release() -> None:
            # Transport terminal cancellation as a value; otherwise shield
            # turns a native CancelledError into a different caller cancel.
            try:
                self.terminate()
            except BaseException as error:
                failures.append(error)

        try:
            await await_cancellation_complete(asyncio.to_thread(release), task_name="windows-process-scope-release")
        except asyncio.CancelledError as primary:
            if failures:
                self._retain_cleanup(primary, tuple(failures))
            raise
        if failures:
            raise failures[0]
