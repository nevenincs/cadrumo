"""Read actual Windows Installer action sequencing without executing a package."""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path


def action_sequence(artifact: Path) -> dict[str, int]:
    """Query the MSI database in read-only mode, closing every native handle."""
    if sys.platform != "win32":
        raise ValueError("MSI database verification requires a native Windows host")
    msi = ctypes.WinDLL("msi.dll", winmode=0x00000800)  # LOAD_LIBRARY_SEARCH_SYSTEM32
    handle = ctypes.c_uint32
    definitions = {
        "MsiOpenDatabaseW": ([ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.POINTER(handle)], handle),
        "MsiDatabaseOpenViewW": ([handle, ctypes.c_wchar_p, ctypes.POINTER(handle)], handle),
        "MsiViewExecute": ([handle, handle], handle),
        "MsiViewFetch": ([handle, ctypes.POINTER(handle)], handle),
        "MsiRecordGetStringW": ([handle, handle, ctypes.c_wchar_p, ctypes.POINTER(handle)], handle),
        "MsiRecordGetInteger": ([handle, handle], ctypes.c_int32),
        "MsiCloseHandle": ([handle], handle),
    }
    for name, (arguments, result) in definitions.items():
        function = getattr(msi, name)
        function.argtypes = arguments
        function.restype = result

    def check(status: int) -> None:
        if status:
            raise ValueError(f"Windows Installer read-only database query failed: {status}")

    database = handle()
    # MSIDBOPEN_READONLY is the null pointer; no install session is created.
    check(msi.MsiOpenDatabaseW(str(artifact.resolve(strict=True)), None, ctypes.byref(database)))
    try:
        view = handle()
        check(
            msi.MsiDatabaseOpenViewW(
                database, "SELECT `Action`, `Sequence` FROM `InstallExecuteSequence`", ctypes.byref(view)
            )
        )
        try:
            check(msi.MsiViewExecute(view, 0))
            actions: dict[str, int] = {}
            while True:
                record = handle()
                status = msi.MsiViewFetch(view, ctypes.byref(record))
                if status == 259:  # ERROR_NO_MORE_ITEMS
                    return actions
                check(status)
                try:
                    size = handle(256)
                    action = ctypes.create_unicode_buffer(size.value)
                    check(msi.MsiRecordGetStringW(record, 1, action, ctypes.byref(size)))
                    actions[action.value] = int(msi.MsiRecordGetInteger(record, 2))
                finally:
                    msi.MsiCloseHandle(record)
        finally:
            msi.MsiCloseHandle(view)
    finally:
        msi.MsiCloseHandle(database)


def verify_upgrade_order(artifact: Path, *, version_product: bool) -> None:
    """Require immutable versions and transactional registration upgrade ordering."""
    sequence = action_sequence(artifact)
    if version_product:
        if "RemoveExistingProducts" in sequence:
            raise ValueError("Version MSI schedules removal of another product")
    elif not (
        0
        < sequence.get("InstallExecute", 0)
        < sequence.get("RemoveExistingProducts", 0)
        < sequence.get("InstallFinalize", 0)
    ):
        raise ValueError(f"Registration MSI lost its transactional upgrade order: {sequence}")
