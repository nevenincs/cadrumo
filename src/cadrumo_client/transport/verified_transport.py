"""Correlated runtime exchanges and success-only native channel cleanup."""

from __future__ import annotations

import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from threading import Event, RLock, Thread
from uuid import UUID

from pydantic import BaseModel

from ..contracts.access_management import SessionInventoryTransfer
from ..contracts.contracts import ByteChannel, RefusalCode, RefusalError, ServerHello
from ..contracts.deadline_budget import remaining_budget
from ..contracts.profile_access import AccessRefusal, ProfileStatusTransfer, Reply, SecretReady
from ..contracts.session_events import ConnectionEvent, LifecycleNotice, SessionEvent
from .frame_io import (
    SecretBearingRequest,
    read_profile_status,
    read_reply_or_event,
    read_session_inventory,
    write_document,
    write_secret,
)
from .transport_cleanup import TransportCleanup, close_transport_after_failure


class VerifiedTransport:
    """Correlated runtime exchanges and success-only native channel cleanup."""

    _channel: ByteChannel
    _exchange_lock: RLock
    _closed: bool
    _channel_closed: bool
    _connection_id: UUID | None
    _lifecycle_notices: bool
    hello: ServerHello

    def subscribe_session_events(
        self, receive: Callable[[ConnectionEvent], None], *, disconnected: Callable[[], None] | None = None
    ) -> Callable[[], None]:
        """Observe this connection without giving a second thread concurrent read authority."""
        with self._exchange_lock:
            if self._closed:
                raise RefusalError(RefusalCode.CONNECTION_CLOSED)
            self._event_receivers.append(receive)
            if self._retained_notice is not None:
                receive(self._retained_notice)
            if disconnected is not None:
                self._disconnect_receivers.append(disconnected)
            if self._event_reader is None:
                self._event_reader = Thread(target=self._read_idle_events, name="runtime-session-events", daemon=True)
                self._event_reader.start()

        def unsubscribe() -> None:
            with self._exchange_lock:
                if receive in self._event_receivers:
                    self._event_receivers.remove(receive)
                if disconnected is not None and disconnected in self._disconnect_receivers:
                    self._disconnect_receivers.remove(disconnected)

        return unsubscribe

    def _initialize_session_events(self) -> None:
        self._event_receivers: list[Callable[[ConnectionEvent], None]] = []
        self._disconnect_receivers: list[Callable[[], None]] = []
        self._event_reader: Thread | None = None
        self._event_stop = Event()
        self._retained_notice: LifecycleNotice | None = None

    def _receive_event(self, event: ConnectionEvent) -> None:
        if isinstance(event, LifecycleNotice) and not self._lifecycle_notices:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        if event.runtime_boot_id != self.hello.boot_id or (
            self._connection_id is not None and event.connection_id != self._connection_id
        ):
            raise RefusalError(RefusalCode.INVALID_FRAME)
        self._connection_id = event.connection_id
        if isinstance(event, LifecycleNotice):
            self._retained_notice = event
        for receive in tuple(self._event_receivers):
            receive(event)

    def _read_idle_events(self) -> None:
        while not self._event_stop.wait(0.05):
            if not self._exchange_lock.acquire(blocking=False):
                continue
            try:
                if self._closed:
                    return
                if not self._channel.read_ready():
                    continue
                received = read_reply_or_event(self._channel, Reply, deadline=time.monotonic() + 5)
                if not isinstance(received, (SessionEvent, LifecycleNotice)):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                self._receive_event(received)
            except BaseException as error:
                try:
                    self._close_after_failure(error)
                finally:
                    for disconnected in tuple(self._disconnect_receivers):
                        disconnected()
                return
            finally:
                self._exchange_lock.release()

    def _close_after_failure(self, error: BaseException) -> None:
        retained = error.__dict__.get("_transport_cleanup")
        if isinstance(retained, TransportCleanup) and retained.resource is self._channel:
            # An inner frame failure already attempted this native release.
            # Fence exchanges now, and let its retained owner retry through
            # the connection's success-only channel-close bookkeeping.
            self._closed = True
            self._channel_closed = retained.released
            retained.resource = self
            return
        close_transport_after_failure(self, error)

    @contextmanager
    def _exchange(self, *, deadline: float, secret: bytearray | None = None) -> Generator[None]:
        """Include queueing in the total budget without closing another caller's exchange."""
        try:
            remaining = remaining_budget(deadline)
            if not self._exchange_lock.acquire(timeout=remaining):
                raise RefusalError(RefusalCode.DEADLINE_EXCEEDED)
            try:
                yield
            finally:
                self._exchange_lock.release()
        finally:
            if secret is not None:
                secret[:] = bytes(len(secret))

    @contextmanager
    def held_exchange(
        self, request: BaseModel, request_id: UUID, *, deadline: float, secret: bytearray | None = None
    ) -> Generator[HeldExchange]:
        """Send ``request`` and hold its exchange until every frame that answers it is read.

        A request answered in steps, with a secret frame or a transfer between
        them, runs here: no other request interleaves, a failed frame closes
        the connection as it does for any exchange, and ``secret`` is wiped on
        every path.

        Args:
            request: The credential-free document that opens the exchange.
            request_id: The identity every reply to it must carry.
            deadline: The bound on the whole exchange, queueing included.
            secret: A secret buffer the exchange will consume, wiped when it ends.
        """
        with self._exchange(deadline=deadline, secret=secret):
            try:
                if self._closed:
                    raise RefusalError(RefusalCode.CONNECTION_CLOSED)
                write_document(self._channel, request, deadline=deadline)
                yield HeldExchange(self, request_id, deadline=deadline)
            except BaseException as error:
                self._close_after_failure(error)
                raise

    @property
    def connection_id(self) -> UUID | None:
        """Return the last verified non-bearer connection identity, if any."""
        with self._exchange_lock:
            return self._connection_id

    def send_secret(self, secret: bytearray, *, deadline: float) -> None:
        """Consume a one-shot secret buffer after peer and cohort verification."""
        with self._exchange(deadline=deadline, secret=secret):
            try:
                if self._closed:
                    raise RefusalError(RefusalCode.CONNECTION_CLOSED)
                write_secret(self._channel, secret, deadline=deadline)
            except BaseException as error:
                self._close_after_failure(error)
                raise
            finally:
                secret[:] = bytes(len(secret))

    def _reply(self, request_id: UUID, *, deadline: float) -> Reply:
        if self._closed:
            raise RefusalError(RefusalCode.CONNECTION_CLOSED)
        while True:
            result = read_reply_or_event(self._channel, Reply, deadline=deadline)
            if not isinstance(result, (SessionEvent, LifecycleNotice)):
                break
            self._receive_event(result)
        self._verify_reply(request_id, result.root.request_id, result.root.runtime_boot_id, result.root.connection_id)
        if isinstance(result.root, ProfileStatusTransfer):
            result = Reply(read_profile_status(self._channel, result.root, deadline=deadline))
        elif isinstance(result.root, SessionInventoryTransfer):
            result = Reply(read_session_inventory(self._channel, result.root, deadline=deadline))
        return result

    def _verify_reply(self, expected: UUID, received: UUID, boot: UUID, connection: UUID) -> None:
        if (
            expected != received
            or boot != self.hello.boot_id
            or (self._connection_id is not None and self._connection_id != connection)
        ):
            raise RefusalError(RefusalCode.INVALID_FRAME)
        self._connection_id = connection

    def _deliver_secret(
        self, request: SecretBearingRequest, secret: bytearray, *, deadline: float
    ) -> tuple[SecretReady, Reply] | AccessRefusal:
        """Send one request, then its secret only after the peer's correlated readiness.

        A refusal before readiness is returned without consuming the secret.
        Otherwise the readiness document and the peer's final reply come back.
        """
        write_document(self._channel, request, deadline=deadline)
        ready = self._reply(request.request_id, deadline=deadline).root
        if isinstance(ready, AccessRefusal):
            return ready
        if not isinstance(ready, SecretReady):
            raise RefusalError(RefusalCode.INVALID_FRAME)
        self.send_secret(secret, deadline=deadline)
        return ready, self._reply(request.request_id, deadline=deadline)

    def close(self) -> None:
        """Stop exchanges immediately and retry failed owned channel cleanup."""
        with self._exchange_lock:
            self._closed = True
            self._event_stop.set()
            if not self._channel_closed:
                self._channel.close()
                self._channel_closed = True


class HeldExchange:
    """The frames of one request, for as long as its connection's exchange is held for it."""

    def __init__(self, transport: VerifiedTransport, request_id: UUID, *, deadline: float) -> None:
        """Bind the held exchange to the request it answers and to its bound."""
        self._transport = transport
        self._request_id = request_id
        self._deadline = deadline

    @property
    def channel(self) -> ByteChannel:
        """Return the held channel, for the frames a reply announces."""
        return self._transport._channel

    def reply(self) -> Reply:
        """Read the next reply to this exchange's request, verified against its coordinates."""
        return self._transport._reply(self._request_id, deadline=self._deadline)

    def send_secret(self, secret: bytearray) -> None:
        """Send one secret frame the peer is ready for; the buffer is consumed and wiped."""
        self._transport.send_secret(secret, deadline=self._deadline)
