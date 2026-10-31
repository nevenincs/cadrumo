"""Parent-side validation of the supervised KDF worker identity."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from typing import cast

from ._kdf_attestation import kdf_worker_platform, validate_ready_attestation_shape
from ._kdf_refusals import supervision_refusal as _supervision_refusal
from ._kdf_windows_job import _WindowsJob

# Darwin adds this non-secret text-encoding preference to every new process,
# whatever environment its parent supplies.
_DARWIN_INJECTED_ENVIRONMENT = frozenset({"__CF_USER_TEXT_ENCODING"})

KDF_WORKER_ENVIRONMENT_REFUSAL = "profile KDF worker environment is not allowlisted"


def verify_ready_worker(
    payload: dict[str, object],
    *,
    neutral_directory: tempfile.TemporaryDirectory[str] | None,
    environment_keys: frozenset[str] | None,
    expected_posix_file_descriptors: tuple[int, int] | None,
    process: subprocess.Popen[bytes],
    job: _WindowsJob | None,
) -> None:
    """Accept a ready child only on the exact environment, directory, descriptors and containment it was given.

    ``environment_keys`` is the allowlist the launch actually passed, so the
    check compares against what this child received instead of rebuilding the
    environment, which walks and normalises every storage location.
    """
    expected_platform = kdf_worker_platform()
    validate_ready_attestation_shape(payload, expected_platform)
    _validate_environment(payload, neutral_directory=neutral_directory, environment_keys=environment_keys)
    if expected_platform != "win32":
        _validate_descriptors(payload, expected_posix_file_descriptors=expected_posix_file_descriptors)
    _verify_process(process, job=job)


def _validate_environment(
    payload: dict[str, object],
    *,
    neutral_directory: tempfile.TemporaryDirectory[str] | None,
    environment_keys: frozenset[str] | None,
) -> None:
    if neutral_directory is None or environment_keys is None:
        raise ValueError("profile KDF neutral directory is unavailable")
    if not _is_neutral_directory(payload["cwd"], neutral_directory.name):
        raise ValueError("profile KDF worker cwd is not neutral")
    reported = payload["environment_keys"]
    if not isinstance(reported, list):
        raise ValueError(KDF_WORKER_ENVIRONMENT_REFUSAL)
    _validate_environment_keys(cast("list[object]", reported), environment_keys)


def _is_neutral_directory(reported: object, neutral_directory: str) -> bool:
    # The kernel reports a directory in its on-disk spelling, which a link or a
    # case-insensitive volume can make textually different from the path the
    # parent created. Identity of the directory itself is the neutrality claim.
    if not isinstance(reported, str) or not reported:
        return False
    try:
        return os.path.samefile(reported, neutral_directory)
    except OSError:
        return False


def _validate_environment_keys(reported: list[object], environment_keys: frozenset[str]) -> None:
    keys = [key for key in reported if isinstance(key, str)]
    given = set(environment_keys)
    injected = _DARWIN_INJECTED_ENVIRONMENT if sys.platform == "darwin" else frozenset[str]()
    if keys != reported or keys != sorted(set(keys)) or not given <= set(keys) <= given | injected:
        raise ValueError(KDF_WORKER_ENVIRONMENT_REFUSAL)


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
    from ._kdf_worker_limits import (
        PROFILE_CUSTODY_KDF_WORKER_CPU_SECONDS,
        PROFILE_CUSTODY_KDF_WORKER_MAX_PROCESSES,
        PROFILE_CUSTODY_KDF_WORKER_MEMORY_BYTES,
    )

    return {
        "cpu_seconds": PROFILE_CUSTODY_KDF_WORKER_CPU_SECONDS,
        "memory_bytes": PROFILE_CUSTODY_KDF_WORKER_MEMORY_BYTES,
        "max_processes": PROFILE_CUSTODY_KDF_WORKER_MAX_PROCESSES,
    }


__all__ = ["KDF_WORKER_ENVIRONMENT_REFUSAL", "verify_ready_worker"]
