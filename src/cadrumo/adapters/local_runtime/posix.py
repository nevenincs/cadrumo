"""Owner-held POSIX runtime sockets with separate native peer verification."""

from __future__ import annotations

import contextlib
import errno
import hashlib
import math
import os
import select
import socket
import stat
import struct
import sys
import time
from pathlib import Path

from ...application.runtime.contracts import RuntimePeer, RuntimeRefusalCode, RuntimeRefusalError


def posix_storage_identity(root: Path) -> str:
    """Bind aliases of one existing directory to its physical storage identity."""
    if sys.platform == "win32":
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    try:
        metadata = root.resolve(strict=True).stat()
        if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid():
            raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED)
    except OSError:
        raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED) from None
    digest = hashlib.sha256(f"{os.getuid()}:{metadata.st_dev}:{metadata.st_ino}".encode("ascii")).hexdigest()
    return digest


def _open_namespace(namespace: Path) -> tuple[Path, int]:
    if sys.platform == "win32":
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    try:
        parent = namespace.parent.resolve(strict=True)
        for ancestor in (parent, *parent.parents):
            metadata = ancestor.stat()
            if metadata.st_uid not in (0, os.getuid()):
                raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED)
            if metadata.st_mode & 0o022 and not metadata.st_mode & stat.S_ISVTX:
                raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED)
        path = parent / namespace.name
        with contextlib.suppress(FileExistsError):
            path.mkdir(mode=0o700)
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        metadata = os.fstat(descriptor)
        if metadata.st_uid != os.getuid() or metadata.st_mode & 0o077:
            os.close(descriptor)
            raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED)
        return path, descriptor
    except OSError:
        raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED) from None


def _peer(sock: socket.socket) -> RuntimePeer:
    if sys.platform == "win32":
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    try:
        if sys.platform.startswith("linux"):
            pid, uid, _gid = struct.unpack("3i", sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        elif sys.platform == "darwin":
            import ctypes

            libc = ctypes.CDLL(None, use_errno=True)
            uid_value, gid_value = ctypes.c_uint(), ctypes.c_uint()
            getpeereid = libc.getpeereid
            getpeereid.argtypes = (ctypes.c_int, ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint))
            getpeereid.restype = ctypes.c_int
            if getpeereid(sock.fileno(), ctypes.byref(uid_value), ctypes.byref(gid_value)) != 0:
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            uid = uid_value.value
            pid = struct.unpack("i", sock.getsockopt(0, 2, 4))[0]
        else:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        if uid != os.getuid() or pid <= 0:
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        return RuntimePeer(os_owner_id=str(uid), process_id=pid)
    except OSError:
        raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED) from None


class PosixRuntimeChannel:
    """A connected Unix socket whose peer UID has already been verified."""

    def __init__(self, sock: socket.socket) -> None:
        """Verify the connected socket before exposing any byte operations."""
        self._socket = sock
        try:
            self._peer = _peer(sock)
        except BaseException:
            sock.close()
            raise

    @property
    def peer(self) -> RuntimePeer:
        """Return kernel-derived peer identity, independent of path permissions."""
        return self._peer

    def _set_deadline(self, deadline: float) -> None:
        remaining = deadline - time.monotonic()
        if not math.isfinite(remaining) or remaining <= 0:
            raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
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
        self._socket.close()


class PosixRuntimeEndpoint:
    """Private endpoint namespace shared by competing clients and one owner."""

    storage_identity: str
    _path: Path
    _name: str

    def __init__(self, *, storage_root: Path, namespace: Path | None = None) -> None:
        """Pin an owner-only directory and one physical storage-root identity."""
        if sys.platform == "win32":
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        self.storage_identity = posix_storage_identity(storage_root)
        # TMPDIR can differ between clients and login contexts. Ownership must
        # converge for one OS owner/root, and Darwin's per-user temporary paths
        # can exceed the Unix socket path limit after adding the endpoint name.
        namespace = namespace or Path("/").joinpath("tmp", f"cdr-{os.getuid()}")
        self._directory, self._directory_fd = _open_namespace(namespace)
        self._name = self.storage_identity[:32] + ".sock"
        self._path = self._directory / self._name
        self._lock_fd: int | None = None
        self._listener: socket.socket | None = None
        self._socket_identity: tuple[int, int] | None = None
        if len(os.fsencode(self._path)) >= 104:
            self.close()
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)

    def _verify_namespace(self) -> None:
        if sys.platform == "win32":
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        try:
            metadata = self._directory.lstat()
            held = os.fstat(self._directory_fd)
        except OSError:
            raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED) from None
        if (
            (metadata.st_dev, metadata.st_ino) != (held.st_dev, held.st_ino)
            or not stat.S_ISDIR(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or metadata.st_mode & 0o077
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED)

    def connect(self, *, timeout: float = 5.0) -> PosixRuntimeChannel:
        """Connect after validating the namespace and socket, then verify the peer."""
        self._verify_namespace()
        try:
            metadata = self._path.lstat()
            if sys.platform == "win32" or not stat.S_ISSOCK(metadata.st_mode) or metadata.st_uid != os.getuid():
                raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED)
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                sock.settimeout(timeout)
                sock.connect(str(self._path))
                return PosixRuntimeChannel(sock)
            except BaseException:
                sock.close()
                raise
        except OSError as error:
            if error.errno in (errno.ENOENT, errno.ECONNREFUSED):
                raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_NOT_READY) from None
            raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED) from None

    def listen(self, *, backlog: int = 32) -> None:
        """Acquire the persistent lock inode before recovering a proven stale socket."""
        if sys.platform == "win32":
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        import fcntl

        if self._lock_fd is not None:
            raise RuntimeRefusalError(RuntimeRefusalCode.OWNER_BUSY)
        self._verify_namespace()
        lock_name = self._name.removesuffix(".sock") + ".lock"
        flags = os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
        try:
            try:
                # Exclusive creation avoids Darwin's observed concurrent
                # O_CREAT/openat ENOENT race. The persistent inode is never
                # replaced or unlinked; every contender locks that inode.
                descriptor = os.open(lock_name, flags | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=self._directory_fd)
            except FileExistsError:
                descriptor = os.open(lock_name, flags, dir_fd=self._directory_fd)
        except OSError:
            raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED) from None
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid() or metadata.st_nlink != 1:
                raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED)
            if metadata.st_mode & 0o077:
                raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeRefusalError(RuntimeRefusalCode.OWNER_BUSY) from None
            self._lock_fd = descriptor
            self._remove_stale_socket()
            listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._listener = listener
            listener.bind(str(self._path))
            metadata = self._path.lstat()
            self._socket_identity = (metadata.st_dev, metadata.st_ino)
            os.chmod(self._path, 0o600, follow_symlinks=False)
            listener.listen(backlog)
            self._verify_namespace()
        except BaseException:
            if self._lock_fd is None:
                os.close(descriptor)
            else:
                self.close()
            raise

    def _remove_stale_socket(self) -> None:
        if sys.platform == "win32":
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        try:
            metadata = self._path.lstat()
        except FileNotFoundError:
            return
        if not stat.S_ISSOCK(metadata.st_mode) or metadata.st_uid != os.getuid():
            raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
            probe.settimeout(0.25)
            try:
                probe.connect(str(self._path))
            except OSError as error:
                if error.errno != errno.ECONNREFUSED:
                    raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED) from None
            else:
                raise RuntimeRefusalError(RuntimeRefusalCode.OWNER_BUSY)
        current = self._path.lstat()
        if (metadata.st_dev, metadata.st_ino) != (current.st_dev, current.st_ino):
            raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED)
        os.unlink(self._name, dir_fd=self._directory_fd)

    def accept(self, *, timeout: float = 5.0) -> PosixRuntimeChannel:
        """Return only accepted connections with native owner identity verified."""
        if self._listener is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        self._listener.settimeout(timeout)
        try:
            connection, _address = self._listener.accept()
            return PosixRuntimeChannel(connection)
        except TimeoutError:
            raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED) from None

    def close(self) -> None:
        """Remove only the owned socket inode; never unlink the ownership lock."""
        if self._listener is not None:
            self._listener.close()
            self._listener = None
        if self._socket_identity is not None:
            with contextlib.suppress(OSError):
                metadata = self._path.lstat()
                if (metadata.st_dev, metadata.st_ino) == self._socket_identity:
                    os.unlink(self._name, dir_fd=self._directory_fd)
            self._socket_identity = None
        if self._lock_fd is not None:
            os.close(self._lock_fd)
            self._lock_fd = None
        if self._directory_fd >= 0:
            os.close(self._directory_fd)
            self._directory_fd = -1
