"""Owner-held POSIX runtime endpoint and inode-fenced lifecycle."""

from __future__ import annotations

import contextlib
import errno
import os
import socket
import stat
import sys
from pathlib import Path
from typing import Never
from uuid import UUID

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.hashing import sha256_hex
from ...core.storage_environment import storage_directory
from ...core.storage_taxonomy import StorageCategory
from ...core.storage_taxonomy_locations import storage_location
from .posix import (
    _accept_socket,
    _lock_exclusive,
    _lock_flags,
    _open_lock,
    _socket_metadata,
    _unix_socket,
    open_private_namespace,
    posix_owner_uid,
    posix_storage_identity,
)
from .posix_channel import PosixRuntimeChannel


def _restore_namespace_descriptor(endpoint: PosixRuntimeEndpoint) -> None:
    if endpoint._directory_fd >= 0:
        return
    directory, descriptor = open_private_namespace(endpoint._directory, create=False)
    if directory != endpoint._directory:
        if descriptor >= 0:
            os.close(descriptor)
        raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED)
    if descriptor < 0:
        raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_NOT_READY)
    endpoint._directory_fd = descriptor


def _verify_namespace_identity(endpoint: PosixRuntimeEndpoint) -> None:
    try:
        metadata = endpoint._directory.lstat()
        held = os.fstat(endpoint._directory_fd)
        if (
            (metadata.st_dev, metadata.st_ino) != (held.st_dev, held.st_ino)
            or not stat.S_ISDIR(metadata.st_mode)
            or metadata.st_uid != posix_owner_uid()
            or metadata.st_mode & 0o077
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED)
    except OSError:
        raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED) from None


def _owned_socket_metadata(endpoint: PosixRuntimeEndpoint) -> os.stat_result:
    metadata = _socket_metadata(endpoint._directory_fd, endpoint._name)
    if metadata is None:
        raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_NOT_READY)
    if sys.platform == "win32" or not stat.S_ISSOCK(metadata.st_mode) or metadata.st_uid != posix_owner_uid():
        raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED)
    return metadata


def _verify_socket_incarnation(endpoint: PosixRuntimeEndpoint, original: os.stat_result) -> None:
    endpoint._verify_namespace()
    current = _socket_metadata(endpoint._directory_fd, endpoint._name)
    if (
        current is None
        or (current.st_dev, current.st_ino) != (original.st_dev, original.st_ino)
        or not stat.S_ISSOCK(current.st_mode)
        or current.st_uid != posix_owner_uid()
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED)


def _connect_verified_socket(
    endpoint: PosixRuntimeEndpoint,
    sock: socket.socket,
    original: os.stat_result,
    timeout: float,
) -> PosixRuntimeChannel:
    sock.settimeout(timeout)
    sock.connect(str(endpoint._path))
    _verify_socket_incarnation(endpoint, original)
    return PosixRuntimeChannel(sock)


def _raise_connect_refusal(error: OSError) -> Never:
    if error.errno in (errno.ENOENT, errno.ECONNREFUSED):
        raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_NOT_READY) from None
    raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED) from None


def _retain_endpoint_lock(endpoint: PosixRuntimeEndpoint, descriptor: int) -> None:
    metadata = os.fstat(descriptor)
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != posix_owner_uid() or metadata.st_nlink != 1:
        raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED)
    if metadata.st_mode & 0o077:
        raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED)
    try:
        _lock_exclusive(descriptor)
    except BlockingIOError:
        raise RuntimeRefusalError(RuntimeRefusalCode.OWNER_BUSY) from None
    endpoint._lock_fd = descriptor


def _bind_endpoint_listener(endpoint: PosixRuntimeEndpoint, backlog: int) -> None:
    endpoint._remove_stale_socket()
    listener = _unix_socket()
    endpoint._listener = listener
    listener.bind(str(endpoint._path))
    metadata = endpoint._path.lstat()
    endpoint._socket_identity = (metadata.st_dev, metadata.st_ino)
    os.chmod(endpoint._path, 0o600, follow_symlinks=False)
    listener.listen(backlog)
    endpoint._verify_namespace()


def _release_failed_listen(endpoint: PosixRuntimeEndpoint, descriptor: int) -> None:
    if endpoint._lock_fd is None:
        os.close(descriptor)
    else:
        endpoint.close()


class PosixRuntimeEndpoint:
    """Private endpoint namespace shared by competing clients and one owner."""

    storage_identity: str
    _path: Path
    _name: str

    def __init__(
        self,
        *,
        storage_root: Path,
        namespace: Path | None = None,
        create_namespace: bool = True,
        worker_namespace: UUID | None = None,
    ) -> None:
        """Pin an owner-only namespace; passive probes never create it."""
        if sys.platform == "win32":
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        self.storage_identity = posix_storage_identity(storage_root)
        namespace = namespace or storage_directory(
            "CADRUMO_RUNTIME_SOCKET_DIR", storage_location(StorageCategory.RUNTIME_SOCKETS).subpath, root=storage_root
        )
        self._create_namespace = create_namespace
        self._closed = False
        self._directory, self._directory_fd = open_private_namespace(namespace, create=create_namespace)
        endpoint_identity = self.storage_identity
        if worker_namespace is not None:
            endpoint_identity = sha256_hex(f"{endpoint_identity}:{worker_namespace.hex}".encode("ascii"))
        self._name = endpoint_identity[:32] + ".sock"
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
        _restore_namespace_descriptor(self)
        _verify_namespace_identity(self)

    def connect(self, *, timeout: float = 5.0) -> PosixRuntimeChannel:
        """Fence namespace/socket incarnation before exposing a verified peer."""
        self._verify_namespace()
        try:
            metadata = _owned_socket_metadata(self)
            sock = _unix_socket()
            try:
                return _connect_verified_socket(self, sock, metadata, timeout)
            except BaseException:
                sock.close()
                raise
        except OSError as error:
            _raise_connect_refusal(error)

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
            _retain_endpoint_lock(self, descriptor)
            _bind_endpoint_listener(self, backlog)
        except BaseException:
            _release_failed_listen(self, descriptor)
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
