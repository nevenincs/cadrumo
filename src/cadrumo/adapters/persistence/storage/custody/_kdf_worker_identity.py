"""Parent-side validation of the supervised KDF worker identity."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from ._kdf_attestation import validate_ready_attestation_shape
from ._kdf_codec import supervision_refusal as _supervision_refusal
from ._kdf_process import worker_environment
from ._kdf_windows_job import _WindowsJob


def verify_ready_worker(
    payload: dict[str, object],
    *,
    neutral_directory: tempfile.TemporaryDirectory[str] | None,
    expected_posix_file_descriptors: tuple[int, int] | None,
    process: subprocess.Popen[bytes],
    job: _WindowsJob | None,
) -> None:
    expected_platform = "win32" if sys.platform == "win32" else "posix"
    validate_ready_attestation_shape(payload, expected_platform)
    _validate_environment(payload, neutral_directory=neutral_directory)
    if expected_platform == "posix":
        _validate_descriptors(payload, expected_posix_file_descriptors=expected_posix_file_descriptors)
    _verify_process(process, job=job)


def _validate_environment(
    payload: dict[str, object],
    *,
    neutral_directory: tempfile.TemporaryDirectory[str] | None,
) -> None:
    if neutral_directory is None:
        raise ValueError("profile KDF neutral directory is unavailable")
    neutral_root = Path(neutral_directory.name).resolve()
    if payload["cwd"] != str(neutral_root):
        raise ValueError("profile KDF worker cwd is not neutral")
    if payload["environment_keys"] != sorted(worker_environment(neutral_root=neutral_root)):
        raise ValueError("profile KDF worker environment is not allowlisted")


def _validate_descriptors(
    payload: dict[str, object],
    *,
    expected_posix_file_descriptors: tuple[int, int] | None,
) -> None:
    if expected_posix_file_descriptors is None:
        raise ValueError("profile KDF child descriptors are unavailable")
    if payload["open_file_descriptors"] != sorted({0, 1, 2, *expected_posix_file_descriptors}):
        raise ValueError("profile KDF worker inherited an unallowlisted descriptor")


def _verify_process(process: subprocess.Popen[bytes], *, job: _WindowsJob | None) -> None:
    if sys.platform == "win32":
        if job is None or not job.contains(process) or job.limits() != _expected_windows_limits():
            raise _supervision_refusal()
        return
    getpgid = getattr(os, "getpgid", None)
    if getpgid is None or getpgid(process.pid) != process.pid:
        raise _supervision_refusal()


def _expected_windows_limits() -> dict[str, int]:
    from ._kdf_windows_job import (
        PROFILE_CUSTODY_KDF_WORKER_CPU_SECONDS,
        PROFILE_CUSTODY_KDF_WORKER_MAX_PROCESSES,
        PROFILE_CUSTODY_KDF_WORKER_MEMORY_BYTES,
    )

    return {
        "cpu_seconds": PROFILE_CUSTODY_KDF_WORKER_CPU_SECONDS,
        "memory_bytes": PROFILE_CUSTODY_KDF_WORKER_MEMORY_BYTES,
        "max_processes": PROFILE_CUSTODY_KDF_WORKER_MAX_PROCESSES,
    }


__all__ = ["verify_ready_worker"]
