"""Open a Linux process descriptor even where the interpreter does not expose ``os.pidfd_open``."""

from __future__ import annotations

import ctypes
import errno
import os
import sys

_PIDFD_OPEN_SYSCALL = 434
"""``pidfd_open``'s number in the kernel's unified syscall table (Linux 5.3 and later).

Syscalls added since the table was unified share one number on every architecture Cadrumo runs on.
"""


def open_process_pidfd(pid: int) -> int:
    """Return a close-on-exec descriptor that becomes readable when process ``pid`` ends.

    ``os.pidfd_open`` is used where the interpreter has it. Some CPython builds omit it, and then the kernel is
    asked directly. A process that does not exist raises ``ProcessLookupError``; a kernel or platform without
    process descriptors raises ``OSError``.
    """
    native = getattr(os, "pidfd_open", None)
    if native is not None:
        return int(native(pid))
    if sys.platform != "linux":
        raise OSError(errno.ENOSYS, os.strerror(errno.ENOSYS))
    syscall = ctypes.CDLL(None, use_errno=True).syscall
    syscall.argtypes = (ctypes.c_long, ctypes.c_int, ctypes.c_uint)
    syscall.restype = ctypes.c_long
    ctypes.set_errno(0)
    descriptor = int(syscall(_PIDFD_OPEN_SYSCALL, pid, 0))
    if descriptor >= 0:
        return descriptor
    code = ctypes.get_errno()
    if code == errno.ESRCH:
        raise ProcessLookupError(code, os.strerror(code))
    raise OSError(code, os.strerror(code))


__all__ = ["open_process_pidfd"]
