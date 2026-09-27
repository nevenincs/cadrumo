"""Creation-time Windows Job membership for operation-owned child resources."""

from __future__ import annotations

import asyncio
import ctypes
import math
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from threading import Lock

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError

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
) -> tuple[int, int]:
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
    close = kernel.CloseHandle
    close.argtypes = (wintypes.HANDLE,)
    close.restype = wintypes.BOOL
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
        close(information.thread)
        return int(information.process), int(information.pid)
    finally:
        destroy(attributes)


class WindowsOwnedProcess:
    """A retained process handle; closing it does not dispose of the owning job."""

    def __init__(self, *, handle: int, pid: int) -> None:
        """Take ownership of the native process handle returned at launch."""
        self._handle: int | None = handle
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
        return win32process.GetExitCodeProcess(self._handle)

    def close(self) -> None:
        """Release the retained process handle after its owning resource settles."""
        import win32api

        if self._handle is not None:
            win32api.CloseHandle(self._handle)
            self._handle = None


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
            win32api.SetHandleInformation(self._job, 1, 0)
            information = win32job.QueryInformationJobObject(self._job, win32job.JobObjectExtendedLimitInformation)
            information["BasicLimitInformation"]["LimitFlags"] = win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            win32job.SetInformationJobObject(self._job, win32job.JobObjectExtendedLimitInformation, information)
            actual = win32job.QueryInformationJobObject(self._job, win32job.JobObjectExtendedLimitInformation)
            if actual["BasicLimitInformation"]["LimitFlags"] != win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE:
                raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        except (pywintypes.error, RuntimeRefusalError):
            if self._job is not None:
                win32api.CloseHandle(self._job)
                self._job = None
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE) from None

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
            if self._job is None:
                raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
            handle, pid = _launch_in_job(
                self._job,
                executable=executable,
                arguments=arguments,
                directory=directory,
                environment=environment,
            )
            process = WindowsOwnedProcess(handle=handle, pid=pid)
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
            if self._termination_failure is not None:
                raise RuntimeRefusalError(self._termination_failure)
            if self._job is None:
                return
            job, self._job = self._job, None
            deadline = time.monotonic() + timeout
            try:
                win32job.TerminateJobObject(job, 1)
                while win32job.QueryInformationJobObject(job, win32job.JobObjectBasicAccountingInformation)[
                    "ActiveProcesses"
                ]:
                    if time.monotonic() >= deadline:
                        raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
                    time.sleep(min(0.01, max(0, deadline - time.monotonic())))
            except RuntimeRefusalError as error:
                # Releasing the last job handle requests termination, but does
                # not prove it finished. Do not turn a retry into false success
                # after discarding the native handle needed for observation.
                self._termination_failure = error.reason
                raise
            except pywintypes.error:
                self._termination_failure = RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE
                raise RuntimeRefusalError(self._termination_failure) from None
            finally:
                win32api.CloseHandle(job)
                for child in self._children:
                    child.close()
                self._children.clear()

    def active_process_ids(self) -> tuple[int, ...]:
        """Snapshot current job members for health; PIDs confer no authority."""
        import win32job

        with self._lock:
            if self._termination_failure is not None:
                raise RuntimeRefusalError(self._termination_failure)
            if self._job is None:
                return ()
            members: object = win32job.QueryInformationJobObject(self._job, win32job.JobObjectBasicProcessIdList)
            if not isinstance(members, tuple) or any(not isinstance(pid, int) or pid <= 0 for pid in members):
                raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
            return tuple(int(pid) for pid in members)

    async def close(self) -> None:
        """Settle through OperationCleanupOwner without blocking its event loop."""
        await asyncio.to_thread(self.terminate)
