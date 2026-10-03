"""Compose native runtime ownership and bounded public transport readiness."""

from __future__ import annotations

import argparse
import signal
import sys
from collections.abc import Callable, Mapping
from functools import partial
from importlib.metadata import version
from pathlib import Path
from threading import Event
from typing import Any
from uuid import UUID, uuid4

from ...adapters.local_runtime.linux_login import linux_login_inventory
from ...adapters.local_runtime.login_policy import compose_runtime_login_policy
from ...adapters.local_runtime.posix import posix_owner_uid
from ...adapters.local_runtime.posix_endpoint import PosixRuntimeEndpoint
from ...adapters.local_runtime.runtime_transport_cleanup import RuntimeTransportCleanup
from ...adapters.local_runtime.server import RuntimeTransportServer
from ...adapters.local_runtime.windows import WindowsRuntimeEndpoint
from ...adapters.local_runtime.windows_login import windows_login_inventory
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError, RuntimeShutdownIncompleteError
from ...application.runtime.login import RuntimeLoginInventory
from ...core.async_cleanup import AsyncResourceCleanupError, async_cleanup_failures, has_async_cleanup_failure
from ...core.config import load_settings, override_settings
from ...core.logging import configure_logging, get_logger
from ...core.startup_phase_log import startup_phase
from .profile_connections import RuntimeProfileConnections
from .shutdown import RuntimeShutdownEvent, RuntimeShutdownWatchdog, terminate_runtime

_LOGGER = get_logger(__name__)


def parse_runtime_arguments(arguments: list[str] | None = None) -> argparse.Namespace:
    """Parse the explicit runtime owner binding."""
    parser = argparse.ArgumentParser(prog="cadrumo-runtime", allow_abbrev=False)
    parser.add_argument("--storage-root", required=True, type=Path)
    parser.add_argument("--storage-identity", required=True)
    parser.add_argument("--expected-version", required=True)
    options = parser.parse_args(arguments)
    return options


def _configure_runtime_logging(root: Path) -> None:
    if sys.platform != "win32":
        return
    # Respect explicit operator routing. Only handler creation sees the fallback
    # after native owner/root verification.
    settings = load_settings()
    if "cadrumo_log_dir" in settings.model_fields_set:
        configure_logging()
    else:
        with override_settings(cadrumo_log_dir=root / "logs"):
            configure_logging()


def _runtime_login_inventory(
    endpoint: WindowsRuntimeEndpoint | PosixRuntimeEndpoint,
) -> Callable[[], RuntimeLoginInventory] | None:
    if isinstance(endpoint, WindowsRuntimeEndpoint):
        return partial(windows_login_inventory, expected_owner=endpoint.os_owner_id)
    if sys.platform == "linux":
        return partial(linux_login_inventory, expected_owner=str(posix_owner_uid()))
    return None


def _serve_transport(
    endpoint: WindowsRuntimeEndpoint | PosixRuntimeEndpoint,
    installed_version: str,
    stop: Event | RuntimeShutdownEvent,
    profiles: RuntimeProfileConnections,
    boot_id: UUID,
) -> None:
    try:
        RuntimeTransportServer(
            endpoint,
            product_version=installed_version,
            stop=stop,
            profiles=profiles,
            boot_id=boot_id,
        ).serve()
    except RuntimeShutdownIncompleteError:
        # Never release the owner lock while callbacks, constructors or
        # uncontained descendants still belong to this runtime.
        terminate_runtime()


def _serve_runtime_endpoint(
    options: argparse.Namespace,
    root: Path,
    endpoint: WindowsRuntimeEndpoint | PosixRuntimeEndpoint,
    installed_version: str,
    stop: Event,
    previous: Mapping[signal.Signals, Any],
) -> None:
    if endpoint.storage_identity != options.storage_identity:
        raise RuntimeRefusalError(RuntimeRefusalCode.ROOT_MISMATCH)
    _configure_runtime_logging(root)
    for number in previous:
        signal.signal(number, lambda _number, _frame: stop.set())
    boot_id = uuid4()
    login_policy = compose_runtime_login_policy(
        os_owner_id=endpoint.os_owner_id if isinstance(endpoint, WindowsRuntimeEndpoint) else str(posix_owner_uid()),
        runtime_boot_id=boot_id,
        stop=stop,
        native_inventory=_runtime_login_inventory(endpoint),
    )
    profiles = RuntimeProfileConnections(
        storage_root=root,
        storage_identity=endpoint.storage_identity,
        runtime_boot_id=boot_id,
        stop=stop,
        capture_login=login_policy.capture,
        login_inventory=login_policy.inventory,
    )
    with startup_phase(_LOGGER, "registry_prepare"):
        profiles.prepare_registry()
    with RuntimeShutdownWatchdog(stop, timeout=RuntimeTransportServer.DRAIN_SECONDS + 2):
        _serve_transport(endpoint, installed_version, stop, profiles, boot_id)


def _release_runtime_endpoint(
    endpoint: WindowsRuntimeEndpoint | PosixRuntimeEndpoint,
    owner: RuntimeTransportCleanup,
    primary_errors: list[BaseException],
) -> None:
    if sys.platform != "win32":
        endpoint.close()
        return
    try:
        owner.close_now()
    except BaseException as failure:
        retained = AsyncResourceCleanupError(
            (owner,), (failure,), retry_task_name="runtime-endpoint-release", close_attempts=1
        )
        if not primary_errors:
            raise retained from failure
        primary_error = primary_errors[0]
        for previous_failure in async_cleanup_failures(primary_error):
            retained = previous_failure.merged_with(retained)
        primary_error.__dict__["async_cleanup_error"] = retained
        if isinstance(primary_error.__dict__.get("cleanup_error"), AsyncResourceCleanupError):
            primary_error.__dict__["cleanup_error"] = retained


def _run_runtime_owner(options: argparse.Namespace, stop: Event, previous: Mapping[signal.Signals, Any]) -> int:
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
    owner = RuntimeTransportCleanup(endpoint)
    primary_errors: list[BaseException] = []
    try:
        _serve_runtime_endpoint(options, root, endpoint, installed_version, stop, previous)
    except BaseException as error:
        primary_errors.append(error)
        raise
    finally:
        _release_runtime_endpoint(endpoint, owner, primary_errors)
    return 0


def run(arguments: list[str] | None = None) -> int:
    """Run one user/root owner with independent profile admission."""
    options = parse_runtime_arguments(arguments)
    stop = Event()
    previous = {number: signal.getsignal(number) for number in (signal.SIGINT, signal.SIGTERM)}
    try:
        return _run_runtime_owner(options, stop, previous)
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
