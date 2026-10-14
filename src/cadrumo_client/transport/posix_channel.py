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

from ..contracts.contracts import Peer, RefusalCode, RefusalError
from ..contracts.deadline_budget import remaining_budget
from .posix import posix_owner_uid


def _linux_peer_credentials(sock: socket.socket) -> tuple[int, int, int]:
    if sys.platform == "linux":
        return struct.unpack("3i", sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
    raise RefusalError(RefusalCode.UNAVAILABLE)


def _linux_peer_pidfd_option() -> int:
    if sys.platform != "linux":
        raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
    exposed = getattr(socket, "SO_PEERPIDFD", None)
    if type(exposed) is int and exposed > 0:
        return exposed
    # Linux's generic socket ABI uses 77 since 6.5. Other architectures can
    # assign different numbers, so an absent Python constant is not portable.
    if platform.machine().casefold() in ("x86_64", "aarch64"):
        return 77
    raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)


def _linux_peer_pidfd(sock: socket.socket) -> int:
    option = _linux_peer_pidfd_option()
    try:
        descriptor = sock.getsockopt(socket.SOL_SOCKET, option)
    except OSError:
        raise RefusalError(RefusalCode.UNAVAILABLE) from None
    if type(descriptor) is not int or descriptor < 0:
        raise RefusalError(RefusalCode.PEER_UNTRUSTED)
    return descriptor


def _require_live_linux_pidfd(descriptor: int) -> None:
    if sys.platform == "linux":
        try:
            poller = select.poll()
            poller.register(descriptor, select.POLLIN | select.POLLERR | select.POLLHUP)
            if poller.poll(0):
                raise RefusalError(RefusalCode.PEER_UNTRUSTED)
            return
        except OSError:
            raise RefusalError(RefusalCode.UNAVAILABLE) from None
    raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)


def _linux_pidfd_process_id(descriptor: int) -> int | None:
    with open(f"/proc/self/fdinfo/{descriptor}", encoding="ascii") as info:
        for line in info:
            name, _, value = line.partition(":")
            if name == "Pid":
                return int(value)
    return None


def _linux_peer_image_path(sock: socket.socket, pid: int) -> str | None:
    """Read the peer's program while its pidfd pins the process, so a reused pid cannot answer.

    The program is evidence shown to a person, not an admission check: a
    kernel without peer pidfds, or a read that does not hold, reports none.
    """
    try:
        descriptor = _linux_peer_pidfd(sock)
    except RefusalError:
        return None
    try:
        _require_live_linux_pidfd(descriptor)
        if _linux_pidfd_process_id(descriptor) != pid:
            return None
        path = os.readlink(f"/proc/{pid}/exe")
        # Still alive after the read: the pid named this process throughout.
        _require_live_linux_pidfd(descriptor)
    except (OSError, ValueError, RefusalError):
        return None
    finally:
        os.close(descriptor)
    return path or None


def _peer(sock: socket.socket) -> Peer:
    if sys.platform == "win32":
        raise RefusalError(RefusalCode.UNAVAILABLE)
    try:
        if sys.platform.startswith("linux"):
            pid, uid, _gid = _linux_peer_credentials(sock)
            image_path = _linux_peer_image_path(sock, pid) if pid > 0 else None
        elif sys.platform == "darwin":
            payload = sock.getsockopt(0, 6, 32)
            if len(payload) != 32:
                raise RefusalError(RefusalCode.PEER_UNTRUSTED)
            audit_uid, uid, _effective_gid, real_uid, _real_gid, pid, session_id, version = struct.unpack(
                "=8I", payload
            )
            reported_pid = struct.unpack("=i", sock.getsockopt(0, 2, 4))[0]
            if (
                uid != posix_owner_uid()
                or real_uid != uid
                or audit_uid != uid
                or not 0 < pid <= 2_147_483_647
                or pid != reported_pid
                or not 0 < session_id < 0xFFFFFFFE
                or version <= 0
                or sock.getsockopt(0, 6, 32) != payload
            ):
                raise RefusalError(RefusalCode.PEER_UNTRUSTED)
            image_path = None
        else:
            raise RefusalError(RefusalCode.UNAVAILABLE)
        if uid != posix_owner_uid() or pid <= 0:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)
        return Peer(os_owner_id=str(uid), process_id=pid, image_path=image_path)
    except OSError:
        raise RefusalError(RefusalCode.PEER_UNTRUSTED) from None


class PosixChannel:
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
    def peer(self) -> Peer:
        """Return kernel-derived peer identity, independent of path permissions."""
        return self._peer

    @contextmanager
    def pinned_peer_socket(self) -> Generator[socket.socket]:
        """Hold this verified socket open while host policy samples native peer facts."""
        with self._capture_guard:
            if self._closed or self._socket.fileno() < 0:
                raise RefusalError(RefusalCode.CONNECTION_CLOSED)
            yield self._socket
            if self._closed or self._socket.fileno() < 0:
                raise RefusalError(RefusalCode.CONNECTION_CLOSED)

    @contextmanager
    def capture_peer_pidfd(self) -> Generator[int]:
        """Pin a live socket peer while a private worker checks its cgroup."""
        with self._capture_guard:
            if self._closed or self._socket.fileno() < 0:
                raise RefusalError(RefusalCode.CONNECTION_CLOSED)
            descriptor = _linux_peer_pidfd(self._socket)
            try:
                if os.get_inheritable(descriptor):
                    raise RefusalError(RefusalCode.PEER_UNTRUSTED)
                _require_live_linux_pidfd(descriptor)
                yield descriptor
                if self._closed or self._socket.fileno() < 0:
                    raise RefusalError(RefusalCode.CONNECTION_CLOSED)
                _require_live_linux_pidfd(descriptor)
            except OSError:
                raise RefusalError(RefusalCode.UNAVAILABLE) from None
            finally:
                os.close(descriptor)

    def _set_deadline(self, deadline: float) -> None:
        remaining = remaining_budget(deadline)
        self._socket.settimeout(remaining)

    def read_ready(self) -> bool:
        """Poll the held socket; a readable EOF is settled by the next bounded read."""
        try:
            readable, _, _ = select.select((self._socket,), (), (), 0)
            return bool(readable)
        except (OSError, ValueError):
            raise RefusalError(RefusalCode.CONNECTION_CLOSED) from None

    def read_exact(self, count: int, *, deadline: float) -> bytes:
        """Bound aggregate read time even when the peer sends one byte at a time."""
        if not 0 <= count <= 64 * 1024:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        payload = bytearray()
        try:
            while len(payload) < count:
                self._set_deadline(deadline)
                block = self._socket.recv(count - len(payload))
                if not block:
                    raise RefusalError(RefusalCode.CONNECTION_CLOSED)
                payload.extend(block)
            return bytes(payload)
        except TimeoutError:
            raise RefusalError(RefusalCode.DEADLINE_EXCEEDED) from None
        except OSError:
            raise RefusalError(RefusalCode.CONNECTION_CLOSED) from None

    def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
        """Write only to the verified connection within the remaining deadline."""
        if len(payload) > 64 * 1024 + 5:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        try:
            self._set_deadline(deadline)
            self._socket.sendall(payload)
        except TimeoutError:
            raise RefusalError(RefusalCode.DEADLINE_EXCEEDED) from None
        except OSError:
            raise RefusalError(RefusalCode.CONNECTION_CLOSED) from None

    def close(self) -> None:
        """Close this stream without touching the runtime singleton lock."""
        with self._capture_guard:
            self._closed = True
            self._socket.close()
