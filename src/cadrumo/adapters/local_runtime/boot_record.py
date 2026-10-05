"""A supervised runtime's non-private boot record beside its installation identity.

The record names one runtime boot: boot id, pid, the native creation stamp of
that pid, product version, versioned package directory and admission policy.
A supervisor compares it with the live process before adopting a runtime. It
is an identity claim, never authority, and holds no other identifier or path.

It is written and read with the hardened custody local-record primitives:
anchored no-follow I/O, a byte bound, duplicate-member refusal and atomic
publication. Each supervised boot replaces it once its endpoint is owned, and a
clean exit removes exactly the bytes that boot published.
"""

from __future__ import annotations

import json
import os
import sys
from enum import StrEnum
from pathlib import Path
from threading import Lock
from typing import Annotated, Final, Literal
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError, field_validator

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.hashing import canonical_json_bytes, reject_duplicate_json_members, reject_json_constant
from ...core.logging import get_logger
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.storage_environment import StorageMode, storage_mode
from ...core.storage_taxonomy import StorageCategory
from ...core.storage_taxonomy_locations import storage_location
from ..persistence.storage.custody.errors import ProfileCustodyRecordError
from ..persistence.storage.custody.filesystem import (
    compare_and_clear_profile_custody_local_record,
    read_optional_profile_custody_local_record,
    write_profile_custody_local_record,
)
from ..persistence.storage.custody.filesystem_primitives import ensure_profile_custody_local_directory
from .linux_worker_process import linux_process_start_identity
from .login_policy import RuntimeAdmissionPolicy
from .macos_process import read_macos_process
from .posix import posix_owner_uid

_LOGGER = get_logger(__name__)

MAXIMUM_BOOT_RECORD_BYTES: Final = 8192
"""Upper bound of the encoded record, far above the largest valid record."""

_MAXIMUM_PACKAGE_DIRECTORY_CHARACTERS: Final = 1024
_MAXIMUM_PID: Final = 2**32 - 1
_MAXIMUM_CREATION_STAMP: Final = 2**64 - 1
_PACKAGE_MANIFEST: Final = ("data", "package-manifest.json")
"""The native package manifest, relative to the package root that holds the interpreter."""

_RECORD_FAILURES = (OSError, ProfileCustodyRecordError, ValueError, TypeError, RecursionError, ValidationError)


class RuntimeBootRecord(BaseModel):
    """One supervised runtime boot's identity claim; it grants no authority.

    ``process_created`` is the native creation stamp of ``pid``, so a reader
    compares it with the same native source: ``FILETIME`` ticks from
    ``GetProcessTimes`` on Windows, ``/proc/<pid>/stat`` start ticks since boot
    on Linux, and microseconds since the epoch from ``proc_pidinfo`` on macOS.
    ``package_directory`` is the absolute versioned native package root, or
    ``None`` in a source checkout and outside a native package.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    schema_version: Literal[1] = 1
    boot_id: UUID
    pid: Annotated[int, Field(gt=0, le=_MAXIMUM_PID)]
    process_created: Annotated[int, Field(gt=0, le=_MAXIMUM_CREATION_STAMP)]
    version: Annotated[str, Field(min_length=1, max_length=64)]
    package_directory: Annotated[str, Field(min_length=1, max_length=_MAXIMUM_PACKAGE_DIRECTORY_CHARACTERS)] | None
    admission: RuntimeAdmissionPolicy

    @field_validator("package_directory")
    @classmethod
    def _package_directory_is_absolute(cls, value: str | None) -> str | None:
        if value is not None and not Path(value).is_absolute():
            raise ValueError("a package directory must be absolute")
        return value


class RuntimeBootRecordUnavailable(StrEnum):
    """Why no boot record could be read."""

    ABSENT = "absent"
    UNREADABLE = "unreadable"


def runtime_boot_record_path(storage_root: Path) -> Path:
    """Return the boot record location under an absolute storage root."""
    if not storage_root.is_absolute():
        raise RuntimeRefusalError(RuntimeRefusalCode.ROOT_MISMATCH)
    return storage_root / storage_location(StorageCategory.RUNTIME_BOOT_RECORD).relative_path()


def encode_runtime_boot_record(record: RuntimeBootRecord) -> bytes:
    """Return the canonical bounded bytes of ``record``."""
    payload = canonical_json_bytes(record.model_dump(mode="json"))
    if len(payload) > MAXIMUM_BOOT_RECORD_BYTES:
        raise ValueError("a runtime boot record exceeds its byte bound")
    return payload


def decode_runtime_boot_record(raw: bytes) -> RuntimeBootRecord:
    """Parse record bytes strictly: one object, no repeated or unknown member, no non-finite constant."""
    if len(raw) > MAXIMUM_BOOT_RECORD_BYTES:
        raise ValueError("a runtime boot record exceeds its byte bound")
    parsed: object = json.loads(
        raw, object_pairs_hook=reject_duplicate_json_members, parse_constant=reject_json_constant
    )
    return RuntimeBootRecord.model_validate_json(canonical_json_bytes(parsed))


def read_runtime_boot_record(*, storage_root: Path) -> RuntimeBootRecord | RuntimeBootRecordUnavailable:
    """Read the published boot record without creating anything.

    A missing ``.runtime`` directory or record is absent. Any other failure,
    including a substituted leaf, an oversized or malformed record, is
    unreadable rather than absent.
    """
    path = runtime_boot_record_path(storage_root)
    if not os.path.lexists(path.parent):
        return RuntimeBootRecordUnavailable.ABSENT
    try:
        raw = read_optional_profile_custody_local_record(path, maximum_bytes=MAXIMUM_BOOT_RECORD_BYTES)
        if raw is None:
            return RuntimeBootRecordUnavailable.ABSENT
        return decode_runtime_boot_record(raw)
    except _RECORD_FAILURES:
        return RuntimeBootRecordUnavailable.UNREADABLE


def runtime_package_directory(interpreter: Path, *, mode: StorageMode) -> str | None:
    """Return the versioned native package root that holds ``interpreter``.

    A source checkout has none. An installed tree has one only when the
    interpreter's directory carries the native package manifest; a wheel
    installation into an ordinary Python environment is not a versioned package.
    """
    if mode is StorageMode.DEVELOPMENT or not interpreter.is_absolute():
        return None
    root = interpreter.parent
    return str(root) if root.joinpath(*_PACKAGE_MANIFEST).is_file() else None


def current_runtime_boot_record(*, boot_id: UUID, version: str, admission: RuntimeAdmissionPolicy) -> RuntimeBootRecord:
    """Describe this process as the runtime of boot ``boot_id``."""
    pid = os.getpid()
    return RuntimeBootRecord(
        boot_id=boot_id,
        pid=pid,
        process_created=_process_created(pid),
        version=version,
        package_directory=runtime_package_directory(Path(sys.executable), mode=storage_mode().mode),
        admission=admission,
    )


def _process_created(pid: int) -> int:
    if sys.platform == "win32":
        return _windows_current_process_created()
    if sys.platform == "linux":
        return int(linux_process_start_identity(pid))
    if sys.platform == "darwin":
        observed = read_macos_process(pid, expected_owner=str(posix_owner_uid()))
        return observed.started_seconds * 1_000_000 + observed.started_microseconds
    raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)


def _windows_current_process_created() -> int:
    if sys.platform != "win32":
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    current = kernel.GetCurrentProcess
    current.argtypes = ()
    current.restype = wintypes.HANDLE
    times = kernel.GetProcessTimes
    filetime = ctypes.POINTER(wintypes.FILETIME)
    times.argtypes = (wintypes.HANDLE, filetime, filetime, filetime, filetime)
    times.restype = wintypes.BOOL
    created, exited, kernel_time, user_time = (wintypes.FILETIME() for _ in range(4))
    # Invariants: GetCurrentProcess returns a pseudo-handle that is valid for
    # this process's whole lifetime and is never closed. GetProcessTimes writes
    # only into the four FILETIME locals, which outlive the call.
    if not times(
        current(),
        ctypes.byref(created),
        ctypes.byref(exited),
        ctypes.byref(kernel_time),
        ctypes.byref(user_time),
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    return (int(created.dwHighDateTime) << 32) | int(created.dwLowDateTime)


class RuntimeBootRecordPublication:
    """Publish one boot's record once and remove only that record again.

    Endpoint ownership admits one publishing runtime per storage root, so
    publication replaces any record an earlier boot left. Removal compares the
    exact published bytes, so a successor's record is never removed.
    """

    def __init__(self, *, storage_root: Path, record: RuntimeBootRecord) -> None:
        """Bind the record location and its canonical bytes; nothing is written yet."""
        self._storage_root = storage_root
        self._path = runtime_boot_record_path(storage_root)
        self._payload = encode_runtime_boot_record(record)
        self._guard = Lock()
        self._published = False
        self._withdrawn = False

    def publish(self) -> bool:
        """Replace any earlier record with this boot's; return False once withdrawn.

        Call only while this runtime owns its endpoint.
        """
        with self._guard:
            if self._withdrawn:
                return False
            if read_runtime_boot_record(storage_root=self._storage_root) is not RuntimeBootRecordUnavailable.ABSENT:
                _LOGGER.info("runtime boot record replaces one an earlier boot left")
            try:
                ensure_profile_custody_local_directory(self._path.parent)
                write_profile_custody_local_record(self._path, self._payload, publish_once=False)
            except (OSError, ProfileCustodyRecordError):
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE) from None
            self._published = True
            return True

    def withdraw(self) -> None:
        """Remove this boot's record if it is still the published one; later publication is refused."""
        with self._guard:
            self._withdrawn = True
            if not self._published:
                return
            self._published = False
            try:
                current = read_optional_profile_custody_local_record(
                    self._path, maximum_bytes=MAXIMUM_BOOT_RECORD_BYTES
                )
                if current != self._payload:
                    return
                compare_and_clear_profile_custody_local_record(
                    self._path, expected=self._payload, maximum_bytes=MAXIMUM_BOOT_RECORD_BYTES
                )
            except (OSError, ProfileCustodyRecordError):
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE) from None
