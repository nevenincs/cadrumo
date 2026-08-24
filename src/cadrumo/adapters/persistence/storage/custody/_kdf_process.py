"""Platform process launch and cleanup for the supervised KDF worker."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from contextlib import suppress
from pathlib import Path
from typing import Any, cast

from ._kdf_codec import supervision_refusal as _supervision_refusal
from ._kdf_windows_job import (
    PROFILE_CUSTODY_KDF_WORKER_CPU_SECONDS,
    PROFILE_CUSTODY_KDF_WORKER_MEMORY_BYTES,
    _WindowsJob,
)


def launch_worker(
    *,
    neutral_root: Path,
    request_read: int,
    result_write: int,
) -> tuple[subprocess.Popen[bytes], _WindowsJob | None]:
    command, launch_kwargs = worker_command(
        neutral_root=neutral_root,
        request_read=request_read,
        result_write=result_write,
    )
    if sys.platform == "win32":
        job = _WindowsJob.create()
        process: subprocess.Popen[bytes] | None = None
        try:
            process = cast(
                "subprocess.Popen[bytes]",
                subprocess.Popen(command, **cast(Any, launch_kwargs)),  # noqa: S603 - fixed interpreter and module argv
            )
            job.assign(process)
            if not job.contains(process):
                raise _supervision_refusal()
        except BaseException:
            if process is None:
                job.close()
            else:
                terminate_process_tree(process, job)
            raise
        finally:
            clear_worker_handle_inheritance(request_read=request_read, result_write=result_write)
        return process, job
    process = cast(
        "subprocess.Popen[bytes]",
        subprocess.Popen(command, **cast(Any, launch_kwargs)),  # noqa: S603 - fixed interpreter and module argv
    )
    return process, None


def clear_worker_handle_inheritance(*, request_read: int, result_write: int) -> None:
    """Close the Windows inheritance window immediately after the one launch."""
    if sys.platform != "win32":
        return
    import msvcrt

    for descriptor in (request_read, result_write):
        with suppress(OSError):
            os.set_handle_inheritable(msvcrt.get_osfhandle(descriptor), False)


def worker_command(
    *,
    neutral_root: Path,
    request_read: int,
    result_write: int,
) -> tuple[list[str], dict[str, object]]:
    neutral_cwd = str(neutral_root.resolve())
    command = [sys.executable, "-m", "cadrumo.adapters.persistence.storage.custody._kdf_worker"]
    environment = worker_environment(neutral_root=neutral_root)
    common: dict[str, object] = {
        "close_fds": True,
        "cwd": neutral_cwd,
        "env": environment,
        "stderr": subprocess.DEVNULL,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
    }
    if sys.platform == "win32":
        import msvcrt

        request_handle = msvcrt.get_osfhandle(request_read)
        result_handle = msvcrt.get_osfhandle(result_write)
        os.set_handle_inheritable(request_handle, True)
        os.set_handle_inheritable(result_handle, True)
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.lpAttributeList = {"handle_list": [request_handle, result_handle]}
        common["startupinfo"] = startupinfo
        command.extend(("--request-handle", str(request_handle), "--result-handle", str(result_handle)))
    else:
        common["pass_fds"] = (request_read, result_write)
        common["start_new_session"] = True
        common["preexec_fn"] = apply_posix_worker_limits
        command.extend(("--request-fd", str(request_read), "--result-fd", str(result_write)))
    return command, common


def worker_environment(*, neutral_root: Path) -> dict[str, str]:
    environment = {
        "CADRUMO_LOG_DIR": str(neutral_root / "logs"),
        "CADRUMO_LOCAL_STORAGE_ROOT": str(neutral_root / "state"),
        "HOME": str(neutral_root),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONNOUSERSITE": "1",
    }
    if sys.platform == "win32":
        system_root = os.environ.get("SYSTEMROOT")
        if system_root is None:
            raise _supervision_refusal()
        environment["SYSTEMROOT"] = system_root
        environment["USERPROFILE"] = str(neutral_root)
        # A HANDLE-safe supervisor may itself run the resolved base CPython
        # executable. Preserve its already-resolved import roots for the KDF
        # child without relying on a virtual-environment launcher hop.
        environment["PYTHONPATH"] = os.pathsep.join(entry for entry in sys.path if entry)
    else:
        environment["LC_ALL"] = "C"
    return environment


def apply_posix_worker_limits() -> None:
    import resource

    resource_module = cast(Any, resource)
    resource_module.setrlimit(resource_module.RLIMIT_AS, (PROFILE_CUSTODY_KDF_WORKER_MEMORY_BYTES,) * 2)
    resource_module.setrlimit(resource_module.RLIMIT_CPU, (PROFILE_CUSTODY_KDF_WORKER_CPU_SECONDS,) * 2)
    resource_module.setrlimit(resource_module.RLIMIT_CORE, (0, 0))
    resource_module.setrlimit(resource_module.RLIMIT_FSIZE, (0, 0))
    resource_module.setrlimit(resource_module.RLIMIT_NOFILE, (16, 16))


def terminate_process_tree(process: subprocess.Popen[bytes], job: _WindowsJob | None) -> None:
    if job is not None:
        job.close()
    elif sys.platform != "win32":
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
    if process.poll() is None:
        process.kill()
    with suppress(subprocess.TimeoutExpired):
        process.wait(timeout=1.0)


__all__ = [
    "apply_posix_worker_limits",
    "clear_worker_handle_inheritance",
    "launch_worker",
    "terminate_process_tree",
    "worker_command",
    "worker_environment",
]
