"""Verified worker connections to the runtime parent, reused for one exchange at a time."""

from __future__ import annotations

import time
from pathlib import Path
from threading import Condition

from cadrumo_client.contracts.contracts import ClientHello, RefusalCode, RefusalError
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.posix_channel import PosixChannel
from cadrumo_client.transport.product_version import installed_product_version

from .native_peer import require_live_native_peer
from .worker_authorization import WORKER_AUTHORIZATION_CONNECTIONS, worker_authorization_namespace
from .worker_transport import WorkerChannel, worker_endpoint

_IDLE_CONNECTIONS = 4
"""Connections kept open between exchanges; a busier moment opens more, up to the runtime's bound."""

_CONNECT_SECONDS = 5.0


class WorkerAuthorizationConnections:
    """Hold this worker's verified connections to its runtime parent.

    A connection proves the runtime's pid, OS owner, storage identity and boot
    id once, when it opens. Before every later exchange the runtime's kernel
    incarnation is checked again through the channel's retained peer. A
    connection carries no admission: each exchange is admitted when the
    runtime receives it. The worker never holds more connections than the
    runtime serves, idle and busy together.

    The pool belongs to one immutable worker identity: one worker id, runtime
    boot id and profile binding. Connections open only when an exchange needs
    one, and all of them close with the worker.
    """

    def __init__(self, *, identity: ProfileWorkerIdentity, root: Path, parent_pid: int) -> None:
        """Bind the pool to its worker and parent; nothing is opened yet."""
        self.identity, self.root, self.parent_pid = identity, root, parent_pid
        self._condition = Condition()
        self._idle: list[WorkerChannel] = []
        self._open = 0
        self._closed = False
        self.opened = 0
        """How many connections this pool has verified and opened in its life."""

    def checkout(self, deadline: float) -> WorkerChannel:
        """Return a connection for one exchange, waiting for a free one while all are busy."""
        while True:
            with self._condition:
                channel = self._take_idle(deadline)
                if channel is None:
                    self._open += 1
            if channel is None:
                return self._open_counted(deadline)
            try:
                self._require_reusable(channel)
            except BaseException as error:
                self._discard(channel)
                if isinstance(error, RefusalError):
                    continue
                raise
            return channel

    def checkin(self, channel: WorkerChannel, *, reusable: bool) -> None:
        """End one exchange: keep the connection only after a terminal frame on both sides."""
        with self._condition:
            keep = reusable and not self._closed and len(self._idle) < _IDLE_CONNECTIONS
            if keep:
                self._idle.append(channel)
                self._condition.notify()
                return
        self._discard(channel)

    def close(self) -> None:
        """Close idle connections now and every busy one when its exchange ends."""
        with self._condition:
            self._closed = True
            idle, self._idle = self._idle, []
            self._condition.notify_all()
        for channel in idle:
            self._discard(channel)

    def _take_idle(self, deadline: float) -> WorkerChannel | None:
        """Pop the most recently used idle connection, or claim room to open one; the caller holds the lock."""
        while True:
            if self._closed:
                raise RefusalError(RefusalCode.CONNECTION_CLOSED)
            if self._idle:
                return self._idle.pop()
            if self._open < WORKER_AUTHORIZATION_CONNECTIONS:
                return None
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RefusalError(RefusalCode.DEADLINE_EXCEEDED)
            self._condition.wait(remaining)

    def _require_reusable(self, channel: WorkerChannel) -> None:
        """Recheck the runtime's incarnation, and that nothing was left unread or closed meanwhile."""
        if channel.peer.process_id != self.parent_pid:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)
        require_live_native_peer(channel)
        # A clean exchange leaves nothing to read; bytes or an end of stream here mean the runtime closed it.
        if channel.read_ready():
            raise RefusalError(RefusalCode.CONNECTION_CLOSED)

    def _open_counted(self, deadline: float) -> WorkerChannel:
        """Open one connection on room already counted; give the room back if it fails."""
        try:
            channel = self._verified_parent_channel(deadline)
        except BaseException:
            with self._condition:
                self._open -= 1
                self._condition.notify()
            raise
        with self._condition:
            self.opened += 1
            if not self._closed:
                return channel
        self._discard(channel)
        raise RefusalError(RefusalCode.CONNECTION_CLOSED)

    def _discard(self, channel: WorkerChannel) -> None:
        try:
            channel.close()
        finally:
            with self._condition:
                self._open -= 1
                self._condition.notify()

    def _verified_parent_channel(self, deadline: float) -> WorkerChannel:
        """Connect to this worker's runtime parent and prove both ends before any exchange."""
        endpoint = worker_endpoint(
            storage_root=self.root, worker_namespace=worker_authorization_namespace(self.identity.worker_id)
        )
        channel: WorkerChannel | None = None
        try:
            channel = endpoint.connect(timeout=max(0.0, min(_CONNECT_SECONDS, deadline - time.monotonic())))
            if (
                channel.peer.process_id != self.parent_pid
                or channel.peer.os_owner_id != self.identity.binding.os_owner_id
            ):
                raise RefusalError(RefusalCode.PEER_UNTRUSTED)
            if isinstance(channel, PosixChannel):
                require_live_native_peer(channel)
            verified = VerifiedConnection(
                channel,
                expected=ClientHello(
                    product_version=installed_product_version(), storage_identity=endpoint.storage_identity
                ),
                deadline=deadline,
            )
            if verified.hello.boot_id != self.identity.runtime_boot_id:
                raise RefusalError(RefusalCode.PEER_UNTRUSTED)
            opened, channel = channel, None
            return opened
        finally:
            if channel is not None:
                channel.close()
            endpoint.close()
