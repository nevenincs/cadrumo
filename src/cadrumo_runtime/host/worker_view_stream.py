"""The profile worker's side of the view stream: its view channel endpoint and the executor's sink.

The worker listens on its view endpoint, beside the control and operation
channels, only while a ``live.sede.view`` operation it owns runs. The runtime
host connects when a window first attaches; the worker admits only its own
native parent, completes the runtime handshake as the server, and opens with
its identity and ``view.bind``. Nothing else may connect: the listener closes
once the host is admitted.

Toward the host the worker writes ``view.*`` documents and announced images
under the host's credit; from the host it reads credit and person input. The
host closing the channel ends the view. Images, documents and input stay in
memory and are never logged.
"""

from __future__ import annotations

import time
from collections import deque
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Condition, Event, Lock, Thread
from uuid import UUID

from cadrumo.application.operations.models import OperationId
from cadrumo.core.diagnostic_log import diagnostic_event
from cadrumo.core.logging import get_logger
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError, ServerHello
from cadrumo_client.contracts.view_stream import (
    ViewClosed,
    ViewClosedReason,
    ViewCredit,
    ViewImage,
    ViewNotice,
    ViewPersonInput,
    ViewState,
    ViewWorkerBind,
)
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity
from cadrumo_client.transport.frame_io import write_document
from cadrumo_client.transport.native_wake import NativeWake
from cadrumo_client.transport.posix_channel import PosixChannel
from cadrumo_client.transport.view_stream import (
    ViewImageOutbox,
    read_view_upstream,
    write_view_document,
    write_view_image,
)

from ..adapters.connection_handshake import accept_connection_handshake
from ..adapters.native_peer import require_live_native_peer
from ..adapters.worker_native_identity import worker_view_namespace
from ..adapters.worker_transport import WorkerChannel, WorkerEndpoint, worker_endpoint

_LOGGER = get_logger(__name__)

_FRAME_SECONDS = 5.0
"""Each frame, and the host's acknowledgement of ``view.closed``, completes within this bound."""

_DOCUMENT_QUEUE = 32
_INPUT_QUEUE = 64
"""Page documents and person input waiting for their reader; excess is dropped, never queued."""


def require_native_parent(channel: WorkerChannel, parent_pid: int) -> None:
    """Check the socket's live kernel peer is the worker's own runtime parent."""
    if channel.peer.process_id != parent_pid:
        raise RefusalError(RefusalCode.PEER_UNTRUSTED)
    if isinstance(channel, PosixChannel):
        require_live_native_peer(channel)


def _close_quietly(channel: WorkerChannel) -> None:
    try:
        channel.close()
    except Exception as error:
        diagnostic_event(_LOGGER, "view_channel_close_failed", fields={"error_type": type(error).__name__}, level=30)


class WorkerViewStream:
    """One view's stream from the worker to the runtime host; the ``ViewStreamSink`` the executor holds."""

    def __init__(
        self,
        *,
        endpoint: WorkerEndpoint,
        identity: ProfileWorkerIdentity,
        parent_pid: int,
        product_version: str,
        bind: ViewWorkerBind,
    ) -> None:
        """Listen for the host's view channel; the caller has not yet granted any credit."""
        self._endpoint = endpoint
        self._identity = identity
        self._parent_pid = parent_pid
        self._product_version = product_version
        self._bind = bind
        self._signal = Condition(Lock())
        self._outbox = ViewImageOutbox()
        self._documents: deque[ViewState | ViewNotice] = deque()
        self._input: Queue[ViewPersonInput] = Queue(maxsize=_INPUT_QUEUE)
        self._channel: WorkerChannel | None = None
        self._closing: ViewClosedReason | None = None
        self._stopping = NativeWake()
        self._ended = Event()
        self._threads: list[Thread] = []
        endpoint.listen()
        accept = Thread(target=self._accept, name="worker-view-accept", daemon=True)
        self._threads.append(accept)
        accept.start()

    @property
    def connected(self) -> bool:
        """Whether the runtime host holds the view channel."""
        return self._channel is not None and not self._ended.is_set()

    @property
    def ended(self) -> bool:
        """Whether the view channel ended; the view must then end."""
        return self._ended.is_set()

    def offer_image(self, announcement: ViewImage, image: bytes) -> None:
        """Make this the newest pending image, replacing any older one not yet sent."""
        if self._ended.is_set():
            return
        self._outbox.offer(announcement, image)
        with self._signal:
            self._signal.notify_all()

    def send(self, document: ViewState | ViewNotice) -> None:
        """Queue one page document for the window, dropping it when the queue is full."""
        with self._signal:
            if self._ended.is_set() or self._closing is not None or len(self._documents) >= _DOCUMENT_QUEUE:
                return
            self._documents.append(document)
            self._signal.notify_all()

    def receive(self, *, timeout: float) -> ViewPersonInput | None:
        """Return the next person input, or ``None`` after ``timeout`` seconds or once ended."""
        deadline = time.monotonic() + max(0.0, timeout)
        while True:
            try:
                return self._input.get(timeout=min(0.25, max(0.0, deadline - time.monotonic())))
            except Empty:
                if self._ended.is_set() or time.monotonic() >= deadline:
                    return None

    def close(self, reason: ViewClosedReason) -> None:
        """Send ``view.closed`` and wait until the host closes the channel, which is its unbinding."""
        with self._signal:
            if self._closing is None:
                self._closing = reason
            self._documents.clear()
            self._outbox.clear()
            self._signal.notify_all()
            unconnected = self._channel is None
        if unconnected:
            self._stop()
        # The host's close is the acknowledgement; a host that never answers is bounded.
        self._ended.wait(timeout=2 * _FRAME_SECONDS)
        self._stop()
        # The accept thread serves the reader and starts the writer, so it is joined first.
        self._threads[0].join(timeout=_FRAME_SECONDS)
        for thread in tuple(self._threads[1:]):
            thread.join(timeout=_FRAME_SECONDS)

    def _stop(self) -> None:
        self._ended.set()
        self._stopping.set()
        with self._signal:
            self._signal.notify_all()
        channel = self._channel
        if channel is not None:
            _close_quietly(channel)

    def _accept(self) -> None:
        """Admit the runtime parent alone, then serve its channel; foreign peers are refused and dropped."""
        try:
            self._accept_host()
        finally:
            # Only this thread waits on the listener, so only it releases it.
            self._endpoint.close()

    def _accept_host(self) -> None:
        while not self._stopping.is_set():
            try:
                channel = self._endpoint.accept(timeout=None, wakes=(self._stopping,))
            except RefusalError as error:
                if error.reason in {RefusalCode.CONNECTION_CLOSED, RefusalCode.DEADLINE_EXCEEDED}:
                    continue
                self._stop()
                return
            try:
                self._admit(channel)
            except RefusalError as error:
                diagnostic_event(_LOGGER, "view_channel_refused", fields={"reason": error.reason.value}, level=30)
                _close_quietly(channel)
                continue
            # One host leg per view: nothing else may connect afterward.
            self._endpoint.close()
            with self._signal:
                if self._stopping.is_set():
                    _close_quietly(channel)
                    return
                self._channel = channel
            writer = Thread(target=self._write, args=(channel,), name="worker-view-writer", daemon=True)
            self._threads.append(writer)
            writer.start()
            self._read(channel)
            return

    def _admit(self, channel: WorkerChannel) -> None:
        require_native_parent(channel, self._parent_pid)
        deadline = time.monotonic() + _FRAME_SECONDS
        accept_connection_handshake(
            channel,
            identity=ServerHello(
                product_version=self._product_version,
                storage_identity=self._endpoint.storage_identity,
                boot_id=self._identity.runtime_boot_id,
            ),
            deadline=deadline,
        )
        write_document(channel, self._identity, deadline=deadline)
        write_document(channel, self._bind, deadline=deadline)

    def _read(self, channel: WorkerChannel) -> None:
        """Take credit and person input until the host closes the channel."""
        try:
            while not self._stopping.is_set():
                if not channel.wait_readable(self._stopping):
                    return
                document = read_view_upstream(channel, deadline=time.monotonic() + _FRAME_SECONDS)
                if isinstance(document, ViewCredit):
                    self._outbox.grant(document.images)
                    with self._signal:
                        self._signal.notify_all()
                    continue
                if self._closing is None:
                    try:
                        self._input.put_nowait(document)
                    except Full:
                        continue
        except RefusalError:
            return
        finally:
            self._ended.set()
            with self._signal:
                self._signal.notify_all()

    def _write(self, channel: WorkerChannel) -> None:
        """Send queued documents and credited images; ``view.closed`` is always the last frame."""
        try:
            while True:
                closing, document, pending = self._next_write()
                if self._ended.is_set():
                    return
                if closing is not None:
                    write_view_document(channel, ViewClosed(reason=closing), deadline=time.monotonic() + _FRAME_SECONDS)
                    return
                if document is not None:
                    write_view_document(channel, document, deadline=time.monotonic() + _FRAME_SECONDS)
                elif pending is not None:
                    write_view_image(channel, pending[0], pending[1], deadline=time.monotonic() + _FRAME_SECONDS)
        except RefusalError:
            self._ended.set()

    def _next_write(
        self,
    ) -> tuple[ViewClosedReason | None, ViewState | ViewNotice | None, tuple[ViewImage, bytes] | None]:
        """Wait for the next frame to send: the closing reason, a document, or a credited image."""
        with self._signal:
            while not self._ended.is_set():
                if self._closing is not None:
                    return self._closing, None, None
                if self._documents:
                    return None, self._documents.popleft(), None
                pending = self._outbox.take()
                if pending is not None:
                    return None, None, pending
                self._signal.wait()
            return None, None, None


class WorkerViewStreams:
    """Open a profile worker's one view stream at a time; the ``ViewStreamSinks`` its operation host composes."""

    def __init__(
        self, *, storage_root: Path, identity: ProfileWorkerIdentity, parent_pid: int, product_version: str
    ) -> None:
        """Bind the worker's identity, its runtime parent and its storage root."""
        self._storage_root = storage_root
        self._identity = identity
        self._parent_pid = parent_pid
        self._product_version = product_version

    def open_view(self, *, operation_id: OperationId, session_id: UUID) -> WorkerViewStream:
        """Listen for the host's view channel; a second view while one listens is refused as busy."""
        endpoint = worker_endpoint(
            storage_root=self._storage_root, worker_namespace=worker_view_namespace(self._identity.worker_id)
        )
        return WorkerViewStream(
            endpoint=endpoint,
            identity=self._identity,
            parent_pid=self._parent_pid,
            product_version=self._product_version,
            bind=ViewWorkerBind(operation_id=operation_id, session_id=session_id),
        )
