"""Owner-held POSIX runtime sockets with separate native peer verification."""

from __future__ import annotations

import contextlib
import errno
import hashlib
import os
import platform
import select
import socket
import stat
import struct
import sys
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from threading import RLock

from ...application.runtime.contracts import RuntimePeer, RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.deadline_budget import remaining_budget
from ...application.runtime.login import RuntimeLoginEvidence


def posix_owner_uid() -> int:
    """Return the native owner UID on a supported POSIX host."""
    if sys.platform != "win32":
        return os.getuid()
    raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)


def _namespace_flags() -> int:
    if sys.platform != "win32":
        return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)


def _lock_flags() -> int:
    if sys.platform != "win32":
        return os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
    raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)


def _unix_socket() -> socket.socket:
    if sys.platform != "win32":
        return socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)


def _accept_socket(listener: socket.socket) -> socket.socket:
    if sys.platform != "win32":
        connection, _address = listener.accept()
        return connection
    raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)


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


def _lock_exclusive(descriptor: int) -> None:
    if sys.platform != "win32":
        import fcntl

        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return
    raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)


def _open_lock(directory_fd: int, name: str, flags: int) -> int:
    try:
        try:
            # Keep one persistent inode across contenders.
            return os.open(name, flags | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=directory_fd)
        except FileExistsError:
            return os.open(name, flags, dir_fd=directory_fd)
    except OSError:
        raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED) from None


def _socket_metadata(directory_fd: int, name: str) -> os.stat_result | None:
    try:
        return os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None


def posix_storage_identity(root: Path) -> str:
    """Bind aliases of one existing directory to its physical storage identity."""
    if sys.platform == "win32":
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    try:
        metadata = root.resolve(strict=True).stat()
        if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != posix_owner_uid():
            raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED)
        return hashlib.sha256(f"{posix_owner_uid()}:{metadata.st_dev}:{metadata.st_ino}".encode("ascii")).hexdigest()
    except OSError:
        raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED) from None


def _open_namespace(namespace: Path, *, create: bool) -> tuple[Path, int]:
    if sys.platform == "win32":
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    try:
        parent = namespace.parent.resolve(strict=True)
        for ancestor in (parent, *parent.parents):
            metadata = ancestor.stat()
            if metadata.st_uid not in (0, posix_owner_uid()):
                raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED)
            if metadata.st_mode & 0o022 and not metadata.st_mode & stat.S_ISVTX:
                raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED)
        path = parent / namespace.name
        if create:
            with contextlib.suppress(FileExistsError):
                path.mkdir(mode=0o700)
        else:
            try:
                path.lstat()
            except FileNotFoundError:
                return path, -1
        try:
            descriptor = os.open(path, _namespace_flags())
        except FileNotFoundError:
            if not create:
                try:
                    path.lstat()
                except FileNotFoundError:
                    return path, -1
            raise
        metadata = os.fstat(descriptor)
        if metadata.st_uid != posix_owner_uid() or metadata.st_mode & 0o077:
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


class PosixRuntimeEndpoint:
    """Private endpoint namespace shared by competing clients and one owner."""

    storage_identity: str
    _path: Path
    _name: str

    def __init__(self, *, storage_root: Path, namespace: Path | None = None, create_namespace: bool = True) -> None:
        """Pin an owner-only namespace; passive probes never create it."""
        if sys.platform == "win32":
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        self.storage_identity = posix_storage_identity(storage_root)
        # TMPDIR can differ between clients and login contexts. Ownership must
        # converge for one OS owner/root, and Darwin's per-user temporary paths
        # can exceed the Unix socket path limit after adding the endpoint name.
        namespace = namespace or Path("/").joinpath("tmp", f"cdr-{posix_owner_uid()}")
        self._create_namespace = create_namespace
        self._closed = False
        self._directory, self._directory_fd = _open_namespace(namespace, create=create_namespace)
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
        if self._closed:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
        if self._directory_fd < 0:
            directory, descriptor = _open_namespace(self._directory, create=False)
            if directory != self._directory:
                if descriptor >= 0:
                    os.close(descriptor)
                raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED)
            if descriptor < 0:
                raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_NOT_READY)
            self._directory_fd = descriptor
        try:
            metadata = self._directory.lstat()
            held = os.fstat(self._directory_fd)
            if (
                (metadata.st_dev, metadata.st_ino) != (held.st_dev, held.st_ino)
                or not stat.S_ISDIR(metadata.st_mode)
                or metadata.st_uid != posix_owner_uid()
                or metadata.st_mode & 0o077
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED)
        except OSError:
            raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED) from None

    def connect(self, *, timeout: float = 5.0) -> PosixRuntimeChannel:
        """Fence namespace/socket incarnation before exposing a verified peer."""
        self._verify_namespace()
        try:
            metadata = _socket_metadata(self._directory_fd, self._name)
            if metadata is None:
                raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_NOT_READY)
            if sys.platform == "win32" or not stat.S_ISSOCK(metadata.st_mode) or metadata.st_uid != posix_owner_uid():
                raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED)
            sock = _unix_socket()
            try:
                sock.settimeout(timeout)
                sock.connect(str(self._path))
                self._verify_namespace()
                current = _socket_metadata(self._directory_fd, self._name)
                if (
                    current is None
                    or (current.st_dev, current.st_ino) != (metadata.st_dev, metadata.st_ino)
                    or not stat.S_ISSOCK(current.st_mode)
                    or current.st_uid != posix_owner_uid()
                ):
                    raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED)
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
        if not self._create_namespace:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        if self._lock_fd is not None:
            raise RuntimeRefusalError(RuntimeRefusalCode.OWNER_BUSY)
        self._verify_namespace()
        lock_name = self._name.removesuffix(".sock") + ".lock"
        flags = _lock_flags()
        # Exclusive creation avoids Darwin's observed concurrent O_CREAT/openat
        # ENOENT race. The persistent inode is never replaced or unlinked.
        descriptor = _open_lock(self._directory_fd, lock_name, flags)
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != posix_owner_uid() or metadata.st_nlink != 1:
                raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED)
            if metadata.st_mode & 0o077:
                raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED)
            try:
                _lock_exclusive(descriptor)
            except BlockingIOError:
                raise RuntimeRefusalError(RuntimeRefusalCode.OWNER_BUSY) from None
            self._lock_fd = descriptor
            self._remove_stale_socket()
            listener = _unix_socket()
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
        metadata = _socket_metadata(self._directory_fd, self._name)
        if metadata is not None:
            if not stat.S_ISSOCK(metadata.st_mode) or metadata.st_uid != posix_owner_uid():
                raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED)
            with _unix_socket() as probe:
                probe.settimeout(0.25)
                try:
                    probe.connect(str(self._path))
                except OSError as error:
                    if error.errno != errno.ECONNREFUSED:
                        raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED) from None
                else:
                    raise RuntimeRefusalError(RuntimeRefusalCode.OWNER_BUSY)
            self._verify_namespace()
            current = _socket_metadata(self._directory_fd, self._name)
            if current is None or (metadata.st_dev, metadata.st_ino) != (current.st_dev, current.st_ino):
                raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED)
            os.unlink(self._name, dir_fd=self._directory_fd)

    def accept(self, *, timeout: float = 5.0) -> PosixRuntimeChannel:
        """Return only accepted connections with native owner identity verified."""
        if self._listener is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        self._listener.settimeout(timeout)
        try:
            return PosixRuntimeChannel(_accept_socket(self._listener))
        except TimeoutError:
            raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED) from None

    def close(self) -> None:
        """Remove only the owned socket inode; never unlink the ownership lock."""
        self._closed = True
        if self._listener is not None:
            self._listener.close()
            self._listener = None
        if self._socket_identity is not None:
            with contextlib.suppress(OSError):
                metadata = _socket_metadata(self._directory_fd, self._name)
                if metadata is not None and (metadata.st_dev, metadata.st_ino) == self._socket_identity:
                    os.unlink(self._name, dir_fd=self._directory_fd)
            self._socket_identity = None
        if self._lock_fd is not None:
            os.close(self._lock_fd)
            self._lock_fd = None
        if self._directory_fd >= 0:
            os.close(self._directory_fd)
            self._directory_fd = -1
