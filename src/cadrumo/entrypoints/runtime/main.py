"""Compose native runtime ownership and bounded public transport readiness."""

from __future__ import annotations

import argparse
import signal
import sys
import time
from collections.abc import Callable, Generator
from contextlib import ExitStack, contextmanager
from functools import partial
from importlib.metadata import version
from pathlib import Path
from threading import Event
from typing import Literal
from uuid import uuid4

from cadrumo.adapters.local_runtime.runtime_manager_composition import installed_runtime_binding

from ...adapters.local_runtime.framing import RuntimeTransportCleanup
from ...adapters.local_runtime.linux_login import linux_login_inventory
from ...adapters.local_runtime.linux_managed_stop import LinuxManagedRuntimeStop
from ...adapters.local_runtime.posix import PosixRuntimeEndpoint, posix_owner_uid
from ...adapters.local_runtime.server import RuntimeTransportServer
from ...adapters.local_runtime.windows import WindowsRuntimeEndpoint
from ...adapters.local_runtime.windows_login import windows_login_inventory
from ...adapters.local_runtime.windows_managed_stop import WindowsManagedRuntimeStop, open_runtime_launcher_latch
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError, RuntimeShutdownIncompleteError
from ...application.runtime.login import RuntimeLoginInventory
from ...core.async_cleanup import AsyncResourceCleanupError, async_cleanup_failures, has_async_cleanup_failure
from ...core.config import load_settings, override_settings
from ...core.logging import LogExtra, configure_logging, get_logger
from .profile_connections import RuntimeProfileConnections
from .shutdown import RuntimeShutdownEvent, RuntimeShutdownWatchdog, terminate_runtime

_LOGGER = get_logger(__name__)


def _log_startup_phase(
    phase: Literal["managed_stop_setup", "registry_prepare"],
    transition: Literal["enter", "leave"],
    elapsed: float,
    *,
    primary_error: BaseException | None = None,
) -> None:
    """Keep diagnostic failures from replacing an existing product primary."""
    try:
        _LOGGER.info(
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


@contextmanager
def _startup_phase(phase: Literal["managed_stop_setup", "registry_prepare"]) -> Generator[None]:
    """Emit only fixed phase names and elapsed native monotonic seconds."""
    started = time.monotonic()
    primary: list[BaseException] = []
    _log_startup_phase(phase, "enter", 0.0)
    try:
        yield
    except BaseException as error:
        primary.append(error)
        raise
    finally:
        elapsed = time.monotonic() - started
        _log_startup_phase(phase, "leave", elapsed, primary_error=primary[0] if primary else None)


def parse_runtime_arguments(arguments: list[str] | None = None) -> argparse.Namespace:
    """Parse the same private native-manager launch binding at both boundaries."""
    parser = argparse.ArgumentParser(prog="cadrumo-runtime", allow_abbrev=False)
    parser.add_argument("--storage-root", required=True, type=Path)
    parser.add_argument("--storage-identity", required=True)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--managed-session", action="store_true")
    parser.add_argument("--windows-runtime-host", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--windows-launcher-identity", help=argparse.SUPPRESS)
    options = parser.parse_args(arguments)
    if (options.windows_runtime_host or options.windows_launcher_identity is not None) and (
        sys.platform != "win32"
        or not options.managed_session
        or not options.windows_runtime_host
        or options.windows_launcher_identity is None
    ):
        parser.error("invalid native runtime host disposition")
    return options


def run(arguments: list[str] | None = None) -> int:
    """Run one user/root owner; a manager argument never grants profile authority."""
    options = parse_runtime_arguments(arguments)
    stop = Event()
    previous = {number: signal.getsignal(number) for number in (signal.SIGINT, signal.SIGTERM)}
    try:
        installed_version = version("cadrumo")
        if options.expected_version != installed_version:
            raise RuntimeRefusalError(RuntimeRefusalCode.VERSION_MISMATCH)
        root = Path(options.storage_root)
        if not root.is_absolute():
            raise RuntimeRefusalError(RuntimeRefusalCode.ROOT_MISMATCH)
        endpoint = (
            WindowsRuntimeEndpoint(storage_root=root)
            if sys.platform == "win32"
            else PosixRuntimeEndpoint(storage_root=root)
        )
        endpoint_owner = RuntimeTransportCleanup(endpoint)
        endpoint_primary: list[BaseException] = []
        try:
            with ExitStack() as launcher_resources:
                if endpoint.storage_identity != options.storage_identity:
                    raise RuntimeRefusalError(RuntimeRefusalCode.ROOT_MISMATCH)
                if options.windows_runtime_host:
                    native_binding = installed_runtime_binding(
                        root=root, endpoint=endpoint, product_version=installed_version
                    )
                    if native_binding is None:
                        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
                    latch = launcher_resources.enter_context(
                        open_runtime_launcher_latch(native_binding, options.windows_launcher_identity)
                    )
                    stop = RuntimeShutdownEvent(before_stop=latch.set)
                if sys.platform == "win32":
                    # Respect explicit operator routing. Only handler creation sees
                    # the fallback after native owner/root verification.
                    settings = load_settings()
                    if "cadrumo_log_dir" in settings.model_fields_set:
                        configure_logging()
                    else:
                        with override_settings(cadrumo_log_dir=root / "logs"):
                            configure_logging()
                for number in previous:
                    signal.signal(number, lambda _number, _frame: stop.set())
                boot_id = uuid4()
                prepare_stop: Callable[[], None] | None = None
                finalize_stop: Callable[[], None] | None = None
                login_inventory: Callable[[], RuntimeLoginInventory] | None = None
                if isinstance(endpoint, WindowsRuntimeEndpoint):
                    owner_id = endpoint.os_owner_id
                    login_inventory = partial(windows_login_inventory, expected_owner=owner_id)
                elif sys.platform == "linux":
                    login_inventory = partial(linux_login_inventory, expected_owner=str(posix_owner_uid()))
                with ExitStack() as resources:
                    if options.managed_session and sys.platform in {"linux", "win32"}:
                        with _startup_phase("managed_stop_setup"):
                            binding = installed_runtime_binding(
                                root=root, endpoint=endpoint, product_version=installed_version
                            )
                            if binding is not None and sys.platform == "linux":
                                prepare_stop = LinuxManagedRuntimeStop(binding)
                            elif binding is not None and sys.platform == "win32":
                                managed_stop = resources.enter_context(WindowsManagedRuntimeStop(binding, stop))
                                prepare_stop = managed_stop
                                finalize_stop = managed_stop.finalize
                    profiles = RuntimeProfileConnections(
                        storage_root=root,
                        storage_identity=endpoint.storage_identity,
                        runtime_boot_id=boot_id,
                        stop=stop,
                        login_inventory=login_inventory,
                    )
                    with _startup_phase("registry_prepare"):
                        profiles.prepare_registry()
                    with RuntimeShutdownWatchdog(stop, timeout=RuntimeTransportServer.DRAIN_SECONDS + 2):
                        try:
                            RuntimeTransportServer(
                                endpoint,
                                product_version=installed_version,
                                stop=stop,
                                profiles=profiles,
                                boot_id=boot_id,
                                owner_stop_available=not options.managed_session or prepare_stop is not None,
                                prepare_owner_stop=prepare_stop,
                                finalize_owner_stop=finalize_stop,
                            ).serve()
                        except RuntimeShutdownIncompleteError:
                            # Never release the owner lock while callbacks, constructors
                            # or uncontained descendants still belong to this runtime.
                            terminate_runtime()
        except BaseException as error:
            endpoint_primary.append(error)
            raise
        finally:
            if sys.platform != "win32":
                endpoint.close()
            else:
                try:
                    endpoint_owner.close_now()
                except BaseException as failure:
                    retained = AsyncResourceCleanupError(
                        (endpoint_owner,), (failure,), retry_task_name="runtime-endpoint-release", close_attempts=1
                    )
                    if not endpoint_primary:
                        raise retained from failure
                    primary_error = endpoint_primary[0]
                    for previous_failure in async_cleanup_failures(primary_error):
                        retained = previous_failure.merged_with(retained)
                    primary_error.__dict__["async_cleanup_error"] = retained
                    if isinstance(primary_error.__dict__.get("cleanup_error"), AsyncResourceCleanupError):
                        primary_error.__dict__["cleanup_error"] = retained
        return 0
    except RuntimeRefusalError as error:
        if sys.platform == "win32" and has_async_cleanup_failure(error):
            raise
        sys.stderr.write(error.reason.value + "\n")
        return 2
    except KeyboardInterrupt as error:
        if sys.platform == "win32" and has_async_cleanup_failure(error):
            raise
        return 0
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)
