"""Open an exact Linux process handle through the native libc capability."""

from __future__ import annotations

import ctypes
import os
import sys

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError


def open_linux_pidfd(pid: int) -> int:
    """Return a noninherited PIDFD or refuse when native custody is unavailable."""
    if sys.platform != "linux" or type(pid) is not int or not 0 < pid <= 2_147_483_647:
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    try:
        library = ctypes.CDLL(None, use_errno=True)
        native_open = library.pidfd_open
        native_open.argtypes = (ctypes.c_int, ctypes.c_uint)
        native_open.restype = ctypes.c_int
        descriptor = int(native_open(pid, 0))
    except (OSError, AttributeError):
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE) from None
    if descriptor < 0:
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    try:
        if os.get_inheritable(descriptor):
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        return descriptor
    except (OSError, RuntimeRefusalError):
        os.close(descriptor)
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE) from None
