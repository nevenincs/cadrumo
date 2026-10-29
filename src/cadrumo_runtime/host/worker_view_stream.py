"""The profile worker's side of the view stream: its view channel endpoint and the executor's sink.

The worker listens on its view endpoint, beside the control and operation
channels, only while a ``live.sede.view`` operation it owns runs. The runtime
host connects when a window first attaches; the worker admits only its own
native parent, completes the runtime handshake as the server, and opens with
its identity and ``view.bind``. Nothing else may connect: the listener closes
once the host is admitted.

Toward the host the worker writes ``view.*`` documents and announced images
under the host's credit; from the host it reads credit and person input. The
host closing the channel ends the view without publishing; ``view.close``,
which the host also sends when the window's connection drops, ends it with a
publication. Downloads stream under the window's transfer credit, one at a
time; uploads are received whole in memory, checked against their completion
and handed to the executor. Images, documents, input and file bytes stay in
memory and are never logged.
"""

from __future__ import annotations

import time
from collections import deque
from pathlib import Path
from threading import Condition, Event, Lock, Thread
from uuid import UUID

from cadrumo.application.operations.models import OperationId
from cadrumo.core.diagnostic_log import diagnostic_event
from cadrumo.core.logging import get_logger
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError, ServerHello
from cadrumo_client.contracts.view_stream import (
    ViewClose,
    ViewClosed,
    ViewClosedReason,
    ViewCredit,
    ViewDialog,
    ViewImage,
    ViewInput,
    ViewNavigate,
    ViewNotice,
    ViewResize,
    ViewSinkInput,
    ViewState,
    ViewWorkerBind,
)
from cadrumo_client.contracts.view_transfer import (
    VIEW_TRANSFER_CREDIT_MAX_CHUNKS,
    ViewConnectionUpstreamDocument,
    ViewDownload,
    ViewDownloadAnswer,
    ViewFileChooser,
    ViewFileChooserAnswer,
    ViewTransferByteSource,
    ViewTransferCancel,
    ViewTransferComplete,
    ViewTransferCredit,
    ViewTransferDirection,
    ViewTransferDownstreamDocument,
    ViewUpload,
    ViewUploadCancelled,
    ViewUploadedFile,
)
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity
from cadrumo_client.transport.frame_io import write_document
from cadrumo_client.transport.native_wake import NativeWake
from cadrumo_client.transport.posix_channel import PosixChannel
from cadrumo_client.transport.view_stream import (
    ViewTransferChunk,
    ViewTransferReceiver,
    ViewTransferSender,
    write_view_document,
    write_view_image,
    write_view_transfer_chunk,
    write_view_transfer_document,
)
from cadrumo_client.transport.view_stream_readers import ViewImageOutbox, ViewUpstreamReader

from ..adapters.connection_handshake import accept_connection_handshake
from ..adapters.native_peer import require_live_native_peer
from ..adapters.worker_native_identity import worker_view_namespace
from ..adapters.worker_transport import WorkerChannel, WorkerEndpoint, worker_endpoint

_LOGGER = get_logger(__name__)

_FRAME_SECONDS = 5.0
"""Each frame, and the host's acknowledgement of ``view.closed``, completes within this bound."""

_DOCUMENT_QUEUE = 32
"""Page documents waiting for the writer; excess is dropped, never queued.

Transfer requests are never dropped: each answers something the window waits on.
"""

_INPUT_QUEUE = 1024
"""Person input waiting for the executor before the reader stops reading the view channel.

No person input is dropped: a dropped key or button release would leave it
held down in the page. Once this many wait, the reader holds the next one and
reads nothing more until the executor takes one, so the host's writes wait in
turn. That paces the window; it does not limit what the person may do.
"""

_UPLOAD_REGRANT = VIEW_TRANSFER_CREDIT_MAX_CHUNKS // 2
"""Top an upload's credit back up once the window has spent this much of it."""

type _Write = (
    tuple[ViewClosedReason, None, None, None]
    | tuple[None, ViewState | ViewNotice | ViewTransferDownstreamDocument, None, None]
    | tuple[None, None, tuple[ViewImage, bytes], None]
    | tuple[None, None, None, ViewTransferSender]
    | tuple[None, None, None, None]
)


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


def _is_person_input(item: ViewSinkInput) -> bool:
    """Whether an inbox item is person input, which the reader paces, rather than something the view waits on."""
    return isinstance(item, ViewInput | ViewNavigate | ViewResize | ViewDialog)


class _Upload:
    """One file the window is sending, held in memory until its completion checks it."""

    __slots__ = ("credit", "data", "upload")

    def __init__(self, upload: ViewUpload) -> None:
        self.upload = upload
        self.data = bytearray()
        self.credit = 0

    def wipe(self) -> None:
        self.data[:] = bytes(len(self.data))
        self.data = bytearray()


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
        self._transfer_documents: deque[ViewTransferDownstreamDocument] = deque()
        self._inbox: deque[ViewSinkInput] = deque()
        self._person_inputs = 0
        self._close_requested = False
        self._uploads = ViewTransferReceiver(ViewTransferDirection.UPLOAD)
        self._receiving: dict[int, _Upload] = {}
        self._sender: ViewTransferSender | None = None
        self._sender_result: bool | None = None
        self._early_credit: dict[int, int] = {}
        self._cancelled_downloads: set[int] = set()
        self._download_turn = Lock()
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

    def send(self, document: ViewState | ViewNotice | ViewDownload | ViewFileChooser | ViewTransferCancel) -> None:
        """Queue one page document, dropped when the queue is full, or one transfer request, never dropped."""
        with self._signal:
            if self._ended.is_set() or self._closing is not None:
                return
            if isinstance(document, ViewDownload | ViewFileChooser | ViewTransferCancel):
                self._transfer_documents.append(document)
            elif len(self._documents) < _DOCUMENT_QUEUE:
                self._documents.append(document)
            else:
                return
            self._signal.notify_all()

    def receive(self, *, timeout: float) -> ViewSinkInput | None:
        """Return the next person input or transfer event, or ``None`` after ``timeout`` seconds or once ended."""
        deadline = time.monotonic() + max(0.0, timeout)
        with self._signal:
            while not self._inbox:
                remaining = deadline - time.monotonic()
                if self._ended.is_set() or remaining <= 0:
                    return None
                self._signal.wait(remaining)
            item = self._inbox.popleft()
            if _is_person_input(item):
                self._person_inputs -= 1
                # A reader holding input back waits for this room.
                self._signal.notify_all()
            return item

    def send_download(self, transfer_id: int, source: ViewTransferByteSource) -> bool:
        """Stream an accepted download under the window's credit; ``False`` when cancelled or ended first."""
        with self._download_turn, self._signal:
            if transfer_id in self._cancelled_downloads:
                self._cancelled_downloads.discard(transfer_id)
                return False
            if self._ended.is_set() or self._closing is not None:
                return False
            sender = ViewTransferSender(transfer_id, source)
            # The window may grant credit as soon as it accepts, before the bytes are ready.
            early = self._early_credit.pop(transfer_id, 0)
            if early:
                sender.grant(early)
            self._sender = sender
            self._sender_result = None
            self._signal.notify_all()
            while not self._signal.wait_for(self._download_settled, timeout=_FRAME_SECONDS):
                pass
            delivered = self._sender_result is True
            self._sender = None
            self._sender_result = None
            return delivered

    def cancel_download(self, transfer_id: int) -> None:
        """Stop the download ``transfer_id`` from the worker side and tell the window."""
        with self._signal:
            self._early_credit.pop(transfer_id, None)
            sender = self._sender
            if sender is not None and sender.transfer_id == transfer_id:
                self._cancel_download(transfer_id)
            else:
                # Not streaming yet: its call returns at once, and the window stops waiting for its bytes.
                self._cancelled_downloads.add(transfer_id)
                if not self._ended.is_set() and self._closing is None:
                    self._transfer_documents.append(
                        ViewTransferCancel(direction=ViewTransferDirection.DOWNLOAD, transfer_id=transfer_id)
                    )
            self._signal.notify_all()

    def _download_settled(self) -> bool:
        """Whether the streaming download finished or was cancelled, or the view ended; hold ``_signal``."""
        return self._sender_result is not None or self._ended.is_set()

    def close(self, reason: ViewClosedReason) -> None:
        """Send ``view.closed`` and wait until the host closes the channel, which is its unbinding."""
        with self._signal:
            if self._closing is None:
                self._closing = reason
            self._documents.clear()
            self._transfer_documents.clear()
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
            for upload in self._receiving.values():
                upload.wipe()
            self._receiving.clear()
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
                if error.reason in {RefusalCode.CONNECTION_CLOSED, RefusalCode.TIMEOUT}:
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
        """Take credit, person input and transfers until the host closes the channel."""
        reader = ViewUpstreamReader(channel, self._uploads)
        try:
            while not self._stopping.is_set():
                if not channel.wait_readable(self._stopping):
                    return
                item = reader.read(deadline=time.monotonic() + _FRAME_SECONDS)
                with self._signal:
                    self._take(item)
                    self._signal.notify_all()
        except RefusalError:
            return
        finally:
            self._ended.set()
            with self._signal:
                self._signal.notify_all()

    def _take(self, item: ViewConnectionUpstreamDocument | ViewTransferChunk) -> None:
        """Apply one upstream document or upload chunk; the caller holds the signal."""
        if isinstance(item, ViewCredit):
            self._outbox.grant(item.images)
        elif isinstance(item, ViewTransferCredit):
            self._take_transfer_credit(item)
        elif isinstance(item, ViewTransferCancel):
            self._take_transfer_cancel(item)
        elif isinstance(item, ViewUpload):
            self._uploads.expect(item.transfer_id, size=item.size)
            upload = _Upload(item)
            self._receiving[item.transfer_id] = upload
            self._grant_upload(upload, VIEW_TRANSFER_CREDIT_MAX_CHUNKS)
        elif isinstance(item, ViewTransferChunk):
            self._receive_chunk(item)
        elif isinstance(item, ViewTransferComplete):
            self._complete_upload(item.transfer_id)
        elif isinstance(item, ViewDownloadAnswer | ViewFileChooserAnswer):
            self._inbox.append(item)
        elif isinstance(item, ViewClose):
            self._take_close(item)
        elif self._wait_for_input_room():
            self._person_inputs += 1
            self._inbox.append(item)

    def _take_close(self, item: ViewClose) -> None:
        if not self._close_requested:
            self._close_requested = True
            self._inbox.append(item)

    def _take_transfer_credit(self, item: ViewTransferCredit) -> None:
        sender = self._sender
        if sender is not None and sender.transfer_id == item.transfer_id and self._sender_result is None:
            sender.grant(item.chunks)
        elif sender is None or sender.transfer_id != item.transfer_id:
            credit = self._early_credit.get(item.transfer_id, 0) + item.chunks
            if credit > VIEW_TRANSFER_CREDIT_MAX_CHUNKS:
                raise RefusalError(RefusalCode.INVALID_FRAME, check="view_transfer_credit")
            self._early_credit[item.transfer_id] = credit

    def _take_transfer_cancel(self, item: ViewTransferCancel) -> None:
        if item.direction is ViewTransferDirection.DOWNLOAD:
            self._early_credit.pop(item.transfer_id, None)
            self._cancel_download(item.transfer_id)
            self._inbox.append(item)
        else:
            upload = self._receiving.pop(item.transfer_id, None)
            if upload is not None:
                upload.wipe()
                # Only this file's chooser loses its files; other choosers keep waiting.
                self._inbox.append(ViewUploadCancelled(chooser_id=upload.upload.chooser_id))

    def _wait_for_input_room(self) -> bool:
        """Hold the reader until the executor has room for one more person input; hold ``_signal``.

        Returns ``False`` once the view is closing or ended, when input no
        longer reaches the page.
        """
        while self._person_inputs >= _INPUT_QUEUE and self._accepts_input():
            self._signal.wait()
        return self._accepts_input()

    def _accepts_input(self) -> bool:
        return (
            self._closing is None
            and not self._close_requested
            and not self._ended.is_set()
            and not self._stopping.is_set()
        )

    def _cancel_download(self, transfer_id: int) -> None:
        """Stop the streaming download the window cancelled, answering with this end's cancel unless complete."""
        sender = self._sender
        if sender is None or sender.transfer_id != transfer_id or self._sender_result is not None:
            return
        finished = sender.done
        sender.cancel()
        if not finished:
            self._transfer_documents.append(
                ViewTransferCancel(direction=ViewTransferDirection.DOWNLOAD, transfer_id=transfer_id)
            )
        self._sender_result = False

    def _grant_upload(self, upload: _Upload, chunks: int) -> None:
        self._transfer_documents.append(self._uploads.grant(upload.upload.transfer_id, chunks))
        upload.credit += chunks

    def _receive_chunk(self, chunk: ViewTransferChunk) -> None:
        upload = self._receiving.get(chunk.transfer_id)
        if upload is None:
            return
        upload.data.extend(chunk.data)
        upload.credit -= 1
        if not chunk.last and upload.credit <= _UPLOAD_REGRANT:
            self._grant_upload(upload, VIEW_TRANSFER_CREDIT_MAX_CHUNKS - upload.credit)

    def _complete_upload(self, transfer_id: int) -> None:
        """Hand over a file whose completion the receiver has already checked in size and digest."""
        upload = self._receiving.pop(transfer_id, None)
        if upload is None:
            return
        self._inbox.append(
            ViewUploadedFile(
                chooser_id=upload.upload.chooser_id,
                name=upload.upload.name,
                mime=upload.upload.mime,
                data=bytes(upload.data),
            )
        )
        upload.wipe()

    def _write(self, channel: WorkerChannel) -> None:
        """Send documents, credited images and download chunks; ``view.closed`` is always the last frame."""
        try:
            while True:
                closing, document, pending, sender = self._next_write()
                if self._ended.is_set():
                    return
                deadline = time.monotonic() + _FRAME_SECONDS
                if closing is not None:
                    write_view_document(channel, ViewClosed(reason=closing), deadline=deadline)
                    return
                if isinstance(document, ViewState | ViewNotice):
                    write_view_document(channel, document, deadline=deadline)
                elif document is not None:
                    write_view_transfer_document(channel, document, deadline=deadline)
                elif pending is not None:
                    write_view_image(channel, pending[0], pending[1], deadline=deadline)
                elif sender is not None:
                    self._write_download_chunk(channel, sender, deadline=deadline)
        except RefusalError:
            self._ended.set()
            with self._signal:
                self._signal.notify_all()

    def _write_download_chunk(self, channel: WorkerChannel, sender: ViewTransferSender, *, deadline: float) -> None:
        """Send one credited chunk and, after the last, the completion that settles the waiting download."""
        payload = sender.next_payload()
        if payload is None:
            return
        write_view_transfer_chunk(channel, payload, deadline=deadline)
        if not sender.done:
            return
        write_view_transfer_document(channel, sender.completion(), deadline=deadline)
        with self._signal:
            if self._sender is sender and self._sender_result is None:
                self._sender_result = True
            self._signal.notify_all()

    def _next_write(self) -> _Write:
        """Wait for the next frame: the closing reason, a document, a credited image or a credited chunk."""
        with self._signal:
            while not self._ended.is_set():
                if self._closing is not None:
                    return self._closing, None, None, None
                if self._documents:
                    return None, self._documents.popleft(), None, None
                if self._transfer_documents:
                    return None, self._transfer_documents.popleft(), None, None
                pending = self._outbox.take()
                if pending is not None:
                    return None, None, pending, None
                sender = self._sender
                if sender is not None and self._sender_result is None and sender.credit > 0 and not sender.done:
                    return None, None, None, sender
                self._signal.wait()
            return None, None, None, None


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
