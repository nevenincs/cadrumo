"""Join a test-owned installed foreground runtime for the whole continuation.

The explicit development session policy proves native IPC and private profile
operations, without claiming native desktop login or lock-state coverage.
"""

from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from importlib.metadata import version
from pathlib import Path
from typing import Any

from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.posix_endpoint import PosixRuntimeEndpoint
from cadrumo.application.runtime.contracts import RuntimeClientHello, RuntimeRefusalCode, RuntimeRefusalError
from dev.acceptance.installed_cli import build_installed_cli_environment

from .cli_contracts import RetencionesInstalledCliError


async def _stop_runtime(process: asyncio.subprocess.Process) -> str:
    if process.returncode is None:
        with suppress(ProcessLookupError):
            process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=15)
        except TimeoutError:
            # Signal this retained direct child; do not infer reusable group
            # ownership after an async child watcher may have reaped a PID.
            with suppress(ProcessLookupError):
                process.kill()
            await asyncio.wait_for(process.wait(), timeout=5)
            return "joined_after_kill"
    else:
        await asyncio.wait_for(process.wait(), timeout=5)
    return "joined"


@contextmanager
def installed_foreground_runtime(
    *,
    cli_executable: Path,
    storage_root: Path,
    authority_root: Path,
    runtime_socket_dir: Path,
    startup_timeout_seconds: float = 60,
) -> Iterator[dict[str, Any]]:
    """Verify installed cohort/root readiness, then join shutdown on every outcome."""
    if sys.platform not in {"darwin", "linux"}:
        raise RetencionesInstalledCliError(stage="runtime_fixture", diagnostic_code="posix_fixture_required")
    executable = cli_executable.resolve(strict=True).parent / "cadrumo-runtime"
    if not executable.is_file():
        raise RetencionesInstalledCliError(stage="runtime_fixture", diagnostic_code="installed_runtime_missing")
    try:
        endpoint = PosixRuntimeEndpoint(storage_root=storage_root, namespace=runtime_socket_dir)
    except RuntimeRefusalError as error:
        raise RetencionesInstalledCliError(stage="runtime_endpoint", diagnostic_code=error.reason.value) from error
    with asyncio.Runner() as runner:
        process = None
        evidence = None
        try:
            cohort = version("cadrumo")
            environment = build_installed_cli_environment(
                storage_root=storage_root, authority_root=authority_root, runtime_socket_dir=runtime_socket_dir
            )
            environment["CADRUMO_DEV_RUNTIME_SESSION_OVERRIDE"] = "1"
            process = runner.run(
                asyncio.create_subprocess_exec(
                    str(executable),
                    "--storage-root",
                    str(storage_root),
                    "--storage-identity",
                    endpoint.storage_identity,
                    "--expected-version",
                    cohort,
                    cwd=storage_root,
                    env=environment,
                    stdin=asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                    start_new_session=True,
                    close_fds=True,
                )
            )
            deadline = time.monotonic() + startup_timeout_seconds
            while True:
                if process.returncode is not None:
                    raise RetencionesInstalledCliError(stage="runtime_startup", diagnostic_code="runtime_exited")
                try:
                    channel = endpoint.connect(timeout=0.2)
                    connection = VerifiedRuntimeConnection(
                        channel,
                        expected=RuntimeClientHello(product_version=cohort, storage_identity=endpoint.storage_identity),
                        deadline=deadline,
                    )
                    boot_id = str(connection.hello.boot_id)
                    connection.close()
                    break
                except RuntimeRefusalError as error:
                    if error.reason is not RuntimeRefusalCode.ENDPOINT_NOT_READY or time.monotonic() >= deadline:
                        raise RetencionesInstalledCliError(
                            stage="runtime_readiness", diagnostic_code=error.reason.value
                        ) from error
                    runner.run(asyncio.sleep(0.05))
            evidence = {
                "mode": "test_owned_installed_foreground",
                "session_policy": "explicit_boot_bounded_development",
                "native_desktop_login_claimed": False,
                "native_lock_state_claimed": False,
                "cohort_root_handshake": "verified",
                "runtime_boot_id": boot_id,
            }
            yield evidence
        finally:
            try:
                if process is not None:
                    shutdown = runner.run(_stop_runtime(process))
            finally:
                endpoint.close()
            if evidence is not None:
                evidence["shutdown"] = shutdown
