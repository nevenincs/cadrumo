"""Creation-time Windows Job membership for operation-owned child resources."""

from __future__ import annotations

import asyncio
import ctypes
import math
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from logging import DEBUG, WARNING
from pathlib import Path
from threading import Lock
from typing import BinaryIO, Final, cast

from cadrumo.core.async_cleanup import AsyncResourceCleanupError, await_cancellation_complete
from cadrumo.core.diagnostic_log import DiagnosticValue, diagnostic_error_fields, diagnostic_event
from cadrumo.core.logging import get_logger

from ..contracts.contracts import RefusalCode, RefusalError
from .windows_job_launch import launch_in_windows_job
from .windows_native_io import NativeWindowsHandle, native_windows_call, owned_windows_handle
from .windows_owned_process import WindowsOwnedProcess
from .windows_process_observation import watch_windows_late_exit
from .windows_process_pipes import windows_parent_streams, windows_standard_pipes

_LOGGER = get_logger(__name__)

_LATE_EXIT_OBSERVATION_SECONDS: Final = 60.0
"""How long, after a termination missed its bound, a child that had not yet exited is still watched."""

if sys.platform == "win32":
    from ctypes import wintypes


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
            raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
        import pywintypes
        import win32api
        import win32job

        self._lock = Lock()
        self._children: list[WindowsOwnedProcess] = []
        self._job: int | None = None
        self._launch_fenced = False
        self._terminated = False
        self._termination_failure: RefusalCode | None = None
        try:
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            create_job = kernel.CreateJobObjectW
            create_job.argtypes = (ctypes.c_void_p, wintypes.LPCWSTR)
            create_job.restype = wintypes.HANDLE
            job = create_job(None, None)
            if not job:
                raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
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
                raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
        except BaseException as error:
            primary = (
                RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE) if isinstance(error, pywintypes.error) else error
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
        executable, directory = _resolve_launch_paths(executable, directory, arguments, environment)
        with self._lock:
            if self._launch_fenced or self._job is None:
                raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
            handle, thread_handle, pid = launch_in_windows_job(
                self._job,
                executable=executable,
                arguments=arguments,
                directory=directory,
                environment=environment,
            )
            process = WindowsOwnedProcess(handle=handle, thread_handle=thread_handle, pid=pid)
            self._children.append(process)
            return process

    def launch_with_standard_pipes(
        self, *, executable: Path, arguments: Sequence[str], directory: Path, environment: Mapping[str, str]
    ) -> tuple[WindowsOwnedProcess, BinaryIO, BinaryIO, BinaryIO]:
        """Launch into the job with private standard-input, standard-output and standard-error pipes.

        Return the process, the writable end of its standard input and the
        readable ends of its standard output and standard error. The caller
        owns draining standard error: a child that fills an unread pipe blocks.
        Only the three child ends are inherited; secrets travel on the
        returned standard input, never the arguments or environment.
        """
        if sys.platform != "win32":
            raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
        executable, directory = _resolve_launch_paths(executable, directory, arguments, environment)
        child_ends, parent_ends = windows_standard_pipes()
        try:
            with self._lock:
                if self._launch_fenced or self._job is None:
                    raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
                handle, thread_handle, pid = launch_in_windows_job(
                    self._job,
                    executable=executable,
                    arguments=arguments,
                    directory=directory,
                    environment=environment,
                    standard_handles=cast("tuple[int, int, int]", tuple(int(end) for end in child_ends)),
                )
                process = WindowsOwnedProcess(handle=handle, thread_handle=thread_handle, pid=pid)
                self._children.append(process)
        except BaseException:
            for end in parent_ends:
                end.Close()
            raise
        finally:
            for end in child_ends:
                end.Close()
        return process, *windows_parent_streams(parent_ends)

    def terminate(self, *, timeout: float = 2.0) -> None:
        """Fence launch, terminate this job and verify no active members to a bound."""
        if not math.isfinite(timeout) or timeout < 0:
            raise RefusalError(RefusalCode.UNAVAILABLE)
        with self._lock:
            self._launch_fenced = True
            deadline = time.monotonic() + timeout
            primary: BaseException | None = None
            native_cause: BaseException | None = None
            failures: list[BaseException] = []
            if self._job is not None and not self._terminated:
                observed = _JobTermination(started=time.monotonic(), timeout=timeout)
                try:
                    _terminate_windows_job(self._job, deadline, observed)
                    self._terminated = True
                    self._termination_failure = None
                except BaseException as error:
                    primary, native_cause = self._record_termination_failure(error)
                    observed.failure = error
                with suppress(Exception):
                    self._report_termination(observed)
            failures.extend(self._release_terminated_job())
            failures.extend(self._release_children())
            if primary is not None:
                self._retain_cleanup(primary, (native_cause or primary, *failures))
                if native_cause is not None:
                    raise primary from native_cause
                raise primary
            if failures:
                raise AsyncResourceCleanupError(
                    (self,), tuple(failures), retry_task_name="windows-process-scope-release", close_attempts=1
                ) from failures[0]

    def _report_termination(self, observed: _JobTermination) -> None:
        """Log how long the Job took to end and how each child exited, before the child handles are released.

        A child still running after a missed bound is watched in the
        background. Reporting never changes the termination outcome.
        """
        failure = observed.failure
        expired = isinstance(failure, RefusalError) and failure.reason is RefusalCode.TIMEOUT
        fields: dict[str, DiagnosticValue] = {
            "elapsed_seconds": round(max(0.0, time.monotonic() - observed.started), 3),
            "timeout_seconds": observed.timeout,
            "job_empty_seconds": observed.job_empty,
            "members_signalled_seconds": observed.members_signalled,
            "outcome": "completed" if failure is None else "deadline_expired" if expired else "failed",
        }
        if failure is not None and not expired:
            fields.update(diagnostic_error_fields(failure))
        diagnostic_event(
            _LOGGER,
            "windows_job_termination_observed",
            fields=fields,
            level=DEBUG if failure is None else WARNING,
            primary_error=failure,
        )
        self._report_child_terminations(failure)
        if expired:
            watch_windows_late_exit(self._children, started=observed.started, seconds=_LATE_EXIT_OBSERVATION_SECONDS)

    def _report_child_terminations(self, failure: BaseException | None) -> None:
        for child in self._children:
            with suppress(Exception):
                code = child.exit_code()
                diagnostic_event(
                    _LOGGER,
                    "windows_job_child_exit_observed",
                    fields={
                        "child_process_id": child.pid,
                        "exit_code": code,
                        "outcome": "running" if code is None else "exited",
                    },
                    level=DEBUG if code is not None else WARNING,
                    primary_error=failure,
                )

    def _record_termination_failure(self, error: BaseException) -> tuple[BaseException, BaseException | None]:
        """Retain the exact native termination refusal for later health and retry."""
        import pywintypes

        native_cause: BaseException | None = None
        if isinstance(error, pywintypes.error):
            primary = RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
            native_cause = error
        else:
            primary = error
        self._termination_failure = (
            error.reason if isinstance(error, RefusalError) else RefusalCode.CONTAINMENT_UNAVAILABLE
        )
        return primary, native_cause

    def _release_terminated_job(self) -> list[BaseException]:
        """Preserve the observation handle until native termination is proven."""
        import win32api

        failures: list[BaseException] = []
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
        return failures

    def _release_children(self) -> list[BaseException]:
        """Attempt every child handle and retain each failed release for retry."""
        failures: list[BaseException] = []
        retained_children: list[WindowsOwnedProcess] = []
        for child in self._children:
            try:
                child.close()
            except BaseException as error:
                failures.append(error)
                retained_children.append(child)
        self._children = retained_children
        return failures

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
        with self._lock:
            if self._termination_failure is not None:
                raise RefusalError(self._termination_failure)
            if self._job is None:
                return ()
            return _job_process_ids(self._job)

    def work_done(self) -> tuple[int, ...] | None:
        """The job's accumulated processor time, page faults, processes and I/O, or ``None`` once it is released.

        The values move while any member runs, faults a page in, starts or
        ends, or performs I/O, so two equal readings mean the whole tree did
        nothing in between. It is one kernel query, cheap enough to sample.
        """
        if sys.platform != "win32":
            raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
        import win32job

        with self._lock:
            if self._job is None:
                return None
            query_job = cast("Callable[[int, int], object]", win32job.QueryInformationJobObject)
            information = cast(
                "dict[str, dict[str, int]]", query_job(self._job, win32job.JobObjectBasicAndIoAccountingInformation)
            )
        basic, io = information["BasicInfo"], information["IoInfo"]
        return (
            basic["TotalUserTime"],
            basic["TotalKernelTime"],
            basic["TotalPageFaultCount"],
            basic["TotalProcesses"],
            basic["ActiveProcesses"],
            io["ReadOperationCount"],
            io["WriteOperationCount"],
            io["OtherOperationCount"],
        )

    def contains_process(self, process_handle: int) -> bool:
        """Corroborate a retained live native process against this exact Job."""
        if sys.platform != "win32":
            raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
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
                raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
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


def _resolve_launch_paths(
    executable: Path, directory: Path, arguments: Sequence[str], environment: Mapping[str, str]
) -> tuple[Path, Path]:
    if not executable.is_absolute() or not directory.is_absolute():
        raise RefusalError(RefusalCode.UNAVAILABLE)
    _require_launch_environment(arguments, environment)
    try:
        return executable.resolve(strict=True), directory.resolve(strict=True)
    except (OSError, ValueError):
        raise RefusalError(RefusalCode.UNAVAILABLE) from None


def _require_launch_environment(arguments: Sequence[str], environment: Mapping[str, str]) -> None:
    """Refuse malformed or case-ambiguous explicit child process inputs."""
    if any("\0" in argument for argument in arguments) or any(
        not key or "=" in key or "\0" in key or "\0" in value for key, value in environment.items()
    ):
        raise RefusalError(RefusalCode.UNAVAILABLE)
    if len({key.upper() for key in environment}) != len(environment):
        raise RefusalError(RefusalCode.UNAVAILABLE)


@dataclass(slots=True)
class _JobTermination:
    """What one termination observed: seconds after the kill request, or ``None`` for what the bound did not reach."""

    started: float
    timeout: float
    job_empty: float | None = None
    members_signalled: float | None = None
    failure: BaseException | None = None


def _terminate_windows_job(job: int, deadline: float, observed: _JobTermination) -> None:
    """Observe this exact Job empty and its members' process objects signaled within the original budget.

    The kernel removes an exiting process from its Job's active count before
    the process object is signaled and its handle table is gone, so an empty
    count alone does not prove that a member has stopped. Each member present
    before termination is retained by handle and waited on as well. A process
    created between that snapshot and termination is ended by the same native
    termination and counted out, but only the count observes it.
    """
    import win32job

    terminate_job = cast("Callable[[int, int], None]", win32job.TerminateJobObject)
    query_job = cast("Callable[[int, int], object]", win32job.QueryInformationJobObject)
    try:
        members = _retain_job_members(job)
    except BaseException:
        # The members still end; termination stays unproven and the caller keeps the Job for a retry.
        terminate_job(job, 1)
        raise
    try:
        terminate_job(job, 1)
        requested = time.monotonic()
        while cast("dict[str, object]", query_job(job, win32job.JobObjectBasicAccountingInformation))[
            "ActiveProcesses"
        ]:
            if time.monotonic() >= deadline:
                raise RefusalError(RefusalCode.TIMEOUT)
            time.sleep(min(0.01, max(0, deadline - time.monotonic())))
        observed.job_empty = round(time.monotonic() - requested, 3)
        _await_job_members(members, deadline)
        observed.members_signalled = round(time.monotonic() - requested, 3)
    finally:
        _release_job_members(members)


def _await_job_members(members: tuple[NativeWindowsHandle, ...], deadline: float) -> None:
    """Wait for each retained member's process object to be signaled before the deadline."""
    if not members:
        return
    import win32event

    for member in members:
        remaining = max(0.0, deadline - time.monotonic())
        result = win32event.WaitForSingleObject(int(member), min(0xFFFFFFFE, math.ceil(remaining * 1000)))
        if result == win32event.WAIT_TIMEOUT:
            raise RefusalError(RefusalCode.TIMEOUT)
        if result != win32event.WAIT_OBJECT_0:
            raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)


def _release_job_members(members: tuple[NativeWindowsHandle, ...]) -> None:
    """Close every retained member handle; these handles are observation only and own nothing."""
    failures: list[BaseException] = []
    for member in members:
        try:
            member.Close()
        except BaseException as error:
            failures.append(error)
    if failures:
        raise failures[0]


def _job_process_ids(job: int) -> tuple[int, ...]:
    """Read only initialized PID slots, with bounded growth while membership changes."""
    if sys.platform != "win32":
        raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    query = kernel.QueryInformationJobObject
    query.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p)
    query.restype = wintypes.BOOL
    capacity = 64
    for _ in range(8):
        buffer = ctypes.create_string_buffer(8 + ctypes.sizeof(ctypes.c_size_t) * capacity)
        succeeded = query(job, 3, buffer, ctypes.sizeof(buffer), None)
        assigned = ctypes.c_uint32.from_buffer(buffer).value
        written = ctypes.c_uint32.from_buffer(buffer, 4).value
        if succeeded:
            if written > capacity:
                break
            # pywin32 sizes its tuple from the assigned count but fills only
            # the returned count. Exiting processes can leave those unequal,
            # exposing NULL tuple entries that crash ordinary Python iteration.
            entries = (ctypes.c_size_t * written).from_buffer(buffer, 8)
            pids = tuple(int(pid) for pid in entries)
            if any(pid <= 0 for pid in pids):
                break
            return pids
        error = ctypes.get_last_error()
        if error != 234:  # ERROR_MORE_DATA
            raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE, check=f"job_process_ids_winerror_{error}")
        capacity = max(capacity * 2, assigned)
        if capacity > 65536:
            break
    raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE, check="job_process_ids_unavailable")


def _retain_job_members(job: int) -> tuple[NativeWindowsHandle, ...]:
    """Open a waitable handle on every current member, confirmed in this Job so a reused PID is never waited on."""
    if sys.platform != "win32":
        raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
    import pywintypes
    import win32api

    listed = _job_process_ids(job)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    observe = kernel.IsProcessInJob
    observe.argtypes = (wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL))
    observe.restype = wintypes.BOOL
    retained: list[NativeWindowsHandle] = []
    try:
        for pid in listed:
            try:
                # SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION: wait on it and ask its Job, nothing more.
                opened = native_windows_call(win32api, "OpenProcess", 0x00100000 | 0x00001000, False, pid)
            except pywintypes.error as error:
                if error.winerror == 87:
                    # ERROR_INVALID_PARAMETER: this member has already exited and its PID is free.
                    continue
                raise
            handle = owned_windows_handle(opened)
            belongs = wintypes.BOOL()
            if not observe(int(handle), job, ctypes.byref(belongs)):
                handle.Close()
                raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
            if belongs.value:
                retained.append(handle)
            else:
                handle.Close()
    except BaseException:
        for handle in retained:
            handle.Close()
        raise
    return tuple(retained)
