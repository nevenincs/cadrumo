"""Platform process launch and cleanup for the supervised KDF worker."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from contextlib import suppress
from pathlib import Path
from typing import Any, cast

from .....core.child_console import child_console_creation_flags
from .....core.storage_environment import ChildEnvironmentProfile, child_environment
from ._kdf_refusals import supervision_refusal as _supervision_refusal
from ._kdf_windows_job import _WindowsJob
from ._kdf_worker_limits import (
    PROFILE_CUSTODY_KDF_WORKER_CPU_SECONDS,
    PROFILE_CUSTODY_KDF_WORKER_MEMORY_BYTES,
)


def launch_worker(
    *,
    neutral_root: Path,
    request_read: int,
    result_write: int,
) -> tuple[subprocess.Popen[bytes], _WindowsJob | None, frozenset[str]]:
    """Launch one contained worker; also name the environment it was given, for its attestation."""
    command, launch_kwargs = worker_command(
        neutral_root=neutral_root,
        request_read=request_read,
        result_write=result_write,
    )
    if sys.platform == "win32":
        job = _WindowsJob.create()
        process: subprocess.Popen[bytes] | None = None
        try:
            process = _launch_worker_process(command, launch_kwargs)
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
        return process, job, _environment_keys(launch_kwargs)
    process = _launch_worker_process(command, launch_kwargs)
    return process, None, _environment_keys(launch_kwargs)


def _environment_keys(launch_kwargs: dict[str, object]) -> frozenset[str]:
    return frozenset(cast("dict[str, str]", launch_kwargs["env"]))


def _launch_worker_process(command: list[str], launch_kwargs: dict[str, object]) -> subprocess.Popen[bytes]:
    """Launch the fixed worker argv directly, owning the child for its whole lifetime.

    The supervisor keeps the child alive across arbitrary caller threads and
    event loops, so the process must not be owned by a loop-bound transport
    that terminates it when the loop or the transport is collected.
    """
    process: subprocess.Popen[Any] = subprocess.Popen(command, **cast(Any, launch_kwargs))
    return cast("subprocess.Popen[bytes]", process)


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
    command = [*worker_interpreter(), "-m", "cadrumo.adapters.persistence.storage.custody._kdf_worker"]
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
        # A supervised runtime's stop is a console Ctrl+C; its own console keeps
        # the worker out of that event so the runtime alone decides its end.
        common["creationflags"] = child_console_creation_flags()
        command.extend(("--request-handle", str(request_handle), "--result-handle", str(result_handle)))
    else:
        descriptor_bound = os.sysconf("SC_OPEN_MAX")
        common["pass_fds"] = (request_read, result_write)
        common["start_new_session"] = True
        common["preexec_fn"] = apply_posix_worker_limits
        command.extend(
            (
                "--request-fd",
                str(request_read),
                "--result-fd",
                str(result_write),
                "--descriptor-bound",
                str(descriptor_bound),
            )
        )
    return command, common


def worker_interpreter() -> tuple[str, ...]:
    """Return the interpreter argv prefix that starts the worker.

    On Windows the child receives its import roots through PYTHONPATH (see
    :func:`worker_environment`), so it runs the base CPython directly and
    without ``site``: a virtual environment's ``python.exe`` is a launcher
    that starts the base interpreter as a second process, and the
    site-packages ``.pth`` hooks import modules the child never uses. Both are
    pure start-up cost on every wrap and unwrap. Elsewhere the interpreter
    itself resolves the environment, so it is kept as is.
    """
    if sys.platform != "win32":
        return (sys.executable,)
    base = getattr(sys, "_base_executable", None)
    executable = base if isinstance(base, str) and base and Path(base).is_file() else sys.executable
    return (executable, "-S")


def worker_environment(*, neutral_root: Path) -> dict[str, str]:
    # The strict profile pins a neutral root and carries no operator override.
    environment = child_environment(ChildEnvironmentProfile.STRICT, neutral_root / "state", base={})
    environment.update(
        {
            "HOME": str(neutral_root),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "PYTHONNOUSERSITE": "1",
        }
    )
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
    # Darwin rejects every finite address-space limit. Its ready attestation
    # omits that limit; the closed Argon2 grid, validated before allocation,
    # bounds the worker's memory there.
    if sys.platform != "darwin":
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
    "worker_interpreter",
]
