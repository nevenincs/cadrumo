"""Correlated runtime exchanges and success-only native channel cleanup."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from threading import RLock
from uuid import UUID

from ...application.runtime.access_management import (
    RuntimeSessionInventoryTransfer,
)
from ...application.runtime.contracts import (
    RuntimeByteChannel,
    RuntimeRefusalCode,
    RuntimeRefusalError,
    RuntimeServerHello,
)
from ...application.runtime.deadline_budget import remaining_budget
from ...application.runtime.profile_access import (
    RuntimeAccessRefusal,
    RuntimeProfileStatusTransfer,
    RuntimeReply,
    RuntimeSecretReady,
)
from .runtime_frame_io import (
    SecretBearingRequest,
    read_document,
    read_profile_status,
    read_session_inventory,
    write_document,
    write_secret,
)
from .runtime_transport_cleanup import RuntimeTransportCleanup, close_runtime_transport_after_failure


class RuntimeVerifiedTransport:
    """Correlated runtime exchanges and success-only native channel cleanup."""

    _channel: RuntimeByteChannel
    _exchange_lock: RLock
    _closed: bool
    _channel_closed: bool
    _connection_id: UUID | None
    hello: RuntimeServerHello

    def _close_after_failure(self, error: BaseException) -> None:
        retained = error.__dict__.get("_runtime_transport_cleanup")
        if isinstance(retained, RuntimeTransportCleanup) and retained.resource is self._channel:
            # An inner frame failure already attempted this native release.
            # Fence exchanges now, and let its retained owner retry through
            # the connection's success-only channel-close bookkeeping.
            self._closed = True
            self._channel_closed = retained.released
            retained.resource = self
            return
        close_runtime_transport_after_failure(self, error)

    @contextmanager
    def _exchange(self, *, deadline: float, secret: bytearray | None = None) -> Generator[None]:
        """Include queueing in the total budget without closing another caller's exchange."""
        try:
            remaining = remaining_budget(deadline)
            if not self._exchange_lock.acquire(timeout=remaining):
                raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
            try:
                yield
            finally:
                self._exchange_lock.release()
        finally:
            if secret is not None:
                secret[:] = bytes(len(secret))

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
                    raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
                write_secret(self._channel, secret, deadline=deadline)
            except BaseException as error:
                self._close_after_failure(error)
                raise
            finally:
                secret[:] = bytes(len(secret))

    def _reply(self, request_id: UUID, *, deadline: float) -> RuntimeReply:
        if self._closed:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
        result = read_document(self._channel, RuntimeReply, deadline=deadline)
        self._verify_reply(request_id, result.root.request_id, result.root.runtime_boot_id, result.root.connection_id)
        if isinstance(result.root, RuntimeProfileStatusTransfer):
            result = RuntimeReply(read_profile_status(self._channel, result.root, deadline=deadline))
        elif isinstance(result.root, RuntimeSessionInventoryTransfer):
            result = RuntimeReply(read_session_inventory(self._channel, result.root, deadline=deadline))
        return result

    def _verify_reply(self, expected: UUID, received: UUID, boot: UUID, connection: UUID) -> None:
        if (
            expected != received
            or boot != self.hello.boot_id
            or (self._connection_id is not None and self._connection_id != connection)
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        self._connection_id = connection

    def _deliver_secret(
        self, request: SecretBearingRequest, secret: bytearray, *, deadline: float
    ) -> tuple[RuntimeSecretReady, RuntimeReply] | RuntimeAccessRefusal:
        """Send one request, then its secret only after the peer's correlated readiness.

        A refusal before readiness is returned without consuming the secret.
        Otherwise the readiness document and the peer's final reply come back.
        """
        write_document(self._channel, request, deadline=deadline)
        ready = self._reply(request.request_id, deadline=deadline).root
        if isinstance(ready, RuntimeAccessRefusal):
            return ready
        if not isinstance(ready, RuntimeSecretReady):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        self.send_secret(secret, deadline=deadline)
        return ready, self._reply(request.request_id, deadline=deadline)

    def close(self) -> None:
        """Stop exchanges immediately and retry failed owned channel cleanup."""
        with self._exchange_lock:
            self._closed = True
            if not self._channel_closed:
                self._channel.close()
                self._channel_closed = True
