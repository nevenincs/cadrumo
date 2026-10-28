"""An in-memory byte channel pair for tests whose document and secret framing stay real.

Shared test support: the runtime's and the MCP harness's tests both drive real
framing over it, so it lives with the client transport they both depend on.
"""

from __future__ import annotations

import time
from threading import Condition

from ...contracts.contracts import ChannelWake, Peer, RefusalCode, RefusalError


class MemoryChannel:
    """Explicit bounded byte-channel port; document and secret framing stay real."""

    def __init__(self) -> None:
        self._condition = Condition()
        self._data = bytearray()
        self._closed = False
        self._other: MemoryChannel | None = None
        self.writes: list[bytes] = []
        self.peer = Peer(os_owner_id="synthetic-owner", process_id=1)

    def pair(self, other: MemoryChannel) -> None:
        self._other = other
        other._other = self

    def read_exact(self, count: int, *, deadline: float) -> bytes:
        with self._condition:
            while len(self._data) < count:
                if self._closed or (self._other is not None and self._other._closed):
                    raise RefusalError(RefusalCode.CONNECTION_CLOSED)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RefusalError(RefusalCode.TIMEOUT)
                self._condition.wait(remaining)
            result = bytes(self._data[:count])
            del self._data[:count]
            return result

    def read_ready(self) -> bool:
        with self._condition:
            return bool(self._data) or self._closed or (self._other is not None and self._other._closed)

    def wait_readable(self, *wakes: ChannelWake) -> bool:
        while not self.read_ready():
            if any(wake.is_set() for wake in wakes):
                return False
            time.sleep(0.01)
        return True

    def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
        other = self._other
        if other is None or time.monotonic() >= deadline:
            raise RefusalError(RefusalCode.TIMEOUT)
        with other._condition:
            if self._closed or other._closed:
                raise RefusalError(RefusalCode.CONNECTION_CLOSED)
            self.writes.append(bytes(payload))
            other._data.extend(payload)
            other._condition.notify_all()

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._condition.notify_all()
        if self._other is not None:
            with self._other._condition:
                self._other._condition.notify_all()
