"""Bounded per-connection retirement queues; publication performs no transport I/O."""

from queue import Empty, Full, Queue
from threading import Event, Lock
from uuid import UUID

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.session_events import RuntimeSessionEvent
from ...application.runtime.transport import RuntimeConnectionContext

SESSION_EVENT_QUEUE_LIMIT = 64


class RuntimeSessionEvents:
    """Retain only verified connections, closing an overflowing stream at its next turn."""

    def __init__(self) -> None:
        """Create empty queues without granting a session or opening custody."""
        self._guard = Lock()
        self._queues: dict[UUID, tuple[Queue[RuntimeSessionEvent], Event]] = {}

    def connect(self, context: RuntimeConnectionContext) -> None:
        """Register one completed native handshake."""
        with self._guard:
            self._queues[context.connection_id] = Queue(maxsize=SESSION_EVENT_QUEUE_LIMIT), Event()

    def disconnect(self, context: RuntimeConnectionContext) -> None:
        """Discard pending notices for a stream whose authority is retired."""
        with self._guard:
            self._queues.pop(context.connection_id, None)

    def publish(self, event: RuntimeSessionEvent) -> None:
        """Enqueue after authority removal without waiting for a client to read."""
        with self._guard:
            target = self._queues.get(event.connection_id)
            if target is None or target[1].is_set():
                return
            try:
                target[0].put_nowait(event)
            except Full:
                target[1].set()

    def take(self, context: RuntimeConnectionContext) -> tuple[RuntimeSessionEvent, ...]:
        """Transfer a bounded batch to the connection's sole frame writer."""
        with self._guard:
            target = self._queues.get(context.connection_id)
            if target is None or target[1].is_set():
                raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
            result: list[RuntimeSessionEvent] = []
            while True:
                try:
                    result.append(target[0].get_nowait())
                except Empty:
                    return tuple(result)
