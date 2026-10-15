"""Strict current-only record for the active-profile pointer.

The pointer is one durable, plaintext coordination record under the storage
root. It names either a selected bucket or an explicit absence and carries the
monotonic transition coordinate used by every pointer consumer. The record is
not a profile manifest or a profile-lifecycle assertion: it only records the
currently selected bucket.
"""

from __future__ import annotations

import os
import stat
import sys
import time
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal

from pydantic import BaseModel, Field, ValidationError, model_validator

from .errors.hierarchy import ActiveProfilePointerError, pydantic_validation_boundary
from .identity.bucket import BucketId
from .models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .toml import TomlDecodeError, parse_toml

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Callable

    from .errors.hierarchy import CadrumoError

if sys.platform == "win32":
    import ctypes
    import msvcrt
    from ctypes import wintypes

POINTER_SCHEMA_VERSION: Final[Literal[2]] = 2


class BucketPointer(BaseModel):
    """One strict active-profile selection and its durable transition revision.

    ``selection`` is deliberately explicit because TOML has no null scalar.
    A selected record carries exactly one bucket id; an absent record is the
    persisted tombstone written by clear. The physically absent initial file
    observes as an absent record at revision zero and is never accepted as an
    on-disk compatibility format.
    """

    model_config = _STRICT_FROZEN

    selection: Literal["absent", "selected"]
    bucket_id: BucketId | None = None
    transition_revision: int = Field(ge=0)
    schema_version: Literal[2]

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_selection(self) -> BucketPointer:
        if (self.selection == "selected") != (self.bucket_id is not None):
            raise ValueError("pointer selection and bucket id must agree")
        return self

    @classmethod
    def absent(cls, *, transition_revision: int) -> BucketPointer:
        """Construct the explicit absent-selection tombstone."""
        return cls(
            selection="absent",
            bucket_id=None,
            transition_revision=transition_revision,
            schema_version=POINTER_SCHEMA_VERSION,
        )

    @classmethod
    def selected(cls, *, bucket_id: str, transition_revision: int) -> BucketPointer:
        """Construct one selected current-format record."""
        return cls(
            selection="selected",
            bucket_id=bucket_id,
            transition_revision=transition_revision,
            schema_version=POINTER_SCHEMA_VERSION,
        )

    def to_toml(self) -> str:
        """Return the deterministic strict current-format TOML payload."""
        lines = [f'selection = "{self.selection}"']
        if self.bucket_id is not None:
            bucket_id_escaped = self.bucket_id.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'bucket_id = "{bucket_id_escaped}"')
        lines.extend(
            (
                f"transition_revision = {self.transition_revision}",
                f"schema_version = {self.schema_version}",
            )
        )
        return "\n".join(lines) + "\n"

    @classmethod
    def from_toml(cls, text: str) -> BucketPointer:
        """Strictly parse a current-format pointer record."""
        return cls.model_validate(parse_toml(text))


def pointer_path(root: Path) -> Path:
    """Return the active-profile record path beneath ``root``."""
    from .storage_taxonomy import StorageCategory
    from .storage_taxonomy_locations import storage_location

    return root / storage_location(StorageCategory.ACTIVE_PROFILE_POINTER).relative_path()


if sys.platform == "win32":

    def _open_windows_pointer_descriptor(target: Path) -> int:
        """Open the pointer without blocking replacement of its directory entry."""
        handle = _WINDOWS_CREATE_FILE(
            str(target),
            _WINDOWS_GENERIC_READ,
            _WINDOWS_FILE_SHARE_ALL,
            None,
            _WINDOWS_OPEN_EXISTING,
            _WINDOWS_FILE_FLAG_OPEN_REPARSE_POINT,
            None,
        )
        handle_value = getattr(handle, "value", handle)
        if handle_value is None or handle_value == _WINDOWS_INVALID_HANDLE:
            raise ctypes.WinError(ctypes.get_last_error())

        descriptor: int | None = None
        handle_owned_by_descriptor = False
        try:
            attributes = _WindowsFileAttributeTagInfo()
            if not _WINDOWS_GET_FILE_INFORMATION_BY_HANDLE_EX(
                handle_value,
                _WINDOWS_FILE_ATTRIBUTE_TAG_INFO,
                ctypes.byref(attributes),
                ctypes.sizeof(attributes),
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            if attributes.file_attributes & _WINDOWS_FILE_ATTRIBUTE_REPARSE_POINT:
                raise OSError("active-profile pointer must not be link-like")

            descriptor = msvcrt.open_osfhandle(handle_value, os.O_RDONLY | os.O_BINARY)
            handle_owned_by_descriptor = True
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise OSError("active-profile pointer must be a bounded regular file")
            result = descriptor
            descriptor = None
            return result
        finally:
            if descriptor is not None:
                os.close(descriptor)
            elif not handle_owned_by_descriptor:
                _WINDOWS_CLOSE_HANDLE(handle_value)


_POINTER_READ_RETRY_SECONDS = 1.0
_POINTER_READ_POLL_SECONDS = 0.02
_POINTER_READ_MAX_WAIT_SECONDS = 15.0
_POINTER_WRITE_RETRY_SECONDS = 1.0
_POINTER_MAXIMUM_BYTES = 1024

if sys.platform == "win32":
    _WINDOWS_GENERIC_READ: Final = 0x80000000
    _WINDOWS_FILE_SHARE_ALL: Final = 0x00000007
    _WINDOWS_OPEN_EXISTING: Final = 3
    _WINDOWS_FILE_FLAG_OPEN_REPARSE_POINT: Final = 0x00200000
    _WINDOWS_FILE_ATTRIBUTE_TAG_INFO: Final = 9
    _WINDOWS_FILE_ATTRIBUTE_REPARSE_POINT: Final = 0x00000400
    _WINDOWS_INVALID_HANDLE: Final = ctypes.c_void_p(-1).value

    class _WindowsFileAttributeTagInfo(ctypes.Structure):
        _fields_ = [("file_attributes", wintypes.DWORD), ("reparse_tag", wintypes.DWORD)]

    _WINDOWS_KERNEL32: Final = ctypes.WinDLL("kernel32", use_last_error=True)
    _WINDOWS_CREATE_FILE = _WINDOWS_KERNEL32.CreateFileW
    _WINDOWS_CREATE_FILE.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    _WINDOWS_CREATE_FILE.restype = wintypes.HANDLE
    _WINDOWS_GET_FILE_INFORMATION_BY_HANDLE_EX = _WINDOWS_KERNEL32.GetFileInformationByHandleEx
    _WINDOWS_GET_FILE_INFORMATION_BY_HANDLE_EX.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    _WINDOWS_GET_FILE_INFORMATION_BY_HANDLE_EX.restype = wintypes.BOOL
    _WINDOWS_CLOSE_HANDLE = _WINDOWS_KERNEL32.CloseHandle
    _WINDOWS_CLOSE_HANDLE.argtypes = [wintypes.HANDLE]
    _WINDOWS_CLOSE_HANDLE.restype = wintypes.BOOL


#: A missing record, or a path whose ancestor is a file so no record can be
#: there. Windows reports both as a missing file and POSIX reports the second
#: as ``ENOTDIR``; either way nothing was ever written, so it is the cold start.
_NO_RECORD_AT_PATH = (FileNotFoundError, NotADirectoryError)


def _pointer_entry_signature(target: Path) -> tuple[str, int, int] | None:
    from .paths import path_stat_fingerprint

    try:
        return path_stat_fingerprint(target)
    except OSError:
        return None


def _open_pointer_descriptor(target: Path) -> int:
    from .link_safety import is_link_like

    if is_link_like(target):
        raise OSError("active-profile pointer must not be link-like")
    if sys.platform == "win32":
        return _open_windows_pointer_descriptor(target)
    return os.open(target, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))


def _read_bounded_pointer_descriptor(descriptor: int) -> bytes:
    metadata = os.fstat(descriptor)
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > _POINTER_MAXIMUM_BYTES:
        raise OSError("active-profile pointer must be a bounded regular file")
    payload = os.read(descriptor, _POINTER_MAXIMUM_BYTES + 1)
    if len(payload) != metadata.st_size or len(payload) > _POINTER_MAXIMUM_BYTES:
        raise OSError("active-profile pointer changed during read")
    return payload


def _read_pointer_once(target: Path) -> bytes:
    descriptor = _open_pointer_descriptor(target)
    try:
        return _read_bounded_pointer_descriptor(descriptor)
    finally:
        os.close(descriptor)


def _read_pointer_bytes_without_contention(target: Path) -> bytes | None:
    try:
        return _read_pointer_once(target)
    except _NO_RECORD_AT_PATH:
        return None


def _read_pointer_bytes_with_windows_contention(target: Path) -> bytes | None:
    from .windows_contention import is_windows_contention

    started = time.monotonic()
    deadline = started + _POINTER_READ_RETRY_SECONDS
    ceiling = started + _POINTER_READ_MAX_WAIT_SECONDS
    signature = _pointer_entry_signature(target)
    while True:
        try:
            return _read_pointer_once(target)
        except _NO_RECORD_AT_PATH:
            return None
        except PermissionError as exc:
            now = time.monotonic()
            current = _pointer_entry_signature(target)
            if current != signature:
                signature = current
                deadline = now + _POINTER_READ_RETRY_SECONDS
            transient_windows_refusal = sys.platform == "win32" and (
                is_windows_contention(exc) or getattr(exc, "winerror", None) is None
            )
            if not transient_windows_refusal or now >= deadline or now >= ceiling:
                raise
            time.sleep(_POINTER_READ_POLL_SECONDS)


def _read_pointer_bytes(target: Path) -> bytes | None:
    """Read one complete record, waiting out a Windows replacement race."""
    if sys.platform == "win32":
        return _read_pointer_bytes_with_windows_contention(target)
    return _read_pointer_bytes_without_contention(target)


def read_pointer(root: Path) -> BucketPointer:
    """Observe the optional selection and durable current coordinate once.

    A missing record is the clean cold start. A present record whose bytes do
    not decode, whose text does not parse, or whose shape does not validate is
    stored-metadata corruption, refused here as the typed pointer error so no
    caller ever sees a raw decoding or validation failure.

    Raises:
        ActiveProfilePointerError: The present record is not a valid pointer.
    """
    target = pointer_path(root)
    raw = _read_pointer_bytes(target)
    if raw is None:
        return BucketPointer.absent(transition_revision=0)
    try:
        return BucketPointer.from_toml(raw.decode("utf-8"))
    except (UnicodeDecodeError, TomlDecodeError, ValidationError) as exc:
        raise ActiveProfilePointerError(path=target) from exc


_CORRUPT_POINTER_READS_AS_UNSELECTED: ContextVar[bool] = ContextVar(
    "corrupt_pointer_reads_as_unselected", default=False
)


@contextmanager
def corrupt_pointer_reads_as_unselected() -> Generator[None]:
    """Read a corrupt pointer as selecting no profile, for the command that repairs it.

    Settings composition and every "which profile is selected" read go through
    the pointer, so a corrupt record makes every command unrunnable, including
    the one that repairs it. Inside this scope those selection reads observe a
    corrupt record as no selection, so the repair runs profile-free. Nothing
    else is relaxed: :func:`read_pointer` and every pointer transition still
    refuse the corrupt record, so the repair still sees exactly what it is
    repairing.
    """
    token = _CORRUPT_POINTER_READS_AS_UNSELECTED.set(True)
    try:
        yield
    finally:
        _CORRUPT_POINTER_READS_AS_UNSELECTED.reset(token)


def read_pointer_selection(root: Path) -> BucketPointer:
    """Observe the pointer for settings composition and profile selection.

    Raises:
        ActiveProfilePointerError: The present record is not a valid pointer and
            no :func:`corrupt_pointer_reads_as_unselected` scope is active.
    """
    try:
        return read_pointer(root)
    except ActiveProfilePointerError:
        if not _CORRUPT_POINTER_READS_AS_UNSELECTED.get():
            raise
        return BucketPointer.absent(transition_revision=0)


def _await_uncontended(operation: Callable[[], None]) -> None:
    """Retry a bounded Windows sharing refusal without masking permanent failures."""
    from .windows_contention import is_windows_contention

    deadline = time.monotonic() + _POINTER_WRITE_RETRY_SECONDS
    while True:
        try:
            operation()
        except PermissionError as exc:
            # Windows can surface a sharing refusal from ``os.open`` without a
            # populated ``winerror``. A bounded retry is safe for every
            # Windows PermissionError: an ACL or directory refusal remains a
            # refusal once the short contention window expires, while a peer's
            # reader handle releases and permits the atomic publication.
            transient_windows_refusal = sys.platform == "win32" and (
                is_windows_contention(exc) or getattr(exc, "winerror", None) is None
            )
            if not transient_windows_refusal or time.monotonic() >= deadline:
                raise
            time.sleep(_POINTER_READ_POLL_SECONDS)
            continue
        return


def write_pointer(root: Path, pointer: BucketPointer) -> None:
    """Atomically replace the one strict pointer record under its owner lock."""
    from .atomic_write import hardened_staged_bytes_publication

    target = pointer_path(root)
    with hardened_staged_bytes_publication(target, pointer.to_toml().encode("utf-8")) as staged:
        _await_uncontended(staged.publish_with_open_readers)


def resolve_active_bucket_id() -> str | None:
    """Resolve a process override or one current persisted selection."""
    from .config import load_settings

    settings = load_settings()
    override = (settings.cadrumo_active_profile or "").strip()
    if override:
        return override
    return read_pointer_selection(settings.cadrumo_local_storage_root).bucket_id


def require_active_bucket_id() -> str:
    """Return the selected bucket or raise the canonical no-profile refusal."""
    from .errors.hierarchy import NoActiveProfileError

    bucket_id = resolve_active_bucket_id()
    if bucket_id is None:
        raise NoActiveProfileError(translated_message="application.workflow.errors.no_active_profile_bucket")
    return bucket_id


def resolve_repository_bucket_id(bucket_id: str | None, *, error_type: type[CadrumoError]) -> str:
    """Resolve an explicit bucket or the current pointer selection."""
    if bucket_id is not None:
        trimmed = bucket_id.strip()
        if trimmed:
            return trimmed
        raise error_type(
            translated_message="application.workflow.errors.no_active_profile_bucket",
            context={"reason": "blank_explicit_bucket_id"},
        )
    active = resolve_active_bucket_id()
    if active is None:
        raise error_type(
            translated_message="application.workflow.errors.no_active_profile_bucket",
            context={"reason": "missing_active_profile_bucket"},
        )
    return active


__all__ = [
    "POINTER_SCHEMA_VERSION",
    "BucketPointer",
    "corrupt_pointer_reads_as_unselected",
    "pointer_path",
    "read_pointer",
    "read_pointer_selection",
    "require_active_bucket_id",
    "resolve_active_bucket_id",
    "resolve_repository_bucket_id",
    "write_pointer",
]
