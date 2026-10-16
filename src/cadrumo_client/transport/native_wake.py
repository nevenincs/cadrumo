"""A flag a thread waits on together with channel input, so an idle wait never polls."""

from __future__ import annotations

import os
import sys
import weakref
from threading import Lock


class NativeWake:
    """A settable flag the kernel waits on alongside a channel.

    Setting it ends a channel's readiness wait at once. It stays set until the
    waiter clears it, so a set that races the start of a wait is never lost.
    """

    def __init__(self) -> None:
        """Create the flag cleared, with its native signal."""
        self._guard = Lock()
        self._set = False
        self._signal = _EventSignal() if sys.platform == "win32" else _PipeSignal()

    @property
    def waitable(self) -> int:
        """Return the native object a wait includes: an event handle or a readable descriptor."""
        return self._signal.waitable

    def is_set(self) -> bool:
        """Return whether the flag is set."""
        return self._set

    def set(self) -> None:
        """Set the flag and wake any wait that includes it."""
        with self._guard:
            if not self._set:
                self._set = True
                self._signal.raise_signal()

    def clear(self) -> None:
        """Clear the flag before the next wait."""
        with self._guard:
            if self._set:
                self._set = False
                self._signal.lower_signal()


class _EventSignal:
    """A manual-reset Windows event; its handle closes with the object."""

    def __init__(self) -> None:
        import win32event

        self._event = win32event.CreateEvent(None, True, False, None)

    @property
    def waitable(self) -> int:
        return int(self._event)

    def raise_signal(self) -> None:
        import win32event

        win32event.SetEvent(self._event)

    def lower_signal(self) -> None:
        import win32event

        win32event.ResetEvent(self._event)


class _PipeSignal:
    """A pipe holding one byte while set; its read end is what a wait selects."""

    def __init__(self) -> None:
        self._read, self._write = os.pipe()
        os.set_blocking(self._read, False)
        os.set_blocking(self._write, False)
        weakref.finalize(self, _close_pipe, self._read, self._write)

    @property
    def waitable(self) -> int:
        return self._read

    def raise_signal(self) -> None:
        os.write(self._write, b"\0")

    def lower_signal(self) -> None:
        os.read(self._read, 1)


def _close_pipe(read: int, write: int) -> None:
    os.close(read)
    os.close(write)
