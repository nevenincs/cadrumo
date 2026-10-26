"""Complete a byte write to an open file descriptor.

:func:`os.write` may accept only a prefix of the buffer, and a descriptor that
can no longer make progress reports zero accepted bytes rather than an error.
Looping on that result spins forever, so a non-positive count is refused as an
:class:`OSError` and the caller decides how to translate it.
"""

from __future__ import annotations

import os


def write_all(fd: int, data: bytes | bytearray | memoryview) -> None:
    """Write ``data`` completely to an already-opened descriptor.

    Args:
        fd: Writable operating-system file descriptor.
        data: Byte payload to write in full.

    Raises:
        OSError: If the descriptor reports no forward progress or another
            operating-system write error occurs.
    """
    view = memoryview(data)
    offset = 0
    while offset < len(view):
        written = os.write(fd, view[offset:])
        if written <= 0:
            raise OSError("descriptor write made no progress")
        offset += written
