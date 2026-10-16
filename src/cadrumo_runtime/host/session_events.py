"""Bounded per-connection retirement queues; publication performs no transport I/O."""

from queue import Empty, Full, Queue
from threading import Event, Lock
from uuid import UUID, uuid4

from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.session_events import (
    AttendanceChanged,
    ConnectionEvent,
    LifecycleNotice,
    ServiceLeaseChanged,
    SignInChanged,
)
from cadrumo_client.contracts.transport import ConnectionContext

SESSION_EVENT_QUEUE_LIMIT = 64

type InvalidationCue = SignInChanged | ServiceLeaseChanged | AttendanceChanged


class RuntimeSessionEvents:
    """Retain only verified connections, closing an overflowing stream at its next turn."""

    def __init__(self) -> None:
        """Create empty queues without granting a session or opening custody."""
        self._guard = Lock()
        self._queues: dict[UUID, tuple[Queue[ConnectionEvent], Event]] = {}
        self._notices: dict[UUID, tuple[LifecycleNotice, Event]] = {}
        self._pending_cues: dict[UUID, set[str]] = {}

    def connect(self, context: ConnectionContext) -> None:
        """Register one completed native handshake."""
        with self._guard:
            self._queues[context.connection_id] = Queue(maxsize=SESSION_EVENT_QUEUE_LIMIT), Event()

    def disconnect(self, context: ConnectionContext) -> None:
        """Discard pending notices for a stream whose authority is retired."""
        with self._guard:
            self._queues.pop(context.connection_id, None)
            self._notices.pop(context.connection_id, None)
            self._pending_cues.pop(context.connection_id, None)

    def publish_cue(self, cue: InvalidationCue) -> None:
        """Queue a cue unless the same one still waits for the connection's writer.

        A cue only asks its receiver to read again, so one waiting cue answers any
        number of changes and a burst cannot overflow the queue and close it.
        """
        with self._guard:
            target = self._queues.get(cue.connection_id)
            if target is None or target[1].is_set():
                return
            pending = self._pending_cues.setdefault(cue.connection_id, set())
            if cue.kind in pending:
                return
            try:
                target[0].put_nowait(cue)
            except Full:
                target[1].set()
                return
            pending.add(cue.kind)

    def publish(self, event: ConnectionEvent) -> None:
        """Enqueue after authority removal without waiting for a client to read."""
        with self._guard:
            target = self._queues.get(event.connection_id)
            if target is None or target[1].is_set():
                return
            try:
                target[0].put_nowait(event)
            except Full:
                target[1].set()

    def upgrade_pending(self, context: ConnectionContext) -> Event | None:
        """Coalesce idle retries; the returned witness means written, never merely queued."""
        if not context.lifecycle_notices:
            return None
        with self._guard:
            target = self._queues.get(context.connection_id)
            if target is None or target[1].is_set():
                return None
            previous = self._notices.get(context.connection_id)
            if previous is not None:
                return previous[1]
            notice = LifecycleNotice(
                runtime_boot_id=context.runtime_boot_id, connection_id=context.connection_id, notice_id=uuid4()
            )
            flushed = Event()
            self._notices[context.connection_id] = notice, flushed
            try:
                target[0].put_nowait(notice)
            except Full:
                target[1].set()
            return flushed

    def flushed(self, context: ConnectionContext, event: ConnectionEvent) -> None:
        """Acknowledge exactly the queued notice after its complete native frame write."""
        if not isinstance(event, LifecycleNotice):
            return
        with self._guard:
            notice = self._notices.get(context.connection_id)
            if notice is not None and notice[0] == event and event.runtime_boot_id == context.runtime_boot_id:
                notice[1].set()

    def take(self, context: ConnectionContext) -> tuple[ConnectionEvent, ...]:
        """Transfer a bounded batch to the connection's sole frame writer."""
        with self._guard:
            target = self._queues.get(context.connection_id)
            if target is None or target[1].is_set():
                raise RefusalError(RefusalCode.CONNECTION_CLOSED)
            result: list[ConnectionEvent] = []
            while True:
                try:
                    result.append(target[0].get_nowait())
                except Empty:
                    # Every taken cue is now the writer's; a later change queues a fresh one.
                    self._pending_cues.pop(context.connection_id, None)
                    return tuple(result)
