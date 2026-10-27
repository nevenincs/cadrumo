"""The view stream relay binds both legs exactly, passes credit through and unbinds at once.

Every leg here is a real native endpoint and channel: the worker's view
endpoint served by the worker's own sink, the runtime host's connection to it,
and a window connection accepted on a runtime endpoint. A view connection from
another native peer comes from a child process.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from threading import Thread
from uuid import UUID, uuid4

import pytest

from cadrumo.application.user_profile.access_contracts import ProfileAccessBinding
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.hashing import content_hash_hex
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.contracts import ByteChannel, Peer, RefusalCode, RefusalError, ServerHello
from cadrumo_client.contracts.profile_access import Request
from cadrumo_client.contracts.transport import ConnectionContext
from cadrumo_client.contracts.view_stream import (
    ViewAttachGranted,
    ViewAttachRequest,
    ViewClose,
    ViewClosed,
    ViewClosedReason,
    ViewConnect,
    ViewConnected,
    ViewCredit,
    ViewImage,
    ViewNavigate,
    ViewNavigateVerb,
    ViewStreamSink,
    ViewStreamSinks,
    ViewWorkerBind,
)
from cadrumo_client.contracts.view_transfer import (
    ViewDownload,
    ViewDownloadAnswer,
    ViewDownloadOutcome,
    ViewFileChooser,
    ViewFileChooserAnswer,
    ViewFileChooserOutcome,
    ViewTransferComplete,
    ViewTransferCredit,
    ViewTransferDirection,
    ViewTransferUpstreamDocument,
    ViewUpload,
    ViewUploadedFile,
)
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity
from cadrumo_client.transport.frame_io import read_document, write_document
from cadrumo_client.transport.view_stream import (
    AssembledViewImage,
    ViewDownstreamReader,
    ViewTransferChunk,
    ViewTransferReceiver,
    ViewTransferSender,
    view_image_frames,
    write_view_document,
    write_view_transfer_chunk,
    write_view_transfer_document,
)

from ...adapters.connection_handshake import accept_connection_handshake
from ...adapters.worker_native_identity import worker_view_namespace
from ...adapters.worker_transport import WorkerChannel, WorkerEndpoint, worker_endpoint
from ..view_stream_relay import ViewAttachGrant, ViewStreamRelay, open_worker_view_leg
from ..worker_view_stream import WorkerViewStream, WorkerViewStreams

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_VERSION = "test"


def _same_process_worker(channel: WorkerChannel) -> None:
    """Stand in for the worker owner's containment check: this test process is the worker."""
    if channel.peer.process_id != os.getpid():
        raise RefusalError(RefusalCode.PEER_UNTRUSTED)


def _operation_id() -> str:
    return content_hash_hex({"view": str(uuid4())})


def _image(sequence: int, size: int = 70_000) -> tuple[ViewImage, bytes]:
    data = bytes((sequence + index) % 251 for index in range(size))
    return (
        ViewImage(
            sequence=sequence,
            byte_length=size,
            pixel_width=4,
            pixel_height=4,
            css_width=4,
            css_height=4,
            scale=1.0,
        ),
        data,
    )


def _wait_until(condition: Callable[[], bool], *, seconds: float = 5.0) -> None:
    deadline = time.monotonic() + seconds
    while not condition():
        if time.monotonic() >= deadline:
            raise AssertionError("condition not reached")
        time.sleep(0.01)


class _Clock:
    def __init__(self) -> None:
        self.offset = 0.0

    def __call__(self) -> float:
        return time.monotonic() + self.offset


@dataclass
class _Window:
    client: ByteChannel
    server: ByteChannel
    context: ConnectionContext
    reader: ViewDownstreamReader
    thread: Thread | None = None

    def read(self) -> object:
        return self.reader.read(deadline=time.monotonic() + 5)

    def send(self, document: ViewCredit | ViewNavigate) -> None:
        write_view_document(self.client, document, deadline=time.monotonic() + 5)

    def quiet(self) -> bool:
        time.sleep(0.3)
        return not self.client.read_ready()


@dataclass
class _Lane:
    root: Path
    relay: ViewStreamRelay
    clock: _Clock
    identity: ProfileWorkerIdentity
    sink: WorkerViewStream
    operation_id: str
    session_id: UUID
    person_id: UUID
    runtime: WorkerEndpoint
    held: set[tuple[UUID, UUID]]
    windows: list[_Window] = field(default_factory=list)

    def grant(
        self,
        *,
        peer: Peer,
        session_id: UUID | None = None,
        profile_id: UUID | None = None,
        operation_id: str | None = None,
    ) -> ViewAttachGrant:
        return ViewAttachGrant(
            operation_id=operation_id or self.operation_id,
            profile_id=profile_id or self.identity.binding.profile_id,
            session_id=session_id or self.session_id,
            person_connection_id=self.person_id,
            peer=peer,
            runtime_boot_id=self.identity.runtime_boot_id,
        )

    def connect_window(self) -> _Window:
        accepted: list[ByteChannel] = []
        accepting = Thread(target=lambda: accepted.append(self.runtime.accept(timeout=5)))
        accepting.start()
        client = self.runtime_endpoint().connect(timeout=5)
        accepting.join()
        server = accepted[0]
        window = _Window(
            client=client,
            server=server,
            context=ConnectionContext(uuid4(), self.identity.runtime_boot_id, server.peer),
            reader=ViewDownstreamReader(client),
        )
        self.windows.append(window)
        return window

    def runtime_endpoint(self) -> WorkerEndpoint:
        return worker_endpoint(storage_root=self.root, worker_namespace=_RUNTIME_NAMESPACE)

    def attach(self) -> _Window:
        window = self.connect_window()
        token = self.relay.issue(self.grant(peer=window.server.peer))
        leg = self.relay.admit(
            attach_token=token, operation_id=self.operation_id, context=window.context, channel=window.server
        )
        request_id = uuid4()
        window.thread = Thread(target=self.relay.serve_window, args=(leg, request_id), daemon=True)
        window.thread.start()
        connected = read_document(window.client, ViewConnected, deadline=time.monotonic() + 5)
        assert connected.request_id == request_id
        assert connected.operation_id == self.operation_id
        return window


_RUNTIME_NAMESPACE = uuid4()


@pytest.fixture
def lane(tmp_path: Path) -> Iterator[_Lane]:
    identity = ProfileWorkerIdentity(
        worker_id=uuid4(),
        runtime_boot_id=uuid4(),
        binding=ProfileAccessBinding(
            profile_id=uuid4(),
            installation_id=uuid4(),
            os_owner_id="synthetic-owner",
            custody_generation=1,
            dek_epoch=uuid4(),
        ),
    )
    operation_id, session_id, person_id = _operation_id(), uuid4(), uuid4()
    held = {(person_id, session_id)}
    clock = _Clock()
    relay = ViewStreamRelay(
        runtime_boot_id=identity.runtime_boot_id,
        holds_session=lambda connection, session: (connection, session) in held,
        clock=clock,
    )
    sink = WorkerViewStreams(
        storage_root=tmp_path, identity=identity, parent_pid=os.getpid(), product_version=_VERSION
    ).open_view(operation_id=operation_id, session_id=session_id)
    bind, channel = open_worker_view_leg(
        storage_root=tmp_path, identity=identity, verify=_same_process_worker, product_version=_VERSION
    )
    assert bind == ViewWorkerBind(operation_id=operation_id, session_id=session_id)
    relay.bind_worker(profile_id=identity.binding.profile_id, bind=bind, channel=channel)
    _wait_until(lambda: sink.connected)
    runtime = worker_endpoint(storage_root=tmp_path, worker_namespace=_RUNTIME_NAMESPACE)
    runtime.listen()
    built = _Lane(tmp_path, relay, clock, identity, sink, operation_id, session_id, person_id, runtime, held)
    try:
        yield built
    finally:
        relay.close()
        sink.close(ViewClosedReason.CANCELLED)
        for window in built.windows:
            window.client.close()
            window.server.close()
        runtime.close()


def _refused(call: Callable[[], object]) -> AccessDenialCode | RefusalCode:
    with pytest.raises((ProfileAccessRefusedError, RefusalError)) as raised:
        call()
    error = raised.value
    assert isinstance(error, ProfileAccessRefusedError | RefusalError)
    return error.reason


def test_view_attach_from_another_session_or_profile_is_refused(lane: _Lane) -> None:
    window = lane.connect_window()
    assert (
        _refused(lambda: lane.relay.issue(lane.grant(peer=window.server.peer, session_id=uuid4())))
        is AccessDenialCode.OPERATION_UNAVAILABLE
    )
    assert (
        _refused(lambda: lane.relay.issue(lane.grant(peer=window.server.peer, profile_id=uuid4())))
        is AccessDenialCode.OPERATION_UNAVAILABLE
    )
    assert (
        _refused(lambda: lane.relay.issue(lane.grant(peer=window.server.peer, operation_id=_operation_id())))
        is AccessDenialCode.OPERATION_UNAVAILABLE
    )


def test_view_token_is_single_use_expires_and_names_its_operation(lane: _Lane) -> None:
    window = lane.connect_window()
    token = lane.relay.issue(lane.grant(peer=window.server.peer))

    def admit(presented: str, operation_id: str | None = None) -> object:
        return lane.relay.admit(
            attach_token=presented,
            operation_id=operation_id or lane.operation_id,
            context=window.context,
            channel=window.server,
        )

    assert admit(token) is not None
    # Presented once, it is spent.
    assert _refused(lambda: admit(token)) is AccessDenialCode.CONNECTION_MISMATCH

    expired = lane.relay.issue(lane.grant(peer=window.server.peer))
    lane.clock.offset += 10.0
    assert _refused(lambda: admit(expired)) is AccessDenialCode.CONNECTION_MISMATCH
    lane.clock.offset = 0.0

    other_operation = lane.relay.issue(lane.grant(peer=window.server.peer))
    assert _refused(lambda: admit(other_operation, _operation_id())) is AccessDenialCode.CONNECTION_MISMATCH
    # A refused presentation spends the token too.
    assert _refused(lambda: admit(other_operation)) is AccessDenialCode.CONNECTION_MISMATCH

    unknown = os.urandom(32).hex()
    assert _refused(lambda: admit(unknown)) is AccessDenialCode.CONNECTION_MISMATCH

    signed_out = lane.relay.issue(lane.grant(peer=window.server.peer))
    lane.held.clear()
    assert _refused(lambda: admit(signed_out)) is AccessDenialCode.AUTHENTICATION_REQUIRED


def test_view_connection_from_another_native_peer_is_refused(lane: _Lane) -> None:
    person = lane.connect_window()
    token = lane.relay.issue(lane.grant(peer=person.server.peer))
    accepted: list[ByteChannel] = []
    accepting = Thread(target=lambda: accepted.append(lane.runtime.accept(timeout=30)))
    accepting.start()
    child = subprocess.Popen(
        [
            sys.executable,
            "-c",
            # A second native peer: another process connects to the runtime endpoint and holds it.
            "import os, sys\n"
            "from pathlib import Path\n"
            "from uuid import UUID\n"
            "from cadrumo_runtime.adapters.worker_transport import worker_endpoint\n"
            "root, namespace = Path(os.environ['VIEW_TEST_ROOT']), UUID(os.environ['VIEW_TEST_NAMESPACE'])\n"
            "channel = worker_endpoint(storage_root=root, worker_namespace=namespace).connect(timeout=20)\n"
            "print('connected', flush=True)\n"
            "sys.stdin.read()\n"
            "channel.close()\n",
        ],
        env={**os.environ, "VIEW_TEST_ROOT": str(lane.root), "VIEW_TEST_NAMESPACE": str(_RUNTIME_NAMESPACE)},
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert child.stdout is not None
        assert child.stdout.readline().strip() == "connected"
        accepting.join(timeout=30)
        foreign = accepted[0]
        try:
            # A virtual environment may relaunch the interpreter, so compare peers rather than the launched pid.
            assert foreign.peer != person.server.peer
            context = ConnectionContext(uuid4(), lane.identity.runtime_boot_id, foreign.peer)
            assert (
                _refused(
                    lambda: lane.relay.admit(
                        attach_token=token, operation_id=lane.operation_id, context=context, channel=foreign
                    )
                )
                is RefusalCode.PEER_UNTRUSTED
            )
        finally:
            foreign.close()
    finally:
        assert child.stdin is not None
        child.stdin.close()
        child.wait(timeout=30)
    # The refused presentation spent the token even for its rightful peer.
    assert (
        _refused(
            lambda: lane.relay.admit(
                attach_token=token, operation_id=lane.operation_id, context=person.context, channel=person.server
            )
        )
        is AccessDenialCode.CONNECTION_MISMATCH
    )


def test_view_images_flow_only_under_window_credit_and_newest_first(lane: _Lane) -> None:
    window = lane.attach()
    lane.sink.offer_image(*_image(1))
    lane.sink.offer_image(*_image(2))
    # No credit from the window: nothing reaches it, and the worker holds no credit either.
    assert window.quiet()
    window.send(ViewCredit(images=1))
    received = window.read()
    assert isinstance(received, AssembledViewImage)
    assert received.announcement.sequence == 2
    assert received.data == _image(2)[1]
    lane.sink.offer_image(*_image(3))
    assert window.quiet()


def test_view_images_without_window_credit_are_dropped_not_buffered(lane: _Lane) -> None:
    first = lane.attach()
    first.send(ViewCredit(images=2))
    lane.sink.offer_image(*_image(1))
    image = first.read()
    assert isinstance(image, AssembledViewImage)
    assert image.announcement.sequence == 1
    # A later attach replaces the window; the worker still holds one credit from the first.
    second = lane.attach()
    closed = first.read()
    assert closed == ViewClosed(reason=ViewClosedReason.REPLACED)
    lane.sink.offer_image(*_image(2))
    # Image 2 used the worker's leftover credit and was dropped by the host as it was read.
    assert second.quiet()
    second.send(ViewCredit(images=1))
    lane.sink.offer_image(*_image(3))
    delivered = second.read()
    assert isinstance(delivered, AssembledViewImage)
    assert delivered.announcement.sequence == 3


def test_view_worker_image_without_credit_is_a_violation_not_buffered(tmp_path: Path) -> None:
    identity = ProfileWorkerIdentity(
        worker_id=uuid4(),
        runtime_boot_id=uuid4(),
        binding=ProfileAccessBinding(
            profile_id=uuid4(),
            installation_id=uuid4(),
            os_owner_id="synthetic-owner",
            custody_generation=1,
            dek_epoch=uuid4(),
        ),
    )
    operation_id, session_id = _operation_id(), uuid4()
    endpoint = worker_endpoint(storage_root=tmp_path, worker_namespace=worker_view_namespace(identity.worker_id))
    endpoint.listen()
    accepted: list[WorkerChannel] = []

    def serve() -> None:
        channel = endpoint.accept(timeout=5)
        accepted.append(channel)
        accept_connection_handshake(
            channel,
            identity=ServerHello(
                product_version=_VERSION, storage_identity=endpoint.storage_identity, boot_id=identity.runtime_boot_id
            ),
            deadline=time.monotonic() + 5,
        )
        write_document(channel, identity, deadline=time.monotonic() + 5)
        write_document(
            channel, ViewWorkerBind(operation_id=operation_id, session_id=session_id), deadline=time.monotonic() + 5
        )

    worker = Thread(target=serve)
    worker.start()
    relay = ViewStreamRelay(runtime_boot_id=identity.runtime_boot_id, holds_session=lambda _c, _s: True)
    bind, channel = open_worker_view_leg(
        storage_root=tmp_path, identity=identity, verify=_same_process_worker, product_version=_VERSION
    )
    worker.join()
    try:
        relay.bind_worker(profile_id=identity.binding.profile_id, bind=bind, channel=channel)
        announcement, data = _image(1)

        def push_uncredited_image() -> None:
            for frame in view_image_frames(announcement, data):
                accepted[0].write_all(frame, deadline=time.monotonic() + 5)
            read_document(accepted[0], ViewCredit, deadline=time.monotonic() + 5)

        # The host refuses at the announcement and closes the leg, so the image never finds a reader.
        with pytest.raises(RefusalError):
            push_uncredited_image()
        _wait_until(lambda: relay.worker_bind(operation_id) is None)
    finally:
        relay.close()
        accepted[0].close()
        endpoint.close()


def test_view_worker_leg_admits_only_the_verified_worker(tmp_path: Path) -> None:
    identity = ProfileWorkerIdentity(
        worker_id=uuid4(),
        runtime_boot_id=uuid4(),
        binding=ProfileAccessBinding(
            profile_id=uuid4(),
            installation_id=uuid4(),
            os_owner_id="synthetic-owner",
            custody_generation=1,
            dek_epoch=uuid4(),
        ),
    )

    def foreign(_channel: WorkerChannel) -> None:
        raise RefusalError(RefusalCode.PEER_UNTRUSTED)

    # No view running: nothing listens, and the attach is refused as unavailable.
    with pytest.raises(ProfileAccessRefusedError) as unavailable:
        open_worker_view_leg(storage_root=tmp_path, identity=identity, verify=foreign, product_version=_VERSION)
    assert unavailable.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE
    # The worker's composition is the port the view executor receives.
    sinks: ViewStreamSinks = WorkerViewStreams(
        storage_root=tmp_path, identity=identity, parent_pid=os.getpid(), product_version=_VERSION
    )
    sink: ViewStreamSink = sinks.open_view(operation_id=_operation_id(), session_id=uuid4())
    try:
        with pytest.raises(RefusalError):
            open_worker_view_leg(storage_root=tmp_path, identity=identity, verify=foreign, product_version=_VERSION)
        assert not sink.connected
    finally:
        sink.close(ViewClosedReason.CANCELLED)
    assert sink.ended


def test_view_operation_end_unbinds_the_window_before_the_worker_settles(lane: _Lane) -> None:
    window = lane.attach()
    lane.sink.close(ViewClosedReason.CANCELLED)
    # close() returns only once the host unbound: the operation may settle now, and nothing is bound.
    assert lane.relay.worker_bind(lane.operation_id) is None
    assert window.read() == ViewClosed(reason=ViewClosedReason.CANCELLED)
    with pytest.raises(RefusalError):
        window.read()


@pytest.mark.parametrize("retire", ["sign_out", "lock", "unheld"])
def test_view_session_retirement_unbinds_both_legs_at_once(lane: _Lane, retire: str) -> None:
    window = lane.attach()
    if retire == "unheld":
        lane.held.clear()
        lane.relay.unbind_unheld()
    else:
        # Sign-out and lock both retire the session through the same unbinding.
        lane.relay.unbind_sessions((lane.session_id,))
    # Synchronously unbound, while the worker's operation is still running.
    assert lane.relay.worker_bind(lane.operation_id) is None
    assert window.read() == ViewClosed(reason=ViewClosedReason.SESSION_RETIRED)
    _wait_until(lambda: lane.sink.ended)
    with pytest.raises(ProfileAccessRefusedError):
        lane.relay.issue(lane.grant(peer=window.server.peer))


def test_view_person_connection_close_unbinds_only_the_window(lane: _Lane) -> None:
    window = lane.attach()
    lane.relay.disconnect(lane.person_id)
    assert window.read() == ViewClosed(reason=ViewClosedReason.SESSION_RETIRED)
    assert lane.relay.worker_bind(lane.operation_id) is not None
    assert not lane.sink.ended


def test_view_window_credit_beyond_two_is_a_violation(lane: _Lane) -> None:
    window = lane.attach()
    window.send(ViewCredit(images=2))
    window.send(ViewCredit(images=1))
    assert window.read() == ViewClosed(reason=ViewClosedReason.PROTOCOL_VIOLATION)
    assert lane.relay.worker_bind(lane.operation_id) is not None


def test_view_person_input_reaches_the_worker_and_runtime_stop_unbinds(lane: _Lane) -> None:
    window = lane.attach()
    window.send(ViewNavigate(verb=ViewNavigateVerb.RELOAD))
    assert lane.sink.receive(timeout=5) == ViewNavigate(verb=ViewNavigateVerb.RELOAD)
    lane.relay.close()
    assert window.read() == ViewClosed(reason=ViewClosedReason.RUNTIME_STOPPING)
    _wait_until(lambda: lane.sink.ended)


def test_view_attach_documents_travel_the_public_request_door() -> None:
    operation_id, token = _operation_id(), os.urandom(32).hex()
    attach = ViewAttachRequest(request_id=uuid4(), profile_id=uuid4(), session_id=uuid4(), operation_id=operation_id)
    connect = ViewConnect(request_id=uuid4(), operation_id=operation_id, attach_token=token)
    assert Request.model_validate_json(attach.model_dump_json()).root == attach
    assert Request.model_validate_json(connect.model_dump_json()).root == connect
    granted = ViewAttachGranted(
        request_id=uuid4(),
        runtime_boot_id=uuid4(),
        connection_id=uuid4(),
        operation_id=operation_id,
        attach_token=token,
    )
    assert granted.expires_in_seconds == 10
    with pytest.raises(ValueError, match="attach_token"):
        ViewConnect(request_id=uuid4(), operation_id=operation_id, attach_token=token.upper())
    with pytest.raises(ValueError, match="attach_token"):
        ViewConnect(request_id=uuid4(), operation_id=operation_id, attach_token=token[:62])


def _transfer_window(window: _Window) -> tuple[ViewDownstreamReader, ViewTransferReceiver]:
    receiver = ViewTransferReceiver(ViewTransferDirection.DOWNLOAD)
    return ViewDownstreamReader(window.client, transfers=receiver), receiver


def _write_upstream(window: _Window, document: ViewTransferUpstreamDocument) -> None:
    write_view_transfer_document(window.client, document, deadline=time.monotonic() + 5)


def test_view_download_bytes_reach_the_window_under_its_transfer_credit(lane: _Lane) -> None:
    window = lane.attach()
    reader, receiver = _transfer_window(window)
    payload = os.urandom(5 * 65_520 + 1_234)
    lane.sink.send(ViewDownload(transfer_id=1, filename="justificante.pdf"))
    offer = reader.read(deadline=time.monotonic() + 5)
    assert offer == ViewDownload(transfer_id=1, filename="justificante.pdf")
    receiver.expect(1)
    _write_upstream(window, ViewDownloadAnswer(transfer_id=1, outcome=ViewDownloadOutcome.ACCEPTED))
    # The window grants credit at once; the worker holds it until its bytes are ready.
    _write_upstream(window, receiver.grant(1, 2))
    assert lane.sink.receive(timeout=5) == ViewDownloadAnswer(transfer_id=1, outcome=ViewDownloadOutcome.ACCEPTED)
    delivered: list[bool] = []
    sending = Thread(target=lambda: delivered.append(lane.sink.send_download(1, io.BytesIO(payload))), daemon=True)
    sending.start()
    received = bytearray()
    while True:
        item = reader.read(deadline=time.monotonic() + 5)
        if isinstance(item, ViewTransferChunk):
            received += item.data
            if not item.last:
                _write_upstream(window, receiver.grant(1, 1))
            continue
        assert isinstance(item, ViewTransferComplete)
        break
    sending.join(timeout=5)
    assert bytes(received) == payload and delivered == [True]


def test_view_upload_reaches_the_worker_whole_and_checked(lane: _Lane) -> None:
    window = lane.attach()
    reader, _ = _transfer_window(window)
    upload = os.urandom(2 * 65_520 + 77)
    lane.sink.send(ViewFileChooser(chooser_id=1, accept=(), multiple=False))
    assert reader.read(deadline=time.monotonic() + 5) == ViewFileChooser(chooser_id=1, accept=(), multiple=False)
    _write_upstream(window, ViewFileChooserAnswer(chooser_id=1, outcome=ViewFileChooserOutcome.SUPPLIED, file_count=1))
    _write_upstream(window, ViewUpload(chooser_id=1, transfer_id=1, name="a.bin", size=len(upload)))
    credit = reader.read(deadline=time.monotonic() + 5)
    assert isinstance(credit, ViewTransferCredit) and credit.transfer_id == 1
    sender = ViewTransferSender(1, io.BytesIO(upload))
    sender.grant(credit.chunks)
    while (chunk := sender.next_payload()) is not None:
        write_view_transfer_chunk(window.client, chunk, deadline=time.monotonic() + 5)
    _write_upstream(window, sender.completion())
    assert lane.sink.receive(timeout=5) == ViewFileChooserAnswer(
        chooser_id=1, outcome=ViewFileChooserOutcome.SUPPLIED, file_count=1
    )
    uploaded = lane.sink.receive(timeout=5)
    assert isinstance(uploaded, ViewUploadedFile)
    assert (uploaded.chooser_id, uploaded.name, uploaded.data) == (1, "a.bin", upload)


def test_view_close_from_the_window_reaches_the_worker(lane: _Lane) -> None:
    window = lane.attach()
    write_view_document(window.client, ViewClose(), deadline=time.monotonic() + 5)
    assert lane.sink.receive(timeout=5) == ViewClose()
    assert not lane.sink.ended


def test_view_window_connection_drop_closes_the_view_like_its_close(lane: _Lane) -> None:
    window = lane.attach()
    window.client.close()
    assert lane.sink.receive(timeout=5) == ViewClose()
    # A window the host unbinds is not a close: the view keeps running for the next window.
    second = lane.attach()
    lane.relay.disconnect(lane.person_id)
    assert second.read() == ViewClosed(reason=ViewClosedReason.SESSION_RETIRED)
    assert lane.sink.receive(timeout=0.5) is None
