"""Time a worker control dispatch spends waiting outside its own work.

A control handler can wait on its peer (a proof transfer, a secret frame or
the parent's final read) or, for ``stop``, on the drain of in-flight
operations. Those waits are attributed to the dispatch that is active in the
current context, so the slow-dispatch budget measures only the handler's own
work. Threads started with :func:`asyncio.to_thread` copy the context and so
add to the same accumulator.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Generator
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from typing import Literal

from cadrumo_client.contracts.contracts import ByteChannel
from cadrumo_client.transport.frame_io import read_secret

type ControlDispatchWaitKind = Literal["peer", "drain"]


class ControlDispatchWaits:
    """Accumulate one dispatch's peer and drain waits on the dispatch's own clock."""

    __slots__ = ("_clock", "_lock", "_seconds")

    def __init__(self, clock: Callable[[], float]) -> None:
        """Measure every wait with ``clock``, the dispatch's own monotonic clock."""
        self._clock = clock
        self._lock = threading.Lock()
        self._seconds: dict[ControlDispatchWaitKind, float] = {"peer": 0.0, "drain": 0.0}

    def seconds(self, kind: ControlDispatchWaitKind) -> float:
        """Return the waits of one kind measured so far."""
        with self._lock:
            return self._seconds[kind]

    def total(self) -> float:
        """Return every wait measured so far."""
        with self._lock:
            return sum(self._seconds.values())

    @contextmanager
    def measure(self, kind: ControlDispatchWaitKind) -> Generator[None]:
        """Add the enclosed block's elapsed time to ``kind``, also when it raises."""
        started = self._clock()
        try:
            yield
        finally:
            elapsed = max(0.0, self._clock() - started)
            with self._lock:
                self._seconds[kind] += elapsed


_ACTIVE: ContextVar[ControlDispatchWaits | None] = ContextVar("control_dispatch_waits", default=None)


@contextmanager
def control_dispatch_waits(clock: Callable[[], float]) -> Generator[ControlDispatchWaits]:
    """Scope a fresh accumulator to one dispatch in the current context."""
    waits = ControlDispatchWaits(clock)
    token = _ACTIVE.set(waits)
    try:
        yield waits
    finally:
        _ACTIVE.reset(token)


@contextmanager
def awaiting(kind: ControlDispatchWaitKind) -> Generator[None]:
    """Attribute the enclosed wait to the active dispatch; outside a dispatch it only runs the block."""
    waits = _ACTIVE.get()
    if waits is None:
        yield
        return
    with waits.measure(kind):
        yield


@contextmanager
def read_peer_secret(channel: ByteChannel, *, deadline: float) -> Generator[bytearray]:
    """Lend one secret frame like ``read_secret``, counting only its read as a peer wait."""
    with ExitStack() as lent:
        with awaiting("peer"):
            secret = lent.enter_context(read_secret(channel, deadline=deadline))
        yield secret
