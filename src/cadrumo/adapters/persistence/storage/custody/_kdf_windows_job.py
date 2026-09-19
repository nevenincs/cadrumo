"""Windows Job Object boundary for the supervised profile KDF worker.

The Job Object structures below are laid out with :mod:`ctypes.wintypes`, which
raises on import on every platform that is not Windows -- its ``VARIANT_BOOL``
names a ``_type_`` the other platforms do not support. Importing this module
therefore has to stay safe everywhere, because the KDF process boundary that
consumes :class:`_WindowsJob` is imported on every platform.

The module-level ``sys.platform == "win32"`` block is what makes that true, and
it is also the only guard shape every checker this project runs narrows on, so
the Windows API resolves when the tree is analysed for Linux or macOS. The
``else`` branch is the same boundary on a platform that has no Job Object: it
refuses, exactly as the supervisor would if the object could not be created.
"""

from __future__ import annotations

import ctypes
import subprocess
import sys
from typing import Any, Final, cast

from ._kdf_refusals import supervision_refusal as _supervision_refusal
from ._kdf_worker_limits import (
    PROFILE_CUSTODY_KDF_WORKER_CPU_SECONDS,
    PROFILE_CUSTODY_KDF_WORKER_MAX_PROCESSES,
    PROFILE_CUSTODY_KDF_WORKER_MEMORY_BYTES,
)

_WIN32_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION: Final = 9
_WIN32_JOB_OBJECT_BASIC_PROCESS_ID_LIST: Final = 3
_WIN32_JOB_OBJECT_LIMIT_PROCESS_TIME: Final = 0x00000002
_WIN32_JOB_OBJECT_LIMIT_ACTIVE_PROCESS: Final = 0x00000008
_WIN32_JOB_OBJECT_LIMIT_PROCESS_MEMORY: Final = 0x00000100
_WIN32_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE: Final = 0x00002000


if sys.platform == "win32":
    from ctypes import wintypes

    class _BasicLimitInformation(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _IoCounters(ctypes.Structure):
        _fields_ = [
            (name, ctypes.c_uint64)
            for name in (
                "ReadOperationCount",
                "WriteOperationCount",
                "OtherOperationCount",
                "ReadTransferCount",
                "WriteTransferCount",
                "OtherTransferCount",
            )
        ]

    class _ExtendedLimitInformation(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _BasicLimitInformation),
            ("IoInfo", _IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    class _WindowsJob:
        """A required kill-on-close Windows process-tree and resource boundary."""

        def __init__(self, handle: int, kernel32: ctypes.CDLL) -> None:
            self._handle = handle
            self._kernel32 = kernel32

        @classmethod
        def create(cls) -> _WindowsJob:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.CreateJobObjectW.restype = wintypes.HANDLE
            handle = kernel32.CreateJobObjectW(None, None)
            if not handle:
                raise _supervision_refusal()
            information = _ExtendedLimitInformation()
            information.BasicLimitInformation.PerProcessUserTimeLimit = (
                PROFILE_CUSTODY_KDF_WORKER_CPU_SECONDS * 10_000_000
            )
            information.BasicLimitInformation.ActiveProcessLimit = PROFILE_CUSTODY_KDF_WORKER_MAX_PROCESSES
            information.BasicLimitInformation.LimitFlags = (
                _WIN32_JOB_OBJECT_LIMIT_PROCESS_TIME
                | _WIN32_JOB_OBJECT_LIMIT_ACTIVE_PROCESS
                | _WIN32_JOB_OBJECT_LIMIT_PROCESS_MEMORY
                | _WIN32_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            )
            information.ProcessMemoryLimit = PROFILE_CUSTODY_KDF_WORKER_MEMORY_BYTES
            if not kernel32.SetInformationJobObject(
                wintypes.HANDLE(handle),
                _WIN32_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
                ctypes.byref(information),
                ctypes.sizeof(information),
            ):
                kernel32.CloseHandle(wintypes.HANDLE(handle))
                raise _supervision_refusal()
            return cls(int(handle), kernel32)

        def assign(self, process: subprocess.Popen[bytes]) -> None:
            process_handle = int(cast(Any, process)._handle)
            if not self._kernel32.AssignProcessToJobObject(
                wintypes.HANDLE(self._handle),
                wintypes.HANDLE(process_handle),
            ):
                raise _supervision_refusal()

        def contains(self, process: subprocess.Popen[bytes]) -> bool:
            """Prove the launched worker PID is present in this exact job object."""

            class _BasicProcessIdList(ctypes.Structure):
                _fields_ = [
                    ("NumberOfAssignedProcesses", wintypes.DWORD),
                    ("NumberOfProcessIdsInList", wintypes.DWORD),
                    ("ProcessIdList", ctypes.c_size_t * PROFILE_CUSTODY_KDF_WORKER_MAX_PROCESSES),
                ]

            if not self._handle:
                return False
            members = _BasicProcessIdList()
            if not self._kernel32.QueryInformationJobObject(
                wintypes.HANDLE(self._handle),
                _WIN32_JOB_OBJECT_BASIC_PROCESS_ID_LIST,
                ctypes.byref(members),
                ctypes.sizeof(members),
                None,
            ):
                return False
            process_ids = members.ProcessIdList[: int(members.NumberOfProcessIdsInList)]
            return process.pid in process_ids

        def limits(self) -> dict[str, int]:
            """Read back the required Job Object limits before releasing a secret."""
            if not self._handle:
                raise _supervision_refusal()
            information = _ExtendedLimitInformation()
            if not self._kernel32.QueryInformationJobObject(
                wintypes.HANDLE(self._handle),
                _WIN32_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
                ctypes.byref(information),
                ctypes.sizeof(information),
                None,
            ):
                raise _supervision_refusal()
            expected_flags = (
                _WIN32_JOB_OBJECT_LIMIT_PROCESS_TIME
                | _WIN32_JOB_OBJECT_LIMIT_ACTIVE_PROCESS
                | _WIN32_JOB_OBJECT_LIMIT_PROCESS_MEMORY
                | _WIN32_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            )
            if information.BasicLimitInformation.LimitFlags & expected_flags != expected_flags:
                raise _supervision_refusal()
            return {
                "cpu_seconds": int(information.BasicLimitInformation.PerProcessUserTimeLimit // 10_000_000),
                "memory_bytes": int(information.ProcessMemoryLimit),
                "max_processes": int(information.BasicLimitInformation.ActiveProcessLimit),
            }

        def close(self) -> None:
            if self._handle:
                self._kernel32.CloseHandle(wintypes.HANDLE(self._handle))
                self._handle = 0

else:

    class _WindowsJob:
        """The same boundary on a platform with no Job Object: it refuses.

        Reached only if a caller skips its own platform guard. Every method raises
        the supervision refusal rather than silently degrading the process-tree and
        resource boundary the supervisor requires before releasing a secret.
        """

        def __init__(self, handle: int, kernel32: ctypes.CDLL) -> None:
            raise _supervision_refusal()

        @classmethod
        def create(cls) -> _WindowsJob:
            raise _supervision_refusal()

        def assign(self, process: subprocess.Popen[bytes]) -> None:
            raise _supervision_refusal()

        def contains(self, process: subprocess.Popen[bytes]) -> bool:
            raise _supervision_refusal()

        def limits(self) -> dict[str, int]:
            raise _supervision_refusal()

        def close(self) -> None:
            raise _supervision_refusal()


__all__ = ["_WindowsJob"]
