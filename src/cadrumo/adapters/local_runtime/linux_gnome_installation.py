"""Explicit, non-activating per-user GNOME login producer installation.

Only the current packaged cohort is accepted. Both files are prepared privately
and published together with native no-replace directory rename. A native failure
can leave the exact published directory; no rollback or compositor acceptance is
implied. Abandoned staging directories require explicit operator reconciliation.
"""

from __future__ import annotations

import ctypes
import errno
import os
import stat
import sys
from collections.abc import Callable, Generator
from contextlib import ExitStack, contextmanager
from importlib.resources import files
from typing import cast
from uuid import uuid4

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.storage_taxonomy import StorageCategory
from ...core.storage_taxonomy_locations import storage_path
from .linux_gnome_lock import GNOME_LOGIN_EXTENSION_UUID

_FILES = ("extension.js", "metadata.json")
_STAGING_PREFIX = "." + GNOME_LOGIN_EXTENSION_UUID + ".stage-"
_MAX_BYTES = 65536


def _refusal(reason: RuntimeRefusalCode = RuntimeRefusalCode.UNAVAILABLE) -> RuntimeRefusalError:
    return RuntimeRefusalError(reason)


def _directory_flags() -> int:
    if sys.platform != "linux":
        raise _refusal()
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


@contextmanager
def _extensions_directory(*, create: bool) -> Generator[int]:
    if sys.platform != "linux":
        raise _refusal()
    uid = os.getuid()
    target = storage_path(StorageCategory.GNOME_EXTENSIONS)
    if not target.is_absolute() or ".." in target.parts:
        raise _refusal(RuntimeRefusalCode.PEER_UNTRUSTED)
    descriptor = os.open("/", _directory_flags())
    try:
        for part in target.parts[1:]:
            try:
                child = os.open(part, _directory_flags(), dir_fd=descriptor)
            except FileNotFoundError:
                if not create:
                    raise
                os.mkdir(part, mode=0o700, dir_fd=descriptor)
                os.fsync(descriptor)
                child = os.open(part, _directory_flags(), dir_fd=descriptor)
            observed = os.fstat(child)
            if (
                observed.st_uid not in (0, uid)
                or observed.st_mode & 0o022
            ):
                os.close(child)
                raise _refusal(RuntimeRefusalCode.PEER_UNTRUSTED)
            os.close(descriptor)
            descriptor = child
        yield descriptor
    finally:
        os.close(descriptor)


def _packaged_files() -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    for name in _FILES:
        payload = files("cadrumo").joinpath("_data/local_runtime/gnome_login", name).read_bytes()
        if not 0 < len(payload) <= _MAX_BYTES:
            raise _refusal()
        result[name] = payload
    return result


def _identity(observed: os.stat_result) -> tuple[int, ...]:
    return (
        observed.st_dev,
        observed.st_ino,
        observed.st_mode,
        observed.st_uid,
        observed.st_gid,
        observed.st_nlink,
        observed.st_size,
        observed.st_mtime_ns,
        observed.st_ctime_ns,
    )


def _require_private_directory(descriptor: int) -> None:
    if sys.platform != "linux":
        raise _refusal()
    observed = os.fstat(descriptor)
    if not stat.S_ISDIR(observed.st_mode) or observed.st_uid != os.getuid() or stat.S_IMODE(observed.st_mode) != 0o700:
        raise _refusal(RuntimeRefusalCode.PEER_UNTRUSTED)


def _require_exact_files(directory: int, expected: dict[str, bytes]) -> None:
    if sys.platform != "linux":
        raise _refusal()
    _require_private_directory(directory)

    present = _directory_entries(directory)
    if present != set(_FILES):
        raise _refusal()
    for name in _FILES:
        _require_exact_file(directory, name, expected[name])
    _require_private_directory(directory)


def _directory_entries(directory: int) -> set[str]:
    present: set[str] = set()
    with os.scandir(directory) as entries:
        for entry in entries:
            if entry.name not in _FILES:
                raise _refusal()
            present.add(entry.name)
    return present


def _require_exact_file(directory: int, name: str, expected: bytes) -> None:
    descriptor = os.open(name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory)
    try:
        observed = os.fstat(descriptor)
        if (
            not stat.S_ISREG(observed.st_mode)
            or observed.st_uid != os.getuid()
            or stat.S_IMODE(observed.st_mode) != 0o600
            or observed.st_nlink != 1
            or not 0 < observed.st_size <= _MAX_BYTES
        ):
            raise _refusal(RuntimeRefusalCode.PEER_UNTRUSTED)
        with os.fdopen(os.dup(descriptor), "rb") as source:
            actual = source.read(_MAX_BYTES + 1)
        if actual != expected or _identity(os.fstat(descriptor)) != _identity(observed):
            raise _refusal(RuntimeRefusalCode.VERSION_MISMATCH)
    finally:
        os.close(descriptor)


def _require_no_staging(parent: int) -> None:
    with os.scandir(parent) as entries:
        for index, entry in enumerate(entries):
            if index >= 4096 or entry.name.startswith(_STAGING_PREFIX):
                raise _refusal()


def _inspect(parent: int, expected: dict[str, bytes]) -> bool:
    _require_no_staging(parent)
    try:
        directory = os.open(GNOME_LOGIN_EXTENSION_UUID, _directory_flags(), dir_fd=parent)
    except FileNotFoundError:
        return False
    try:
        before = os.fstat(directory)
        _require_exact_files(directory, expected)
        current = os.stat(GNOME_LOGIN_EXTENSION_UUID, dir_fd=parent, follow_symlinks=False)
        if _identity(current) != _identity(before):
            raise _refusal()
        return True
    finally:
        os.close(directory)


def _check_parent_binding(parent: int) -> None:
    with _extensions_directory(create=False) as current:
        before, after = os.fstat(parent), os.fstat(current)
        if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
            raise _refusal(RuntimeRefusalCode.PEER_UNTRUSTED)


def _native_publish_directory(parent: int, staging: str) -> None:
    if sys.platform != "linux":
        raise _refusal()
    library = ctypes.CDLL("libc.so.6", use_errno=True)
    native = library.renameat2
    native.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    native.restype = ctypes.c_int
    rename = cast(Callable[[int, bytes, int, bytes, int], int], native)
    result = rename(parent, staging.encode("ascii"), parent, GNOME_LOGIN_EXTENSION_UUID.encode("ascii"), 1)
    if result != 0:
        if ctypes.get_errno() == errno.EEXIST:
            raise _refusal(RuntimeRefusalCode.VERSION_MISMATCH)
        raise _refusal()


class _StagedProducer:
    """Own only this invocation's staging directory and exclusively created files."""

    def __init__(self, parent: int) -> None:
        self.parent = parent
        self.name = _STAGING_PREFIX + uuid4().hex
        self.directory: int | None = None
        self.observed: os.stat_result | None = None
        self.created: dict[str, tuple[int, int]] = {}
        self.published = False

    def __enter__(self) -> _StagedProducer:
        os.mkdir(self.name, mode=0o700, dir_fd=self.parent)
        try:
            self.directory = os.open(self.name, _directory_flags(), dir_fd=self.parent)
            self.observed = os.fstat(self.directory)
            _require_private_directory(self.directory)
            return self
        except BaseException:
            self.close()
            raise

    def write(self, name: str, payload: bytes) -> None:
        """Prepare one complete file before any producer becomes visible."""
        if sys.platform != "linux" or self.directory is None:
            raise _refusal()
        descriptor = os.open(
            name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=self.directory
        )
        try:
            observed = os.fstat(descriptor)
            self.created[name] = (observed.st_dev, observed.st_ino)
            with os.fdopen(os.dup(descriptor), "wb") as destination:
                destination.write(payload)
                destination.flush()
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def publish(self, expected: dict[str, bytes]) -> None:
        """Publish both files as one no-clobber directory operation."""
        if self.directory is None or self.observed is None:
            raise _refusal()
        _require_exact_files(self.directory, expected)
        os.fsync(self.directory)
        _check_parent_binding(self.parent)
        source = os.stat(self.name, dir_fd=self.parent, follow_symlinks=False)
        if (source.st_dev, source.st_ino) != (self.observed.st_dev, self.observed.st_ino):
            raise _refusal()
        _native_publish_directory(self.parent, self.name)
        self.published = True
        os.fsync(self.parent)
        target = os.stat(GNOME_LOGIN_EXTENSION_UUID, dir_fd=self.parent, follow_symlinks=False)
        if (target.st_dev, target.st_ino) != (self.observed.st_dev, self.observed.st_ino):
            raise _refusal()

    def close(self) -> None:
        """Remove only the owned unpublished stage, retaining cleanup failures."""
        try:
            if not self.published and self.directory is not None and self.observed is not None:
                try:
                    current = os.stat(self.name, dir_fd=self.parent, follow_symlinks=False)
                except FileNotFoundError:
                    return  # A native failure may have completed publication.
                if (current.st_dev, current.st_ino) != (self.observed.st_dev, self.observed.st_ino):
                    raise _refusal()
                for name, identity in self.created.items():
                    current = os.stat(name, dir_fd=self.directory, follow_symlinks=False)
                    if (current.st_dev, current.st_ino) != identity:
                        raise _refusal()
                    os.unlink(name, dir_fd=self.directory)
                os.rmdir(self.name, dir_fd=self.parent)
                os.fsync(self.parent)
        finally:
            if self.directory is not None:
                os.close(self.directory)
                self.directory = None

    def __exit__(self, *_: object) -> None:
        self.close()


def inspect_gnome_login_producer() -> bool:
    """Return absence or exact current files; unsafe/partial installation refuses."""
    try:
        expected = _packaged_files()
        with ExitStack() as owned:
            try:
                parent = owned.enter_context(_extensions_directory(create=False))
            except FileNotFoundError:
                return False
            result = _inspect(parent, expected)
            _check_parent_binding(parent)
            return result
    except (OSError, AttributeError, ValueError):
        raise _refusal() from None


def install_gnome_login_producer() -> bool:
    """Create the current producer once, or return False for already-exact files.

    No Shell extension is enabled, disabled, reloaded or otherwise activated.
    Existing foreign or previous-cohort files are never replaced.
    """
    try:
        expected = _packaged_files()
        with _extensions_directory(create=True) as parent:
            if _inspect(parent, expected):
                _check_parent_binding(parent)
                return False
            with _StagedProducer(parent) as staged:
                for name, payload in expected.items():
                    staged.write(name, payload)
                staged.publish(expected)
            if not _inspect(parent, expected):
                raise _refusal()
            _check_parent_binding(parent)
            return True
    except (OSError, AttributeError, ValueError):
        raise _refusal() from None
