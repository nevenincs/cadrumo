"""Bounded concurrent transport hosting over native owner-verified endpoints."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore, Event
from typing import Protocol
from uuid import UUID, uuid4

from ...application.runtime.contracts import (
    RuntimeByteChannel,
    RuntimeRefusalCode,
    RuntimeRefusalError,
    RuntimeServerHello,
)
from ...application.runtime.operation_access import (
    RuntimeOperationContract,
    RuntimeOperationControl,
    RuntimeOperationObserve,
    RuntimeOperationSubmit,
)
from ...application.runtime.profile_access import RuntimeAccessRefusal, RuntimeProfileHandler, RuntimeRequest
from ...application.runtime.transport import RuntimeConnectionContext, RuntimeStatusRequest, RuntimeTransportStatus
from .framing import accept_runtime_handshake, read_document, write_document


class RuntimeListener(Protocol):
    """Exclusive native ownership with bounded acceptance and verified peers."""

    @property
    def storage_identity(self) -> str:
        """Return the canonical root identity selected by the native endpoint."""
        ...

    def listen(self) -> None:
        """Claim ownership, refusing any existing live owner."""
        ...

    def accept(self, *, timeout: float) -> RuntimeByteChannel:
        """Accept a kernel-verified peer within the supplied deadline."""
        ...

    def close(self) -> None:
        """Release native listener ownership after accepted channels settle."""
        ...


class RuntimeTransportServer:
    """Host public readiness and the application-owned profile admission door.

    Each unauthenticated connection has bounded I/O and its own identity. The
    fixed worker count bounds peer resource consumption. Operation execution
    belongs to the application supervisor, never to this transport pool.
    """

    def __init__(
        self,
        listener: RuntimeListener,
        *,
        product_version: str,
        stop: Event,
        profiles: RuntimeProfileHandler | None = None,
        boot_id: UUID | None = None,
    ) -> None:
        """Bind one endpoint and a fresh process boot, without claiming ownership yet."""
        self.listener = listener
        self.stop = stop
        self.profiles = profiles
        self.identity = RuntimeServerHello(
            product_version=product_version, storage_identity=listener.storage_identity, boot_id=boot_id or uuid4()
        )
        self.ready = Event()
        self._failed = Event()
        self._slots = BoundedSemaphore(32)

    def _connection(self, channel: RuntimeByteChannel) -> None:
        context = RuntimeConnectionContext(uuid4(), self.identity.boot_id, channel.peer)
        try:
            accept_runtime_handshake(channel, identity=self.identity, deadline=time.monotonic() + 5)
            while not self.stop.is_set():
                if not channel.read_ready():
                    self.stop.wait(0.05)
                    continue
                request = read_document(channel, RuntimeRequest, deadline=time.monotonic() + 5).root
                if isinstance(request, RuntimeStatusRequest):
                    status = RuntimeTransportStatus(
                        request_id=request.request_id,
                        runtime_boot_id=context.runtime_boot_id,
                        connection_id=context.connection_id,
                        accepting_connections=not self.stop.is_set(),
                    )
                elif isinstance(
                    request,
                    RuntimeOperationSubmit
                    | RuntimeOperationControl
                    | RuntimeOperationObserve
                    | RuntimeOperationContract,
                ):
                    if self.profiles is not None:
                        self.profiles.operation(context, channel, request)
                        continue
                    status = RuntimeAccessRefusal(
                        request_id=request.request_id,
                        runtime_boot_id=context.runtime_boot_id,
                        connection_id=context.connection_id,
                        code=RuntimeRefusalCode.UNAVAILABLE,
                    )
                elif self.profiles is not None:
                    status = self.profiles.handle(context, channel, request)
                else:
                    status = RuntimeAccessRefusal(
                        request_id=request.request_id,
                        runtime_boot_id=context.runtime_boot_id,
                        connection_id=context.connection_id,
                        code=RuntimeRefusalCode.UNAVAILABLE,
                    )
                write_document(channel, status, deadline=time.monotonic() + 5)
        except RuntimeRefusalError:
            # No peer input or secret bytes become a diagnostic. Incompatible,
            # malformed, disconnected and timed-out connections end locally.
            return
        except Exception:
            self._failed.set()
            self.stop.set()
        finally:
            try:
                if self.profiles is not None:
                    self.profiles.disconnect(context)
            except Exception:
                self._failed.set()
                self.stop.set()
            finally:
                channel.close()
                self._slots.release()

    def serve(self) -> None:
        """Hold singleton ownership through all accepted connection cleanup."""
        try:
            self.listener.listen()
            with ThreadPoolExecutor(max_workers=32, thread_name_prefix="cadrumo-ipc") as workers:
                self.ready.set()
                try:
                    self._accept_connections(workers)
                finally:
                    self.stop.set()
            if self._failed.is_set():
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        finally:
            self.ready.clear()
            try:
                if self.profiles is not None:
                    self.profiles.close()
            finally:
                self.listener.close()

    def _accept_connections(self, workers: ThreadPoolExecutor) -> None:
        while not self.stop.is_set():
            if self.profiles is not None:
                self.profiles.poll()
            try:
                channel = self.listener.accept(timeout=0.2)
            except RuntimeRefusalError as error:
                if error.reason in {
                    RuntimeRefusalCode.DEADLINE_EXCEEDED,
                    RuntimeRefusalCode.PEER_UNTRUSTED,
                    RuntimeRefusalCode.CONNECTION_CLOSED,
                }:
                    continue
                raise
            if self.stop.is_set() or not self._slots.acquire(blocking=False):
                channel.close()
                continue
            try:
                workers.submit(self._connection, channel)
            except BaseException:
                channel.close()
                self._slots.release()
                raise
