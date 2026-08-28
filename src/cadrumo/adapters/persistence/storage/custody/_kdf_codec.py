"""Canonical codecs and framed transport for the supervised profile KDF."""

from __future__ import annotations

import base64
import ctypes
import os
import queue
import struct
from contextlib import suppress
from typing import Final, cast

from .....core.hashing import bounded_canonical_json_bytes, canonical_json_digest
from .errors import ProfileCustodyRefusal, ProfileCustodyRefusedError
from .records import ProfileCustodyKdfParameters

KDF_FRAME_MAGIC: Final = b"CKDF"
KDF_FRAME_VERSION: Final = 1
KDF_FRAME_CONTROL: Final = 1
KDF_FRAME_DEK: Final = 2
KDF_FRAME_HEADER: Final = struct.Struct("!4sBBHI")
_FRAME_MAX_BYTES: Final = 8 * 1024


def canonical_frame_bytes(payload: object) -> bytes:
    """Encode one supervised-KDF frame body under the canonical encoding."""
    return bounded_canonical_json_bytes(payload, maximum_bytes=_FRAME_MAX_BYTES, subject="profile KDF frame")


def canonical_frame_digest(payload: object) -> str:
    """Digest one supervised-KDF frame body under the canonical encoding."""
    return canonical_json_digest(payload, maximum_bytes=_FRAME_MAX_BYTES, subject="profile KDF frame")


def decode_canonical_b64(value: str, *, field_name: str, expected_bytes: int | None) -> bytes:
    try:
        decoded = base64.b64decode(value.encode("ascii"), validate=True)
    except (UnicodeEncodeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be canonical base64") from exc
    if expected_bytes is not None and len(decoded) != expected_bytes:
        raise ValueError(f"{field_name} has an invalid byte length")
    if expected_bytes is None and not decoded:
        raise ValueError(f"{field_name} must not be empty")
    if base64.b64encode(decoded).decode("ascii") != value:
        raise ValueError(f"{field_name} must be canonical base64")
    return decoded


def kdf_strength(parameters: ProfileCustodyKdfParameters) -> tuple[int, int, int]:
    return (parameters.memory_mib, parameters.iterations, parameters.parallelism)


def read_kdf_frame_to_queue(fd: int, result_queue: queue.Queue[tuple[int, bytes] | BaseException]) -> None:
    try:
        result_queue.put(read_kdf_frame(fd))
    except BaseException as exc:
        result_queue.put(exc)


def read_kdf_frame(fd: int) -> tuple[int, bytes]:
    header = _read_exact(fd, KDF_FRAME_HEADER.size)
    magic, version, kind, flags, length = KDF_FRAME_HEADER.unpack(header)
    if magic != KDF_FRAME_MAGIC or version != KDF_FRAME_VERSION or flags != 0:
        raise ValueError("profile KDF frame header is invalid")
    if kind not in {KDF_FRAME_CONTROL, KDF_FRAME_DEK}:
        raise ValueError("profile KDF frame kind is invalid")
    if length > _FRAME_MAX_BYTES:
        raise ValueError("profile KDF frame exceeds its bounded transport")
    return cast(int, kind), _read_exact(fd, length)


def write_kdf_frame(fd: int, value: bytes, *, kind: int) -> None:
    if len(value) > _FRAME_MAX_BYTES:
        raise ValueError("profile KDF frame exceeds its bounded transport")
    if kind not in {KDF_FRAME_CONTROL, KDF_FRAME_DEK}:
        raise ValueError("profile KDF frame kind is invalid")
    _write_all(fd, KDF_FRAME_HEADER.pack(KDF_FRAME_MAGIC, KDF_FRAME_VERSION, kind, 0, len(value)) + value)


def _read_exact(fd: int, length: int) -> bytes:
    chunks: list[bytes] = []
    remaining = length
    while remaining:
        chunk = os.read(fd, remaining)
        if not chunk:
            raise EOFError("profile KDF worker closed its pipe")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _write_all(fd: int, value: bytes) -> None:
    offset = 0
    while offset < len(value):
        offset += os.write(fd, value[offset:])


def close_fd(fd: int | None) -> None:
    if fd is None:
        return
    with suppress(OSError):
        os.close(fd)


def resource_refusal() -> ProfileCustodyRefusedError:
    return ProfileCustodyRefusedError(
        ProfileCustodyRefusal.KDF_RESOURCE_LIMIT,
        translated_message="errors.refused.refused_profile_custody_kdf_resource_limit",
    )


def supervision_refusal() -> ProfileCustodyRefusedError:
    return ProfileCustodyRefusedError(
        ProfileCustodyRefusal.KDF_SUPERVISION_UNAVAILABLE,
        translated_message="errors.refused.refused_profile_custody_kdf_supervision_unavailable",
    )


def windows_available_memory_bytes() -> int:
    class _MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = _MemoryStatus()
    status.dwLength = ctypes.sizeof(status)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    if not kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise OSError(ctypes.get_last_error(), "GlobalMemoryStatusEx failed")
    return int(status.ullAvailPhys)


__all__ = [
    "KDF_FRAME_CONTROL",
    "KDF_FRAME_DEK",
    "KDF_FRAME_HEADER",
    "KDF_FRAME_MAGIC",
    "KDF_FRAME_VERSION",
    "read_kdf_frame",
    "write_kdf_frame",
]
