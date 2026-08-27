"""Windows Job Object boundary for the supervised profile KDF worker."""

from __future__ import annotations

import ctypes
import subprocess
from ctypes import wintypes
from typing import Any, Final, cast

from ._kdf_codec import supervision_refusal as _supervision_refusal

PROFILE_CUSTODY_KDF_WORKER_MEMORY_BYTES: Final = 1024 * 1024 * 1024
PROFILE_CUSTODY_KDF_WORKER_CPU_SECONDS: Final = 15
PROFILE_CUSTODY_KDF_WORKER_MAX_PROCESSES: Final = 2
_WIN32_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION: Final = 9
_WIN32_JOB_OBJECT_BASIC_PROCESS_ID_LIST: Final = 3
_WIN32_JOB_OBJECT_LIMIT_PROCESS_TIME: Final = 0x00000002
_WIN32_JOB_OBJECT_LIMIT_ACTIVE_PROCESS: Final = 0x00000008
_WIN32_JOB_OBJECT_LIMIT_PROCESS_MEMORY: Final = 0x00000100
_WIN32_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE: Final = 0x00002000


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

    def __init__(self, handle: int, kernel32: ctypes.WinDLL) -> None:
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
        information.BasicLimitInformation.PerProcessUserTimeLimit = PROFILE_CUSTODY_KDF_WORKER_CPU_SECONDS * 10_000_000
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
        from ctypes import wintypes

        process_handle = int(cast(Any, process)._handle)
        if not self._kernel32.AssignProcessToJobObject(
            wintypes.HANDLE(self._handle),
            wintypes.HANDLE(process_handle),
        ):
            raise _supervision_refusal()

    def contains(self, process: subprocess.Popen[bytes]) -> bool:
        """Prove the launched worker PID is present in this exact job object."""
        from ctypes import wintypes

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
        from ctypes import wintypes

        if self._handle:
            self._kernel32.CloseHandle(wintypes.HANDLE(self._handle))
            self._handle = 0


__all__ = [
    "PROFILE_CUSTODY_KDF_WORKER_CPU_SECONDS",
    "PROFILE_CUSTODY_KDF_WORKER_MAX_PROCESSES",
    "PROFILE_CUSTODY_KDF_WORKER_MEMORY_BYTES",
    "_WindowsJob",
]
