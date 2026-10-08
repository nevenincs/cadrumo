"""Owner-held POSIX runtime sockets with separate native peer verification."""

from __future__ import annotations

import contextlib
import os
import socket
import stat
import sys
from pathlib import Path

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.hashing import sha256_hex


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
        return sha256_hex(f"{posix_owner_uid()}:{metadata.st_dev}:{metadata.st_ino}".encode("ascii"))
    except OSError:
        raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED) from None


def _validate_namespace_ancestors(parent: Path) -> None:
    for ancestor in (parent, *parent.parents):
        metadata = ancestor.stat()
        if metadata.st_uid not in (0, posix_owner_uid()):
            raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED)
        if metadata.st_mode & 0o022 and not metadata.st_mode & stat.S_ISVTX:
            raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED)


def _prepare_namespace(path: Path, *, create: bool) -> bool:
    if create:
        with contextlib.suppress(FileExistsError):
            path.mkdir(mode=0o700)
        return True
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    return True


def _namespace_path_is_missing(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return True
    return False


def _open_namespace_directory(path: Path, *, create: bool) -> int:
    try:
        return os.open(path, _namespace_flags())
    except FileNotFoundError:
        if not create and _namespace_path_is_missing(path):
            return -1
        raise


def _validate_namespace_descriptor(descriptor: int) -> None:
    metadata = os.fstat(descriptor)
    if metadata.st_uid != posix_owner_uid() or metadata.st_mode & 0o077:
        os.close(descriptor)
        raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED)


def open_private_namespace(namespace: Path, *, create: bool) -> tuple[Path, int]:
    """Open one owner-only namespace below trusted ancestors without following its leaf."""
    if sys.platform == "win32":
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    try:
        parent = namespace.parent.resolve(strict=True)
        _validate_namespace_ancestors(parent)
        path = parent / namespace.name
        if not _prepare_namespace(path, create=create):
            return path, -1
        descriptor = _open_namespace_directory(path, create=create)
        if descriptor < 0:
            return path, descriptor
        _validate_namespace_descriptor(descriptor)
        return path, descriptor
    except OSError:
        raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED) from None
