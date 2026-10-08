"""Lazy native Darwin transport directory resolution with retained inode custody."""

from __future__ import annotations

import os
import stat
import sys
from contextlib import suppress
from functools import cache
from pathlib import Path
from threading import RLock

from .product_identity import PRODUCT_IDENTITY

# Public Darwin SDK unistd.h. Python does not expose this confstr name on macOS.
_CS_DARWIN_USER_CACHE_DIR = 65538
_RESOLUTION_LOCK = RLock()


def _directory_flags() -> int:
    if sys.platform != "win32":
        return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    raise OSError("Native POSIX directory custody is unavailable on Windows")


def _owner_uid() -> int:
    if sys.platform != "win32":
        return os.geteuid()
    raise OSError("Native POSIX owner identity is unavailable on Windows")


def _user_cache_directory() -> str | None:
    if sys.platform != "win32":
        return os.confstr(_CS_DARWIN_USER_CACHE_DIR)
    raise OSError("Native Darwin cache lookup is unavailable on Windows")


def _open_directory(path: Path) -> int:
    """Walk the canonical path with no-follow handles, never following a new alias."""
    descriptor = os.open(path.anchor, _directory_flags())
    try:
        for part in path.parts[1:]:
            child = os.open(part, _directory_flags(), dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
            metadata = os.fstat(descriptor)
            if metadata.st_uid not in (0, _owner_uid()) or (
                metadata.st_mode & 0o022 and not metadata.st_mode & stat.S_ISVTX
            ):
                raise PermissionError("Darwin transport ancestors must be trusted directories")
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _private_identity(descriptor: int) -> tuple[int, int]:
    metadata = os.fstat(descriptor)
    if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != _owner_uid() or stat.S_IMODE(metadata.st_mode) != 0o700:
        raise PermissionError("Darwin transport directory must be owned by the current user with mode 0700")
    return metadata.st_dev, metadata.st_ino


class _Namespace:
    def __init__(self, base: Path) -> None:
        self.base = base
        self.path = base / PRODUCT_IDENTITY.python_package
        self.base_fd = _open_directory(base)
        self.directory_fd: int | None = None
        self.lock = RLock()
        try:
            self.base_identity = _private_identity(self.base_fd)
        except BaseException:
            os.close(self.base_fd)
            raise

    def _verify_base(self) -> None:
        descriptor = _open_directory(self.base)
        try:
            if (
                _private_identity(descriptor) != self.base_identity
                or _private_identity(self.base_fd) != self.base_identity
            ):
                raise PermissionError("Darwin transport base was replaced")
        finally:
            os.close(descriptor)

    def verify(self, *, create: bool) -> Path:
        if sys.platform == "win32":
            raise OSError("Native POSIX directory custody is unavailable on Windows")
        with self.lock:
            self._verify_base()
            if create and self.directory_fd is None:
                with suppress(FileExistsError):
                    os.mkdir(PRODUCT_IDENTITY.python_package, mode=0o700, dir_fd=self.base_fd)
            try:
                descriptor = os.open(
                    PRODUCT_IDENTITY.python_package,
                    _directory_flags(),
                    dir_fd=self.base_fd,
                )
            except FileNotFoundError:
                if self.directory_fd is not None or create:
                    raise
                return self.path
            try:
                identity = _private_identity(descriptor)
                if self.directory_fd is None:
                    self.directory_fd = os.dup(descriptor)
                elif identity != _private_identity(self.directory_fd):
                    raise PermissionError("Darwin transport namespace was replaced")
            finally:
                os.close(descriptor)
            self._verify_base()
            return self.path


@cache
def _namespace() -> _Namespace:
    value = _user_cache_directory()
    if not value or not Path(value).is_absolute():
        raise OSError("Darwin user cache query returned no absolute directory")
    return _Namespace(Path(value).resolve(strict=True))


def darwin_socket_directory(*, create: bool = False) -> Path:
    """Resolve once, retain handles and refuse replacement; never use an ambient fallback."""
    with _RESOLUTION_LOCK:
        return _namespace().verify(create=create)
