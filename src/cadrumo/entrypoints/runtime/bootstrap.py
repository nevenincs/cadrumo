"""Start the runtime under an isolated interpreter before application imports."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Literal, cast

if TYPE_CHECKING:
    from argparse import Namespace
    from logging import Logger

    from _win32typing import PyHANDLE


def _log_startup_phase(
    logger: Logger,
    phase: Literal["bootstrap", "main_import"],
    transition: Literal["enter", "leave"],
    elapsed: float,
    *,
    primary_error: BaseException | None = None,
) -> None:
    """Keep only fixed diagnostic values and preserve any original primary."""
    try:
        from ...core.logging import LogExtra

        logger.info(
            "runtime_startup phase=%s transition=%s elapsed_seconds=%.6f",
            phase,
            transition,
            elapsed,
            extra=LogExtra(
                {"startup_phase": phase, "transition": transition, "elapsed_seconds": elapsed}
            ).for_logging(),
        )
    except Exception:
        return
    except BaseException:
        if primary_error is None:
            raise


def _require_managed_login(expected_owner: str) -> None:
    """Require fresh positive native login evidence, independently of completeness."""
    from ...adapters.local_runtime.windows_login import windows_login_inventory
    from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
    from ...application.user_profile.access_contracts import Availability, LoginEligibility

    inventory = windows_login_inventory(expected_owner=expected_owner)
    for witness in inventory.logins:
        observed = witness.observe(credential_facilities=Availability.NOT_REQUIRED)
        if (
            observed.login_id == witness.login_id
            and observed.os_owner_id == expected_owner
            and observed.active
            and observed.unattended is LoginEligibility.ELIGIBLE
        ):
            return
    raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)


async def _run_managed_windows(options: Namespace, environment: Mapping[str, str]) -> int:
    """Own at most three isolated host attempts, with one physical Job per attempt."""
    from datetime import datetime
    from importlib.metadata import version
    from pathlib import Path
    from uuid import UUID, uuid4

    import win32api
    import win32con
    import win32process

    from ...adapters.local_runtime.framing import RuntimeTransportCleanup, VerifiedRuntimeConnection
    from ...adapters.local_runtime.runtime_manager_composition import installed_runtime_binding
    from ...adapters.local_runtime.server import RuntimeTransportServer
    from ...adapters.local_runtime.windows import WindowsRuntimeEndpoint
    from ...adapters.local_runtime.windows_managed_stop import WindowsRuntimeLaunchIdentity, WindowsRuntimeStopLatch
    from ...adapters.local_runtime.windows_manager import WindowsTaskManager
    from ...adapters.local_runtime.windows_process import (
        WindowsOwnedProcess,
        WindowsProcessScope,
        unreturned_windows_process_scope,
    )
    from ...adapters.local_runtime.windows_task_process import task_engine_owns_process
    from ...application.runtime.contracts import (
        RuntimeClientHello,
        RuntimeRefusalCode,
        RuntimeRefusalError,
        RuntimeShutdownIncompleteError,
    )
    from ...core.async_cleanup import (
        AsyncCloseable,
        async_cleanup_failures,
        close_async_resources,
        has_async_cleanup_failure,
    )

    if sys.platform != "win32" or not sys.flags.isolated or not options.managed_session or options.windows_runtime_host:
        raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
    process_times = cast("Callable[[int], Mapping[str, object]]", win32process.GetProcessTimes)
    installed_version = version("cadrumo")
    if options.expected_version != installed_version:
        raise RuntimeRefusalError(RuntimeRefusalCode.VERSION_MISMATCH)
    root = Path(options.storage_root)
    if not root.is_absolute():
        raise RuntimeRefusalError(RuntimeRefusalCode.ROOT_MISMATCH)
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    endpoint_owner = RuntimeTransportCleanup(endpoint)
    latch: WindowsRuntimeStopLatch | None = None
    outer_primary: list[BaseException] = []
    try:
        if endpoint.storage_identity != options.storage_identity:
            raise RuntimeRefusalError(RuntimeRefusalCode.ROOT_MISMATCH)
        binding = installed_runtime_binding(root=root, endpoint=endpoint, product_version=installed_version)
        if binding is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        manager = WindowsTaskManager(binding)
        original = manager.prepare_current_process_stop()
        # These are lifecycle coordinates, not private session authority.
        latch = WindowsRuntimeStopLatch(
            expected_owner=binding.os_owner_id, name="Local\\cadrumo-runtime-stop-" + uuid4().hex, create=True
        )
        identity = WindowsRuntimeLaunchIdentity(
            stop_name=latch.name,
            launcher_pid=os.getpid(),
            launcher_created=cast(datetime, process_times(win32api.GetCurrentProcess())["CreationTime"]).isoformat(),
            instance_guid=str(original.instance_guid),
            engine_pid=original.engine_pid,
            login_autostart=original.login_autostart,
        )
        previous_boot: UUID | None = None
        for attempt in range(3):
            if latch.wait(0):
                return 0
            # Reuse the established 75-second cold-start readiness bound. The
            # synchronous native API calls themselves offer no cancellation API.
            deadline = time.monotonic() + 75
            current = manager.prepare_current_process_stop()
            if current != original:
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            _require_managed_login(binding.os_owner_id)
            if manager.prepare_current_process_stop() != original:
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            if latch.wait(0):
                return 0
            if time.monotonic() >= deadline:
                raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
            scope: WindowsProcessScope | None = None
            peer_owner: RuntimeTransportCleanup | None = None
            peer_process: WindowsOwnedProcess | None = None
            probe_owner: RuntimeTransportCleanup | None = None
            attempt_primary: list[BaseException] = []
            exit_code: int | None = None
            try:
                try:
                    scope = WindowsProcessScope()
                except BaseException as error:
                    scope = unreturned_windows_process_scope(error)
                    raise
                if latch.wait(0):
                    return 0
                if time.monotonic() >= deadline:
                    raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
                launched = scope.launch(
                    executable=Path(sys.executable),
                    arguments=(
                        "-I",
                        "-m",
                        "cadrumo.entrypoints.runtime",
                        *sys.argv[1:],
                        "--windows-runtime-host",
                        "--windows-launcher-identity",
                        identity.encode(),
                    ),
                    directory=root,
                    environment=environment,
                )
                stop_deadline: float | None = None
                ready = False
                while not ready:
                    if latch.wait(0) and stop_deadline is None:
                        stop_deadline = time.monotonic() + RuntimeTransportServer.DRAIN_SECONDS + 2
                    if stop_deadline is not None and time.monotonic() >= stop_deadline:
                        return 0
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        if latch.wait(0):
                            return 0
                        raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
                    try:
                        # This is the exact creation-time Job child, not a PID
                        # reopened to determine whether the launcher still lives.
                        launched.wait(timeout=0)
                    except RuntimeRefusalError as error:
                        if error.reason is not RuntimeRefusalCode.DEADLINE_EXCEEDED:
                            raise
                    else:
                        # A host which never proved readiness is never retried.
                        if latch.wait(0):
                            return 0
                        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
                    connection = None
                    probe_primary: list[BaseException] = []
                    try:
                        channel = endpoint.connect(timeout=min(0.5, remaining))
                        probe_owner = RuntimeTransportCleanup(channel)
                        pid = channel.peer.process_id
                        if pid is None or pid == os.getpid():
                            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
                        handle = int(
                            cast(
                                "PyHANDLE",
                                cast(
                                    object,
                                    win32api.OpenProcess(
                                        win32con.PROCESS_QUERY_INFORMATION | win32con.SYNCHRONIZE, False, pid
                                    ),
                                ),
                            ).Detach()
                        )
                        peer_process = WindowsOwnedProcess(handle=handle, pid=pid)
                        peer_owner = RuntimeTransportCleanup(peer_process)
                        channel.verify_peer_process(handle)
                        created = process_times(handle)["CreationTime"]
                        if (
                            not scope.contains_process(handle)
                            or not task_engine_owns_process(launched.pid, pid)
                            or manager.prepare_current_process_stop() != original
                            or not scope.contains_process(handle)
                            or process_times(handle)["CreationTime"] != created
                            or time.monotonic() >= deadline
                        ):
                            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
                        channel.verify_peer_process(handle)
                        # A connectable, exact owned host has already armed
                        # its shutdown watchdog before opening this listener.
                        try:
                            connection = VerifiedRuntimeConnection(
                                channel,
                                expected=RuntimeClientHello(
                                    product_version=installed_version, storage_identity=endpoint.storage_identity
                                ),
                                deadline=min(deadline, stop_deadline) if stop_deadline is not None else deadline,
                            )
                        except BaseException as error:
                            retained = error.__dict__.get("_runtime_transport_cleanup")
                            if isinstance(retained, RuntimeTransportCleanup):
                                probe_owner = retained
                            raise
                        probe_owner.resource = connection
                        if connection.hello.boot_id == previous_boot:
                            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
                        channel.verify_peer_process(handle)
                        previous_boot = connection.hello.boot_id
                        ready = True
                    except BaseException as error:
                        probe_primary.append(error)
                        if not (
                            isinstance(error, RuntimeRefusalError)
                            and connection is None
                            and peer_process is None
                            and error.reason is RuntimeRefusalCode.ENDPOINT_NOT_READY
                            and not has_async_cleanup_failure(error)
                        ):
                            raise
                    finally:
                        await close_async_resources(
                            probe_owner,
                            task_name="managed-runtime-readiness-close",
                            primary_error=probe_primary[0] if probe_primary else None,
                        )
                        if probe_owner is not None and probe_owner.released:
                            probe_owner = None
                    if probe_primary:
                        if has_async_cleanup_failure(probe_primary[0]):
                            raise probe_primary[0]
                        await asyncio.sleep(0.05)
                if peer_process is None:
                    raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
                while exit_code is None:
                    if latch.wait(0) and stop_deadline is None:
                        # The host publishes BEFORE its local stop Event. Keep
                        # its existing drain/watchdog opportunity before any
                        # native containment retirement, without a restart.
                        stop_deadline = time.monotonic() + RuntimeTransportServer.DRAIN_SECONDS + 2
                    try:
                        exit_code = peer_process.wait(timeout=0)
                    except RuntimeRefusalError as error:
                        if error.reason is not RuntimeRefusalCode.DEADLINE_EXCEEDED:
                            raise
                        if stop_deadline is not None and time.monotonic() >= stop_deadline:
                            raise RuntimeShutdownIncompleteError() from error
                        await asyncio.sleep(0.05)
            except BaseException as error:
                attempt_primary.append(error)
                raise
            finally:
                # Every attempt's entire Job settles before the next can exist.
                # Adopt actual native failure owners, never another scope proxy.
                attempt_resources: dict[int, AsyncCloseable] = {
                    id(resource): resource for resource in (probe_owner, scope, peer_owner) if resource is not None
                }
                if attempt_primary:
                    for failure in async_cleanup_failures(attempt_primary[0]):
                        for resource in failure.resources:
                            attempt_resources[id(resource)] = resource
                await close_async_resources(
                    *attempt_resources.values(),
                    task_name="managed-runtime-attempt-release",
                    primary_error=attempt_primary[0] if attempt_primary else None,
                )
            # Classify the actual retained pipe host, never the venv redirector.
            if latch.wait(0) or exit_code == 0:
                return 0
            if exit_code in (None, 2, 259) or not isinstance(exit_code, int) or not 0 <= exit_code <= 0xFFFFFFFF:
                return 2
            if attempt == 2:
                return 2
            if latch.wait(float(attempt + 1)):
                return 0
        return 2
    except BaseException as error:
        outer_primary.append(error)
        raise
    finally:
        outer_resources: dict[int, AsyncCloseable] = {
            id(resource): resource
            for resource in (latch.cleanup_owner if latch is not None else None, endpoint_owner)
            if resource is not None
        }
        if outer_primary:
            for failure in async_cleanup_failures(outer_primary[0]):
                for resource in failure.resources:
                    outer_resources[id(resource)] = resource
        await close_async_resources(
            *outer_resources.values(),
            task_name="managed-runtime-launcher-release",
            primary_error=outer_primary[0] if outer_primary else None,
        )


def main() -> None:
    """Exclude ambient import paths and third-party model plugins at the launch door."""
    environment = {
        key: value for key, value in os.environ.items() if not key.upper().startswith(("PYTHON", "LD_", "DYLD_"))
    }
    environment["PYDANTIC_DISABLE_PLUGINS"] = "__all__"
    if not sys.flags.isolated:
        arguments = [sys.executable, "-I", "-m", "cadrumo.entrypoints.runtime", *sys.argv[1:]]
        if sys.platform == "win32":
            # Windows has no exec-style process replacement. Keep the manager's
            # launcher alive until its isolated runtime exits, without a shell.
            result = subprocess.run(arguments, env=environment, check=False)  # noqa: S603 -- exact interpreter/module.
            raise SystemExit(result.returncode)
        os.execve(  # noqa: S606 -- exact interpreter and module; no shell or credential arguments.
            sys.executable,
            arguments,
            environment,
        )
    os.environ.clear()
    os.environ.update(environment)
    if sys.platform != "win32":
        from .main import run

        raise SystemExit(run())

    started = time.monotonic()
    from ...core.logging import (
        defer_logging_configuration,
        get_logger,
        resume_logging_configuration,
    )

    logger = get_logger(__name__)
    # Quiet phase records stay in the canonical bounded buffer until main has
    # validated its root. A pre-main hang has no durable diagnostic file yet.
    defer_logging_configuration()
    try:
        _log_startup_phase(logger, "bootstrap", "enter", 0.0)
        importing = time.monotonic()
        primary: list[BaseException] = []
        _log_startup_phase(logger, "main_import", "enter", 0.0)
        try:
            from .main import parse_runtime_arguments, run
        except BaseException as error:
            primary.append(error)
            raise
        finally:
            elapsed = time.monotonic() - importing
            _log_startup_phase(logger, "main_import", "leave", elapsed, primary_error=primary[0] if primary else None)
            elapsed = time.monotonic() - started
            _log_startup_phase(logger, "bootstrap", "leave", elapsed, primary_error=primary[0] if primary else None)
        options = parse_runtime_arguments()
        if options.managed_session and not options.windows_runtime_host:
            from ...application.runtime.contracts import RuntimeRefusalError
            from ...core.async_cleanup import has_async_cleanup_failure

            try:
                result = asyncio.run(_run_managed_windows(options, environment))
            except BaseException as error:
                if has_async_cleanup_failure(error):
                    sys.stderr.write("runtime_cleanup_incomplete\n")
                elif isinstance(error, RuntimeRefusalError):
                    sys.stderr.write(error.reason.value + "\n")
                else:
                    sys.stderr.write("runtime_unavailable\n")
                # This is the process entrypoint only. The async owner above
                # keeps the exact primary and retry owners for library callers.
                raise SystemExit(2) from None
            raise SystemExit(result)
        raise SystemExit(run())
    finally:
        resume_logging_configuration()
