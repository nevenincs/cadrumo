"""Readiness attestation shared by the parent and child KDF processes."""

from __future__ import annotations

import json
import os
import sys
from typing import Any, cast

from ._kdf_codec import KDF_TRANSPORT_ENCODING
from ._kdf_codec import canonical_frame_bytes as _canonical_frame_bytes
from ._kdf_worker_limits import (
    PROFILE_CUSTODY_KDF_WORKER_CPU_SECONDS,
    PROFILE_CUSTODY_KDF_WORKER_MAX_PROCESSES,
    PROFILE_CUSTODY_KDF_WORKER_MEMORY_BYTES,
)


def kdf_worker_platform() -> str:
    """Name the ready-attestation contract this host's KDF worker can prove.

    Darwin rejects any finite address-space limit, so its worker proves the
    remaining hard limits; the closed Argon2 grid, validated before allocation,
    bounds its memory instead. Each contract only ever verifies on its own host.
    """
    if sys.platform == "win32":
        return "win32"
    if sys.platform == "darwin":
        return "darwin"
    return "posix"


def kdf_worker_ready_attestation(*, request_fd: int, result_fd: int) -> bytes:
    """Build a child attestation of the limits it can observe before secrets arrive."""
    platform = kdf_worker_platform()
    limits = expected_kdf_worker_limits(platform)
    if platform != "win32":
        import resource

        resource_module = cast(Any, resource)
        observed = {
            "cpu_seconds": resource_module.getrlimit(resource_module.RLIMIT_CPU)[0],
            "max_open_files": resource_module.getrlimit(resource_module.RLIMIT_NOFILE)[0],
        }
        if platform == "posix":
            observed["memory_bytes"] = resource_module.getrlimit(resource_module.RLIMIT_AS)[0]
        if observed != {name: value for name, value in limits.items() if name != "max_processes"}:
            raise ValueError("profile KDF worker limits are not active")
    payload: dict[str, object] = {
        "cwd": os.getcwd(),
        "environment_keys": sorted(os.environ),
        "limits": limits,
        "platform": platform,
        "protocol": "profile-kdf-ready/v1",
        "transport": "framed-anonymous-pipe/v1",
    }
    if platform != "win32":
        payload["open_file_descriptors"] = _open_posix_file_descriptors(
            authorized=(request_fd, result_fd),
        )
    return _canonical_frame_bytes(payload)


def _open_posix_file_descriptors(*, authorized: tuple[int, int]) -> list[int]:
    candidates = {*(range(16)), *authorized}
    return [descriptor for descriptor in sorted(candidates) if _is_open_file_descriptor(descriptor)]


def _is_open_file_descriptor(descriptor: int) -> bool:
    try:
        os.fstat(descriptor)
    except OSError:
        return False
    return True


def expected_kdf_worker_limits(platform: str) -> dict[str, int]:
    limits: dict[str, int] = {
        "cpu_seconds": PROFILE_CUSTODY_KDF_WORKER_CPU_SECONDS,
        "max_processes": PROFILE_CUSTODY_KDF_WORKER_MAX_PROCESSES,
    }
    if platform != "darwin":
        limits["memory_bytes"] = PROFILE_CUSTODY_KDF_WORKER_MEMORY_BYTES
    if platform != "win32":
        limits["max_open_files"] = 16
    return limits


def parse_ready_attestation(value: bytes) -> dict[str, object]:
    parsed = json.loads(value.decode(KDF_TRANSPORT_ENCODING, errors="strict"))
    if not isinstance(parsed, dict):
        raise ValueError("profile KDF ready payload is invalid")
    return cast("dict[str, object]", parsed)


def validate_ready_attestation_shape(payload: dict[str, object], expected_platform: str) -> None:
    expected_fields = {"cwd", "environment_keys", "limits", "platform", "protocol", "transport"}
    if expected_platform != "win32":
        expected_fields.add("open_file_descriptors")
    if set(payload) != expected_fields:
        raise ValueError("profile KDF ready fields are invalid")
    if (
        payload["platform"] != expected_platform
        or payload["protocol"] != "profile-kdf-ready/v1"
        or payload["transport"] != "framed-anonymous-pipe/v1"
        or payload["limits"] != expected_kdf_worker_limits(expected_platform)
    ):
        raise ValueError("profile KDF ready attestation is invalid")


__all__ = [
    "expected_kdf_worker_limits",
    "kdf_worker_platform",
    "kdf_worker_ready_attestation",
    "parse_ready_attestation",
    "validate_ready_attestation_shape",
]
