"""Create Windows processes inside their owning Job at launch time."""

from __future__ import annotations

import ctypes
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from ..contracts.contracts import RefusalCode, RefusalError

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


def _win32_check(step: str) -> str:
    # The Win32 error number is the only cause a failed containment call reports; it names no payload.
    if sys.platform == "win32":
        return f"{step}_winerror_{ctypes.get_last_error()}"
    return step


def _attribute_list_count(standard_handles: tuple[int, int, int] | None) -> int:
    # Job membership always needs one attribute; explicit inherited handles add another.
    return 1 if standard_handles is None else 2


def launch_in_windows_job(
    job: int,
    *,
    executable: Path,
    arguments: Sequence[str],
    directory: Path,
    environment: Mapping[str, str],
    standard_handles: tuple[int, int, int] | None = None,
) -> tuple[int, int, int]:
    """Create a process already assigned to its owning Windows Job."""
    if sys.platform != "win32":
        raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
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
    get_error_mode = kernel.GetThreadErrorMode
    get_error_mode.argtypes = ()
    get_error_mode.restype = wintypes.DWORD
    set_error_mode = kernel.SetThreadErrorMode
    set_error_mode.argtypes = (wintypes.DWORD, ctypes.POINTER(wintypes.DWORD))
    set_error_mode.restype = wintypes.BOOL
    count = _attribute_list_count(standard_handles)
    size = ctypes.c_size_t()
    initialize(None, count, 0, ctypes.byref(size))
    if size.value == 0:
        raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE, check=_win32_check("attribute_list_size"))
    attributes = ctypes.create_string_buffer(size.value)
    if not initialize(attributes, count, 0, ctypes.byref(size)):
        raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE, check=_win32_check("attribute_list_initialize"))
    try:
        jobs = (wintypes.HANDLE * 1)(job)
        # PROC_THREAD_ATTRIBUTE_JOB_LIST: the kernel assigns before any child
        # code runs. No create-then-assign or suspended unowned orphan window.
        if not update(attributes, 0, 0x0002000D, jobs, ctypes.sizeof(jobs), None, None):
            raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE, check=_win32_check("job_list_attribute"))
        startup = _StartupInfoEx()
        startup.startup.cb = ctypes.sizeof(startup)
        startup.attributes = ctypes.addressof(attributes)
        inherited = None
        if standard_handles is not None:
            # PROC_THREAD_ATTRIBUTE_HANDLE_LIST: exactly these three pipe ends
            # are inherited, so no other inheritable handle of this process leaks.
            inherited = (wintypes.HANDLE * 3)(*standard_handles)
            if not update(attributes, 0, 0x00020002, inherited, ctypes.sizeof(inherited), None, None):
                raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE, check=_win32_check("handle_list_attribute"))
            startup.startup.dwFlags = 0x00000100  # STARTF_USESTDHANDLES
            startup.startup.hStdInput, startup.startup.hStdOutput, startup.startup.hStdError = standard_handles
        information = _ProcessInformation()
        command = ctypes.create_unicode_buffer(subprocess.list2cmdline((str(executable), *arguments)))
        block = ctypes.create_unicode_buffer(
            "\0".join(f"{key}={value}" for key, value in sorted(environment.items(), key=lambda item: item[0].upper()))
            + "\0\0"
        )
        # EXTENDED_STARTUPINFO_PRESENT | CREATE_UNICODE_ENVIRONMENT |
        # CREATE_NO_WINDOW. Inherit no handles, including this job handle,
        # beyond the standard handles the handle list names.
        # CREATE_NO_WINDOW does not suppress the loader's invalid-image dialog.
        # SEM_FAILCRITICALERRORS returns that error to this launching thread;
        # preserve every other thread's policy and restore ours after the call.
        previous_error_mode = get_error_mode()
        if not set_error_mode(previous_error_mode | 0x0001, None):
            raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE, check=_win32_check("launch_error_mode"))
        try:
            if not create(
                str(executable),
                command,
                None,
                None,
                inherited is not None,
                0x08080400,
                block,
                str(directory),
                ctypes.byref(startup),
                ctypes.byref(information),
            ):
                raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE, check=_win32_check("create_process"))
        finally:
            set_error_mode(previous_error_mode, None)
        return int(information.process), int(information.thread), int(information.pid)
    finally:
        destroy(attributes)
