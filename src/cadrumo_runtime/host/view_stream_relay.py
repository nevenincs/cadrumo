"""The runtime host's view stream relay between a profile worker and the window.

Each running ``live.sede.view`` has at most two legs here. The worker leg is a
verified connection the host opens to the worker's view endpoint when a window
first attaches; the worker opens it with ``view.bind``, naming its operation
and submitting session. The window leg is a view connection admitted by a
single-use attach token, bound to the exact session, profile, native peer,
runtime boot and operation, and spent by its first presentation. One window
leg is bound per operation; a later attach replaces it.

Credit passes through: the host grants the worker only what the window has
granted and not yet used, and forwards each image chunk as it reads it. An
image arriving while the window has no credit is dropped as it is read, so
the host buffers no image. Credit beyond two images on either leg, and any
frame the view codec refuses, is a protocol violation.

Person input the worker holds back waits in the worker leg for as long as
the worker lives: its own reader paces the person, and a page busy for a
while is not a failure. Only the leg's end, whether its peer went away, it
broke the protocol or the host unbound it, ends that wait. Images keep
reaching the window meanwhile under the credit the worker holds, because the
worker's frames are read on their own thread; credit the window grants later
reaches the worker behind the held input, in the order the window sent it.

Transfer documents and transfer chunks pass through unchanged in both
directions, each chunk checked for a well-formed header and never inside an
image's chunk run; their credit is end to end, between the bytes' sender and
receiver. A transfer frame for a window that is not attached is dropped. The
window's ``view.close`` passes to the worker, which then publishes and ends
the view; a window leg that drops without it, rather than being unbound by
the host or replaced, is closed the same way, the host sending ``view.close``
in its stead.

The host unbinds at once, without waiting for the worker to settle: when the
operation ends (the worker's ``view.closed``, whose acknowledgement is the
host closing the worker leg), when the submitting session is retired or
locked, when the person connection that asked for the token closes, on a
violation, and when the runtime stops. Unbinding closes the window leg after
a best-effort ``view.closed``. Frames, documents and tokens are private and
never logged; diagnostics carry only closed reason codes.
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock, RLock, Thread
from uuid import UUID

from cadrumo.application.operations.models import OperationId
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.diagnostic_log import diagnostic_event
from cadrumo.core.logging import get_logger
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.contracts import ByteChannel, ClientHello, Peer, RefusalCode, RefusalError
from cadrumo_client.contracts.transport import ConnectionContext
from cadrumo_client.contracts.view_stream import (
    VIEW_ATTACH_TOKEN_BYTES,
    VIEW_ATTACH_TOKEN_SECONDS,
    VIEW_CREDIT_MAX_IMAGES,
    ViewClose,
    ViewClosed,
    ViewClosedReason,
    ViewConnected,
    ViewCredit,
    ViewImage,
    ViewState,
    ViewWorkerBind,
)
from cadrumo_client.contracts.view_transfer import (
    ViewConnectionDownstreamDocument,
    ViewConnectionDownstreamFrame,
    ViewConnectionUpstreamDocument,
    ViewConnectionUpstreamFrame,
)
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity
from cadrumo_client.transport.frame_io import (
    DOCUMENT_FRAME_KIND,
    decode_document,
    document_frame,
    encode_frame,
    read_document,
    read_frame_of_kinds,
)
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.native_wake import NativeWake
from cadrumo_client.transport.view_stream import (
    VIEW_CHUNK_FRAME_KIND,
    ViewChunkHeader,
    ViewTransferChunkHeader,
    is_view_transfer_chunk,
    write_view_document,
)

from ..adapters.worker_native_identity import worker_view_namespace
from ..adapters.worker_transport import WorkerChannel, worker_endpoint

_LOGGER = get_logger(__name__)

_FRAME_SECONDS = 5.0
"""Each relayed frame and each leg handshake completes within this bound."""

_HELD_WRITE_SECONDS = 0xFFFFFFFE / 1000
"""A write to the worker waits up to the longest single native wait; liveness ends it first.

The worker paces person input by not reading, so this is no bound on the
person's use: the worker leg's end closes its channel, which cancels the
write, and a worker that went away fails it.
"""

_CLOSING_SECONDS = 1.0
"""The best-effort ``view.closed`` to a window being unbound; its close follows regardless."""

_WORKER_KINDS = frozenset({DOCUMENT_FRAME_KIND, VIEW_CHUNK_FRAME_KIND})


def _violation(check: str) -> RefusalError:
    return RefusalError(RefusalCode.INVALID_FRAME, check=check)


def _close_quietly(channel: ByteChannel) -> None:
    try:
        channel.close()
    except Exception as error:
        diagnostic_event(_LOGGER, "view_leg_close_failed", fields={"error_type": type(error).__name__}, level=30)


def _token_key(token: bytes) -> bytes:
    return hashlib.sha256(token).digest()


def open_worker_view_leg(
    *,
    storage_root: Path,
    identity: ProfileWorkerIdentity,
    verify: Callable[[WorkerChannel], None],
    product_version: str,
) -> tuple[ViewWorkerBind, WorkerChannel]:
    """Connect to the worker's view endpoint and admit only that worker's own native process.

    ``verify`` is the worker owner's native check of the channel's peer. An
    endpoint nobody listens on means the worker runs no view.
    """
    endpoint = worker_endpoint(storage_root=storage_root, worker_namespace=worker_view_namespace(identity.worker_id))
    try:
        channel = endpoint.connect(timeout=_FRAME_SECONDS)
    except RefusalError as error:
        if error.reason is RefusalCode.ENDPOINT_NOT_READY:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE) from None
        raise
    try:
        verify(channel)
        deadline = time.monotonic() + _FRAME_SECONDS
        connection = VerifiedConnection(
            channel,
            expected=ClientHello(product_version=product_version, storage_identity=endpoint.storage_identity),
            deadline=deadline,
        )
        if connection.hello.boot_id != identity.runtime_boot_id:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED, check="view_worker_boot")
        if read_document(channel, ProfileWorkerIdentity, deadline=deadline) != identity:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED, check="view_worker_identity")
        bind = read_document(channel, ViewWorkerBind, deadline=deadline)
    except BaseException:
        _close_quietly(channel)
        raise
    return bind, channel


@dataclass(frozen=True, slots=True)
class ViewAttachGrant:
    """Who may present a token: the exact attaching session, its person connection and native peer."""

    operation_id: OperationId
    profile_id: UUID
    session_id: UUID
    person_connection_id: UUID
    peer: Peer
    runtime_boot_id: UUID


@dataclass(slots=True)
class _PendingAttach:
    token: bytes
    grant: ViewAttachGrant
    expires_at: float


@dataclass(slots=True)
class _WindowLeg:
    channel: ByteChannel
    context: ConnectionContext
    grant: ViewAttachGrant
    stopping: NativeWake = field(default_factory=NativeWake)
    write_lock: Lock = field(default_factory=Lock)
    credit: int = 0
    ready: bool = False
    unbound: bool = False
    close_sent: bool = False


@dataclass(slots=True)
class _WorkerLeg:
    profile_id: UUID
    bind: ViewWorkerBind
    channel: WorkerChannel
    stopping: NativeWake = field(default_factory=NativeWake)
    write_lock: Lock = field(default_factory=Lock)
    credit: int = 0
    last_sequence: int | None = None
    last_state: ViewState | None = None
    window: _WindowLeg | None = None
    ended: bool = False


class ViewStreamRelay:
    """Bind view legs to their exact operation and relay frames between them under credit."""

    def __init__(
        self,
        *,
        runtime_boot_id: UUID,
        holds_session: Callable[[UUID, UUID], bool],
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """``holds_session(connection_id, session_id)`` says whether a person connection still holds that session."""
        self._boot = runtime_boot_id
        self._holds_session = holds_session
        self._clock = clock
        self._guard = RLock()
        self._workers: dict[OperationId, _WorkerLeg] = {}
        self._pending: dict[bytes, _PendingAttach] = {}
        self._opening = Lock()
        self._closed = False

    @property
    def opening(self) -> Lock:
        """Serialize opening worker legs, so two attaches cannot both connect to one worker."""
        return self._opening

    def worker_bind(self, operation_id: OperationId) -> ViewWorkerBind | None:
        """Return the bind of the worker leg serving this operation, if one is open."""
        with self._guard:
            worker = self._workers.get(operation_id)
            return None if worker is None or worker.ended else worker.bind

    def bind_worker(self, *, profile_id: UUID, bind: ViewWorkerBind, channel: WorkerChannel) -> None:
        """Adopt an admitted worker leg and start relaying from it; its window has no credit yet."""
        with self._guard:
            if self._closed:
                _close_quietly(channel)
                raise RefusalError(RefusalCode.DRAINING)
            if any(worker.profile_id == profile_id and not worker.ended for worker in self._workers.values()):
                # A worker holds one view at a time; another bound leg of this profile is stale.
                _close_quietly(channel)
                raise ProfileAccessRefusedError(AccessDenialCode.SUBJECT_BUSY)
            worker = _WorkerLeg(profile_id=profile_id, bind=bind, channel=channel)
            self._workers[bind.operation_id] = worker
        Thread(target=self._relay_worker, args=(worker,), name="view-worker-relay", daemon=True).start()

    def issue(self, grant: ViewAttachGrant) -> str:
        """Mint a single-use token for a worker leg the grant's session submitted; it lapses in ten seconds."""
        with self._guard:
            if self._closed:
                raise RefusalError(RefusalCode.DRAINING)
            worker = self._workers.get(grant.operation_id)
            if (
                worker is None
                or worker.ended
                or worker.profile_id != grant.profile_id
                or worker.bind.session_id != grant.session_id
            ):
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            self._expire_pending()
            token = secrets.token_bytes(VIEW_ATTACH_TOKEN_BYTES)
            self._pending[_token_key(token)] = _PendingAttach(
                token=token, grant=grant, expires_at=self._clock() + VIEW_ATTACH_TOKEN_SECONDS
            )
            return token.hex()

    def admit(
        self, *, attach_token: str, operation_id: OperationId, context: ConnectionContext, channel: ByteChannel
    ) -> _WindowLeg:
        """Spend a presented token and bind its view connection; every mismatch refuses it.

        The token is removed on presentation whether or not it is accepted, so
        it can never be presented twice.
        """
        presented = bytes.fromhex(attach_token)
        with self._guard:
            if self._closed:
                raise RefusalError(RefusalCode.DRAINING)
            pending = self._pending.pop(_token_key(presented), None)
            if pending is None or not hmac.compare_digest(pending.token, presented):
                raise ProfileAccessRefusedError(AccessDenialCode.CONNECTION_MISMATCH)
            grant = pending.grant
            if self._clock() >= pending.expires_at or grant.operation_id != operation_id:
                raise ProfileAccessRefusedError(AccessDenialCode.CONNECTION_MISMATCH)
            if (
                context.runtime_boot_id != self._boot
                or grant.runtime_boot_id != self._boot
                or context.peer != grant.peer
                or channel.peer != grant.peer
            ):
                raise RefusalError(RefusalCode.PEER_UNTRUSTED, check="view_connection_peer")
        # Never ask the connection owner while holding this guard: it calls in here under its own.
        if not self._holds_session(grant.person_connection_id, grant.session_id):
            raise ProfileAccessRefusedError(AccessDenialCode.AUTHENTICATION_REQUIRED)
        with self._guard:
            worker = self._workers.get(operation_id)
            if self._closed or worker is None or worker.ended or worker.bind.session_id != grant.session_id:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            replaced = worker.window
            leg = _WindowLeg(channel=channel, context=context, grant=grant)
            worker.window = leg
        if replaced is not None:
            self._unbind_window(replaced, ViewClosedReason.REPLACED)
        return leg

    def serve_window(self, leg: _WindowLeg, request_id: UUID) -> None:
        """Answer ``view_connected``, then relay the window's upstream documents until the leg unbinds."""
        with leg.write_lock:
            try:
                with self._guard:
                    worker = self._workers.get(leg.grant.operation_id)
                    if worker is None or worker.window is not leg:
                        return
                    state = worker.last_state
                leg.channel.write_all(
                    document_frame(
                        ViewConnected(
                            request_id=request_id,
                            runtime_boot_id=self._boot,
                            connection_id=leg.context.connection_id,
                            operation_id=leg.grant.operation_id,
                        )
                    ),
                    deadline=time.monotonic() + _FRAME_SECONDS,
                )
                if state is not None:
                    write_view_document(leg.channel, state, deadline=time.monotonic() + _FRAME_SECONDS)
            except RefusalError:
                self._end_window(leg)
                return
            with self._guard:
                leg.ready = not leg.unbound
        try:
            self._relay_window(leg, worker)
        finally:
            self._close_dropped_window(leg, worker)
            self._end_window(leg)

    def unbind_sessions(self, session_ids: tuple[UUID, ...]) -> None:
        """End every view a retired or locked session submitted, and spend its tokens."""
        retired = set(session_ids)
        if not retired:
            return
        with self._guard:
            self._pending = {
                key: pending for key, pending in self._pending.items() if pending.grant.session_id not in retired
            }
            ending = [worker for worker in self._workers.values() if worker.bind.session_id in retired]
        for worker in ending:
            self._end_worker(worker, ViewClosedReason.SESSION_RETIRED)

    def unbind_unheld(self) -> None:
        """End every view whose submitting session no person connection holds any longer."""
        with self._guard:
            attached = [
                (worker, worker.window.grant.person_connection_id)
                for worker in self._workers.values()
                if worker.window is not None
            ]
        ending = [worker for worker, holder in attached if not self._holds_session(holder, worker.bind.session_id)]
        for worker in ending:
            self._end_worker(worker, ViewClosedReason.SESSION_RETIRED)

    def unbind_profile(self, profile_id: UUID) -> None:
        """End every view of a profile whose worker incarnation was retired."""
        with self._guard:
            ending = [worker for worker in self._workers.values() if worker.profile_id == profile_id]
            self._pending = {
                key: pending for key, pending in self._pending.items() if pending.grant.profile_id != profile_id
            }
        for worker in ending:
            self._end_worker(worker, ViewClosedReason.OPERATION_ENDED)

    def disconnect(self, connection_id: UUID) -> None:
        """Unbind every window attached through this person connection, and spend its tokens."""
        with self._guard:
            self._pending = {
                key: pending
                for key, pending in self._pending.items()
                if pending.grant.person_connection_id != connection_id
            }
            legs = [
                worker.window
                for worker in self._workers.values()
                if worker.window is not None and worker.window.grant.person_connection_id == connection_id
            ]
        for leg in legs:
            self._unbind_window(leg, ViewClosedReason.SESSION_RETIRED)

    def close(self) -> None:
        """End every view because the runtime stops, and refuse new legs."""
        with self._guard:
            self._closed = True
            self._pending.clear()
            ending = list(self._workers.values())
        for worker in ending:
            self._end_worker(worker, ViewClosedReason.RUNTIME_STOPPING)

    def _expire_pending(self) -> None:
        instant = self._clock()
        self._pending = {key: pending for key, pending in self._pending.items() if pending.expires_at > instant}

    def _end_worker(self, worker: _WorkerLeg, reason: ViewClosedReason) -> None:
        """Unbind the window first, then close the worker leg, which ends the view in the worker."""
        with self._guard:
            if worker.ended:
                return
            worker.ended = True
            window = worker.window
            if self._workers.get(worker.bind.operation_id) is worker:
                del self._workers[worker.bind.operation_id]
            self._pending = {
                key: pending
                for key, pending in self._pending.items()
                if pending.grant.operation_id != worker.bind.operation_id
            }
        if window is not None:
            self._unbind_window(window, reason)
        worker.stopping.set()
        _close_quietly(worker.channel)
        diagnostic_event(_LOGGER, "view_unbound", fields={"reason": reason.value}, level=10)

    def _unbind_window(self, leg: _WindowLeg, reason: ViewClosedReason | None) -> None:
        """Detach the window at once, tell it why when its writer is free, and close it."""
        with self._guard:
            if leg.unbound:
                return
            leg.unbound = True
            leg.ready = False
            worker = self._workers.get(leg.grant.operation_id)
            if worker is not None and worker.window is leg:
                worker.window = None
        leg.stopping.set()
        # A writer mid-image holds the lock; closing the channel then cancels its write.
        if reason is not None and leg.write_lock.acquire(timeout=_CLOSING_SECONDS):
            try:
                closing = ViewClosed(reason=reason)
                # The close follows whether or not the window still reads.
                with contextlib.suppress(RefusalError):
                    write_view_document(leg.channel, closing, deadline=time.monotonic() + _CLOSING_SECONDS)
            finally:
                leg.write_lock.release()
        _close_quietly(leg.channel)

    def _end_window(self, leg: _WindowLeg) -> None:
        self._unbind_window(leg, None)

    @staticmethod
    def _read_window_frame(leg: _WindowLeg) -> ViewConnectionUpstreamDocument | bytes:
        """Read one upstream document, or the payload of one well-formed upload chunk."""
        kind, payload = read_frame_of_kinds(
            leg.channel, kinds=_WORKER_KINDS, deadline=time.monotonic() + _FRAME_SECONDS
        )
        if kind == VIEW_CHUNK_FRAME_KIND:
            if not is_view_transfer_chunk(payload):
                raise _violation("view_image_chunk_upstream")
            ViewTransferChunkHeader.decode(payload)
            return payload
        return decode_document(payload, ViewConnectionUpstreamFrame).root

    def _relay_window(self, leg: _WindowLeg, worker: _WorkerLeg | None) -> None:
        """Turn window credit into worker credit and forward input, uploads and close, refusing violations."""
        if worker is None:
            return
        while not leg.unbound:
            try:
                if not leg.channel.wait_readable(leg.stopping):
                    return
                item = self._read_window_frame(leg)
            except RefusalError as error:
                if error.reason is RefusalCode.INVALID_FRAME:
                    diagnostic_event(_LOGGER, "view_window_violation", fields={"check": error.check or "-"}, level=30)
                return
            forwarded: ViewConnectionUpstreamDocument | bytes
            if isinstance(item, ViewCredit):
                with self._guard:
                    violated = leg.credit + item.images > VIEW_CREDIT_MAX_IMAGES
                    grant = 0
                    if not violated:
                        leg.credit += item.images
                        grant = max(0, leg.credit - worker.credit)
                        worker.credit += grant
                if violated:
                    self._unbind_window(leg, ViewClosedReason.PROTOCOL_VIOLATION)
                    return
                if grant == 0:
                    continue
                forwarded = ViewCredit(images=grant)
            else:
                if isinstance(item, ViewClose):
                    with self._guard:
                        leg.close_sent = True
                forwarded = item
            if not self._write_worker(worker, forwarded):
                return

    def _write_worker(self, worker: _WorkerLeg, item: ViewConnectionUpstreamDocument | bytes) -> bool:
        """Write one document or upload chunk to the worker, waiting while it holds input back.

        A failure ends the view; a worker that is alive but busy is not one.
        """
        frame = encode_frame(VIEW_CHUNK_FRAME_KIND, item) if isinstance(item, bytes) else document_frame(item)
        try:
            with worker.write_lock:
                worker.channel.write_all(frame, deadline=time.monotonic() + _HELD_WRITE_SECONDS)
        except RefusalError:
            self._end_worker(worker, ViewClosedReason.FAILED)
            return False
        return True

    def _close_dropped_window(self, leg: _WindowLeg, worker: _WorkerLeg | None) -> None:
        """Close the view for a window leg that dropped on its own without sending ``view.close``.

        A leg the host unbound or replaced, or whose worker already ended, is
        not a close: those end, or keep, the view on their own terms.
        """
        if worker is None:
            return
        with self._guard:
            dropped = not leg.unbound and not leg.close_sent and worker.window is leg and not worker.ended
            if dropped:
                leg.close_sent = True
        if dropped:
            self._write_worker(worker, ViewClose())

    def _relay_worker(self, worker: _WorkerLeg) -> None:
        """Forward the worker's documents and credited images; drop images the window has no credit for."""
        reason = ViewClosedReason.OPERATION_ENDED
        try:
            while not worker.ended:
                if not worker.channel.wait_readable(worker.stopping):
                    return
                kind, payload = read_frame_of_kinds(
                    worker.channel, kinds=_WORKER_KINDS, deadline=time.monotonic() + _FRAME_SECONDS
                )
                if kind == VIEW_CHUNK_FRAME_KIND:
                    if not is_view_transfer_chunk(payload):
                        raise _violation("view_chunk_unannounced")
                    ViewTransferChunkHeader.decode(payload)
                    self._forward_frame(worker, encode_frame(VIEW_CHUNK_FRAME_KIND, payload))
                    continue
                document = decode_document(payload, ViewConnectionDownstreamFrame).root
                if isinstance(document, ViewClosed):
                    reason = document.reason
                    return
                if isinstance(document, ViewImage):
                    self._relay_image(worker, document)
                    continue
                if isinstance(document, ViewState):
                    with self._guard:
                        worker.last_state = document
                self._forward_document(worker, document)
        except RefusalError as error:
            if error.reason is RefusalCode.INVALID_FRAME:
                reason = ViewClosedReason.PROTOCOL_VIOLATION
                diagnostic_event(_LOGGER, "view_worker_violation", fields={"check": error.check or "-"}, level=30)
        finally:
            self._end_worker(worker, reason)

    def _forward_document(self, worker: _WorkerLeg, document: ViewConnectionDownstreamDocument) -> None:
        self._forward_frame(worker, document_frame(document))

    def _forward_frame(self, worker: _WorkerLeg, frame: bytes) -> None:
        """Pass one document or transfer chunk to an attached window; without one it is dropped."""
        with self._guard:
            leg = worker.window if worker.window is not None and worker.window.ready else None
        if leg is None:
            return
        with leg.write_lock:
            try:
                leg.channel.write_all(frame, deadline=time.monotonic() + _FRAME_SECONDS)
            except RefusalError:
                failed = True
            else:
                failed = False
        if failed:
            self._end_window(leg)

    def _relay_image(self, worker: _WorkerLeg, announcement: ViewImage) -> None:
        """Pass one image through chunk by chunk, or read and drop it when the window has no credit."""
        with self._guard:
            if worker.credit == 0:
                raise _violation("view_image_without_credit")
            if worker.last_sequence is not None and announcement.sequence <= worker.last_sequence:
                raise _violation("view_image_sequence")
            worker.credit -= 1
            worker.last_sequence = announcement.sequence
            leg = worker.window if worker.window is not None and worker.window.ready else None
            if leg is not None and leg.credit > 0:
                leg.credit -= 1
            else:
                leg = None
        if leg is not None and not leg.write_lock.acquire(timeout=_FRAME_SECONDS):
            leg = None
        try:
            leg = self._send_to_window(leg, document_frame(announcement))
            expected = 0
            while True:
                kind, payload = read_frame_of_kinds(
                    worker.channel, kinds=_WORKER_KINDS, deadline=time.monotonic() + _FRAME_SECONDS
                )
                if kind != VIEW_CHUNK_FRAME_KIND:
                    raise _violation("view_image_interleaved")
                header = ViewChunkHeader.decode(payload)
                if (
                    header.sequence != announcement.sequence
                    or header.image_length != announcement.byte_length
                    or header.chunk_index != expected
                ):
                    raise _violation("view_chunk_order")
                leg = self._send_to_window(leg, encode_frame(VIEW_CHUNK_FRAME_KIND, payload))
                if header.last:
                    return
                expected += 1
        finally:
            if leg is not None:
                leg.write_lock.release()

    def _send_to_window(self, leg: _WindowLeg | None, frame: bytes) -> _WindowLeg | None:
        """Write one frame to a window whose writer lock is held; a failed or unbound window is let go."""
        if leg is None:
            return None
        if not leg.unbound:
            with contextlib.suppress(RefusalError):
                leg.channel.write_all(frame, deadline=time.monotonic() + _FRAME_SECONDS)
                return leg
        leg.write_lock.release()
        self._end_window(leg)
        return None
