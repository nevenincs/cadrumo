"""A runtime host serving one running view, for the native lane's tests.

The desktop's Rust lane runs as the window. This process is the runtime and
the view's worker: it serves the storage root's runtime pipe with the real
handshake, answers ``view_attach`` and ``view_connect`` through the real
:class:`ViewStreamRelay`, and holds the view's worker leg through the real
:class:`WorkerViewStream`, bound as the runtime binds it. The page is a
synthetic image source, so no browser is needed; the browser's end of the
stream is covered by the Python integration test of the view.

Run as ``python -B -m cadrumo_runtime.host.tests.view_stream_native_peer ROOT VERSION``.
It prints one JSON line per event and reads one command per line:
``download`` offers a download, ``choose`` opens a file chooser, and
``sign_out`` retires the view's session. End of input ends the process.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import secrets
import sys
import time
from pathlib import Path
from threading import Event, Lock, Thread, Timer
from typing import Annotated
from uuid import uuid4

from pydantic import Field, RootModel

from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo_client.contracts.contracts import ByteChannel, RefusalCode, RefusalError, ServerHello
from cadrumo_client.contracts.profile_access import AccessRefusal
from cadrumo_client.contracts.transport import ConnectionContext
from cadrumo_client.contracts.view_stream import (
    TextInput,
    ViewAttachGranted,
    ViewAttachRequest,
    ViewClose,
    ViewClosedReason,
    ViewConnect,
    ViewImage,
    ViewInput,
    ViewNavigate,
)
from cadrumo_client.contracts.view_transfer import (
    ViewDownload,
    ViewDownloadAnswer,
    ViewDownloadOutcome,
    ViewFileChooser,
    ViewUploadCancelled,
    ViewUploadedFile,
)
from cadrumo_client.transport.frame_io import read_document, write_document
from cadrumo_client.transport.windows import WindowsEndpoint

from ...adapters.connection_handshake import accept_connection_handshake
from ..view_stream_relay import ViewAttachGrant, ViewStreamRelay
from ..worker_view_stream import WorkerViewStream, WorkerViewStreams
from .view_stream_host_support import bind_worker_leg, synthetic_worker_identity

_LIFETIME_SECONDS = 120
_FRAME_SECONDS = 0.02
_DOWNLOAD_TRANSFER_ID = 1
_CHOOSER_ID = 1

#: The bytes of each image are a pure function of its sequence, so the window can check every one.
_IMAGE_REPEATS = 6400


def image_bytes(sequence: int) -> bytes:
    """The synthetic page's image for ``sequence``: 200 KiB, spanning several chunks."""
    return hashlib.sha256(b"view-frame" + sequence.to_bytes(8, "big")).digest() * _IMAGE_REPEATS


_DOWNLOAD = hashlib.sha256(b"view-download").digest() * 12000


class _FirstRequest(RootModel[Annotated[ViewAttachRequest | ViewConnect, Field(discriminator="action")]]):
    """A view connection's first request, or the person connection's attach request."""


class _Peer:
    def __init__(self, root: Path, version: str) -> None:
        self.identity = synthetic_worker_identity()
        self.boot = self.identity.runtime_boot_id
        self.operation_id = secrets.token_hex(32)
        self.session_id = uuid4()
        self.person_id = uuid4()
        self._held = {(self.person_id, self.session_id)}
        self._output = Lock()
        self._stopping = Event()
        self.relay = ViewStreamRelay(
            runtime_boot_id=self.boot, holds_session=lambda connection, session: (connection, session) in self._held
        )
        self.sink: WorkerViewStream = WorkerViewStreams(
            storage_root=root, identity=self.identity, parent_pid=os.getpid(), product_version=version
        ).open_view(operation_id=self.operation_id, session_id=self.session_id)
        bind_worker_leg(self.relay, storage_root=root, identity=self.identity, product_version=version)
        self.endpoint = WindowsEndpoint(storage_root=root)
        self.hello = ServerHello(
            product_version=version, storage_identity=self.endpoint.storage_identity, boot_id=self.boot
        )

    def emit(self, event: str, **members: object) -> None:
        with self._output:
            sys.stdout.write(json.dumps({"event": event, **members}) + "\n")
            sys.stdout.flush()

    def start(self) -> None:
        self.endpoint.listen()
        for target in (self._accept, self._frames, self._worker):
            Thread(target=target, daemon=True).start()
        self.emit(
            "ready",
            profile_id=str(self.identity.binding.profile_id),
            session_id=str(self.session_id),
            connection_id=str(self.person_id),
            runtime_boot_id=str(self.boot),
            operation_id=self.operation_id,
            download_sha256=hashlib.sha256(_DOWNLOAD).hexdigest(),
            download_size=len(_DOWNLOAD),
        )

    def command(self, line: str) -> None:
        if line == "download":
            self.sink.send(
                ViewDownload(
                    transfer_id=_DOWNLOAD_TRANSFER_ID, filename="justificante.pdf", size=len(_DOWNLOAD), mime=None
                )
            )
        elif line == "choose":
            self.sink.send(ViewFileChooser(chooser_id=_CHOOSER_ID, accept=(), multiple=False))
        elif line == "sign_out":
            self._held.clear()
            self.relay.unbind_sessions((self.session_id,))
            self.emit("signed_out", worker_bound=self.relay.worker_bind(self.operation_id) is not None)
        else:
            self.emit("unknown")

    def stop(self) -> None:
        self._stopping.set()
        self.relay.close()
        self.sink.close(ViewClosedReason.CANCELLED)
        self.endpoint.close()

    def _accept(self) -> None:
        while not self._stopping.is_set():
            try:
                channel = self.endpoint.accept(timeout=1)
            except RefusalError as error:
                if error.reason is RefusalCode.DEADLINE_EXCEEDED:
                    continue
                return
            Thread(target=self._serve, args=(channel,), daemon=True).start()

    def _serve(self, channel: ByteChannel) -> None:
        try:
            accept_connection_handshake(channel, identity=self.hello, deadline=time.monotonic() + 5)
            first = read_document(channel, _FirstRequest, deadline=time.monotonic() + 5).root
            if isinstance(first, ViewConnect):
                self._view_connection(channel, first)
                return
            context = ConnectionContext(self.person_id, self.boot, channel.peer)
            request: ViewAttachRequest | ViewConnect = first
            while isinstance(request, ViewAttachRequest):
                self._attach(channel, context, request)
                channel.wait_readable()
                request = read_document(channel, _FirstRequest, deadline=time.monotonic() + 5).root
        except RefusalError:
            pass
        finally:
            channel.close()

    def _attach(self, channel: ByteChannel, context: ConnectionContext, request: ViewAttachRequest) -> None:
        reply: ViewAttachGranted | AccessRefusal
        try:
            token = self.relay.issue(
                ViewAttachGrant(
                    operation_id=request.operation_id,
                    profile_id=request.profile_id,
                    session_id=request.session_id,
                    person_connection_id=context.connection_id,
                    peer=context.peer,
                    runtime_boot_id=self.boot,
                )
            )
            reply = ViewAttachGranted(
                request_id=request.request_id,
                runtime_boot_id=self.boot,
                connection_id=context.connection_id,
                operation_id=request.operation_id,
                attach_token=token,
            )
        except (RefusalError, ProfileAccessRefusedError) as error:
            reply = AccessRefusal(
                request_id=request.request_id,
                runtime_boot_id=self.boot,
                connection_id=context.connection_id,
                code=error.reason,
            )
            self.emit("attach_refused", code=str(error.reason))
        write_document(channel, reply, deadline=time.monotonic() + 5)

    def _view_connection(self, channel: ByteChannel, request: ViewConnect) -> None:
        context = ConnectionContext(uuid4(), self.boot, channel.peer)
        try:
            leg = self.relay.admit(
                attach_token=request.attach_token, operation_id=request.operation_id, context=context, channel=channel
            )
        except (RefusalError, ProfileAccessRefusedError) as error:
            refusal = AccessRefusal(
                request_id=request.request_id,
                runtime_boot_id=self.boot,
                connection_id=context.connection_id,
                code=error.reason,
            )
            write_document(channel, refusal, deadline=time.monotonic() + 5)
            return
        self.relay.serve_window(leg, request.request_id)

    def _frames(self) -> None:
        """Offer a new image every few milliseconds, whether or not the window has credit."""
        sequence = 0
        while not self.sink.ended and not self._stopping.is_set():
            image = image_bytes(sequence)
            self.sink.offer_image(
                ViewImage(
                    sequence=sequence,
                    byte_length=len(image),
                    pixel_width=64,
                    pixel_height=48,
                    css_width=64,
                    css_height=48,
                    scale=1.0,
                ),
                image,
            )
            sequence += 1
            time.sleep(_FRAME_SECONDS)

    def _worker(self) -> None:
        """Act on what the window sends, as the view's executor would, and report it."""
        while not self._stopping.is_set():
            item = self.sink.receive(timeout=0.2)
            if item is None:
                if self.sink.ended:
                    self.emit("ended")
                    return
                continue
            if isinstance(item, ViewInput):
                event = item.event
                self.emit("input", type=event.type, text=event.text if isinstance(event, TextInput) else None)
            elif isinstance(item, ViewNavigate):
                self.emit("navigate", verb=item.verb.value)
            elif isinstance(item, ViewClose):
                self.emit("close")
                self.sink.close(ViewClosedReason.OPERATION_ENDED)
            elif isinstance(item, ViewDownloadAnswer):
                if item.outcome is ViewDownloadOutcome.ACCEPTED:
                    Thread(target=self._send_download, args=(item.transfer_id,), daemon=True).start()
                else:
                    self.emit("download_answered", outcome=item.outcome.value)
            elif isinstance(item, ViewUploadedFile):
                self.emit(
                    "uploaded",
                    chooser_id=item.chooser_id,
                    name=item.name,
                    size=len(item.data),
                    sha256=hashlib.sha256(item.data).hexdigest(),
                )
            elif isinstance(item, ViewUploadCancelled):
                self.emit("upload_cancelled", chooser_id=item.chooser_id)
            else:
                self.emit("transfer", kind=item.kind)

    def _send_download(self, transfer_id: int) -> None:
        delivered = self.sink.send_download(transfer_id, io.BytesIO(_DOWNLOAD))
        self.emit("downloaded", delivered=delivered)


def main() -> None:
    """Serve one view until input ends, under a hard lifetime bound."""
    lifetime = Timer(_LIFETIME_SECONDS, os._exit, args=(124,))
    lifetime.daemon = True
    lifetime.start()
    peer = _Peer(Path(sys.argv[1]), sys.argv[2])
    peer.start()
    try:
        for line in sys.stdin:
            peer.command(line.strip())
    finally:
        peer.stop()
        lifetime.cancel()


if __name__ == "__main__":
    main()


__all__ = ["image_bytes", "main"]
