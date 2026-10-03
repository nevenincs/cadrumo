"""Verified POSIX byte channel with kernel-derived peer identity."""

from __future__ import annotations

import os
import platform
import select
import socket
import struct
import sys
from collections.abc import Generator
from contextlib import contextmanager
from threading import RLock
from typing import TYPE_CHECKING

from ...application.runtime.contracts import RuntimePeer, RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.deadline_budget import remaining_budget
from ...application.runtime.login import RuntimeLoginEvidence
from .posix import posix_owner_uid

if TYPE_CHECKING:
    from .macos_login import MacosPeerAuditToken


def _linux_peer_credentials(sock: socket.socket) -> tuple[int, int, int]:
    if sys.platform == "linux":
        return struct.unpack("3i", sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
    raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)


def _linux_peer_pidfd_option() -> int:
    if sys.platform != "linux":
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    exposed = getattr(socket, "SO_PEERPIDFD", None)
    if type(exposed) is int and exposed > 0:
        return exposed
    # Linux's generic socket ABI uses 77 since 6.5. Other architectures can
    # assign different numbers, so an absent Python constant is not portable.
    if platform.machine().casefold() in ("x86_64", "aarch64"):
        return 77
    raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)


def _linux_peer_pidfd(sock: socket.socket) -> int:
    option = _linux_peer_pidfd_option()
    try:
        descriptor = sock.getsockopt(socket.SOL_SOCKET, option)
    except OSError:
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE) from None
    if type(descriptor) is not int or descriptor < 0:
        raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
    return descriptor


def _require_live_linux_pidfd(descriptor: int) -> None:
    if sys.platform == "linux":
        try:
            poller = select.poll()
            poller.register(descriptor, select.POLLIN | select.POLLERR | select.POLLHUP)
            if poller.poll(0):
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            return
        except OSError:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE) from None
    raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)


def _peer(sock: socket.socket) -> RuntimePeer:
    if sys.platform == "win32":
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    try:
        if sys.platform.startswith("linux"):
            pid, uid, _gid = _linux_peer_credentials(sock)
        elif sys.platform == "darwin":
            from .macos_login import macos_peer_audit_token

            token = macos_peer_audit_token(sock, expected_owner=str(posix_owner_uid()))
            uid, pid = token.effective_user_id, token.process_id
        else:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        if uid != posix_owner_uid() or pid <= 0:
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        return RuntimePeer(os_owner_id=str(uid), process_id=pid)
    except OSError:
        raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED) from None


class PosixRuntimeChannel:
    """A connected Unix socket whose peer UID has already been verified."""

    def __init__(self, sock: socket.socket) -> None:
        """Verify the connected socket before exposing any byte operations."""
        self._socket = sock
        self._capture_guard = RLock()
        self._closed = False
        try:
            self._peer = _peer(sock)
        except BaseException:
            sock.close()
            raise

    @property
    def peer(self) -> RuntimePeer:
        """Return kernel-derived peer identity, independent of path permissions."""
        return self._peer

    def capture_login(self) -> RuntimeLoginEvidence:
        """Pin the verified socket while capturing its native login provenance."""
        # Pin the socket against close/descriptor reuse until the temporary
        # PIDFD has been consumed and released. Public transport needs no PIDFD.
        with self._capture_guard:
            if self._closed or self._socket.fileno() < 0:
                raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
            if sys.platform == "darwin":
                from .macos_login import capture_macos_login

                binding = capture_macos_login(self._socket, expected_owner=self._peer.os_owner_id)
                if self._closed:
                    raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
                return binding
            descriptor = _linux_peer_pidfd(self._socket)
            try:
                try:
                    if os.get_inheritable(descriptor):
                        raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
                    _require_live_linux_pidfd(descriptor)
                    from .linux_login import capture_linux_login

                    binding = capture_linux_login(descriptor, expected_owner=self._peer.os_owner_id)
                    _require_live_linux_pidfd(descriptor)
                    if self._closed:
                        raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
                    return binding
                finally:
                    os.close(descriptor)
            except OSError:
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE) from None

    @contextmanager
    def capture_peer_pidfd(self) -> Generator[int]:
        """Pin a live socket peer while a private worker checks its cgroup."""
        with self._capture_guard:
            if self._closed or self._socket.fileno() < 0:
                raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
            descriptor = _linux_peer_pidfd(self._socket)
            try:
                if os.get_inheritable(descriptor):
                    raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
                _require_live_linux_pidfd(descriptor)
                yield descriptor
                _require_live_linux_pidfd(descriptor)
            except OSError:
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE) from None
            finally:
                os.close(descriptor)

    def capture_peer_audit_token(self) -> MacosPeerAuditToken:
        """Re-read the pinned socket peer's kernel audit token on Darwin.

        The token's pidversion is compared inside the kernel, so the result
        names the exact live incarnation that owns this connection.
        """
        with self._capture_guard:
            if self._closed or self._socket.fileno() < 0:
                raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
            if sys.platform != "darwin":
                raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
            from .macos_login import macos_peer_audit_token

            token = macos_peer_audit_token(self._socket, expected_owner=self._peer.os_owner_id)
            if token.process_id != self._peer.process_id:
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            return token

    def require_live_peer(self) -> None:
        """Prove the verified peer is still the same live kernel process."""
        if sys.platform == "darwin":
            self.capture_peer_audit_token()
            return
        with self.capture_peer_pidfd():
            pass

    def _set_deadline(self, deadline: float) -> None:
        remaining = remaining_budget(deadline)
        self._socket.settimeout(remaining)

    def read_ready(self) -> bool:
        """Poll the held socket; a readable EOF is settled by the next bounded read."""
        try:
            readable, _, _ = select.select((self._socket,), (), (), 0)
            return bool(readable)
        except (OSError, ValueError):
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED) from None

    def read_exact(self, count: int, *, deadline: float) -> bytes:
        """Bound aggregate read time even when the peer sends one byte at a time."""
        if not 0 <= count <= 64 * 1024:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        payload = bytearray()
        try:
            while len(payload) < count:
                self._set_deadline(deadline)
                block = self._socket.recv(count - len(payload))
                if not block:
                    raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
                payload.extend(block)
            return bytes(payload)
        except TimeoutError:
            raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED) from None
        except OSError:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED) from None

    def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
        """Write only to the verified connection within the remaining deadline."""
        if len(payload) > 64 * 1024 + 5:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        try:
            self._set_deadline(deadline)
            self._socket.sendall(payload)
        except TimeoutError:
            raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED) from None
        except OSError:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED) from None

    def close(self) -> None:
        """Close this stream without touching the runtime singleton lock."""
        with self._capture_guard:
            self._closed = True
            self._socket.close()
