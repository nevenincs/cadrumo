"""Compose native runtime ownership and bounded public transport readiness."""

from __future__ import annotations

import argparse
import os
import signal
import sys
from collections.abc import Callable, Mapping
from functools import partial
from importlib.metadata import version
from pathlib import Path
from threading import Event
from typing import Any
from uuid import UUID, uuid4

from ...adapters.local_runtime.boot_record import RuntimeBootRecordPublication, current_runtime_boot_record
from ...adapters.local_runtime.linux_login import linux_login_inventory
from ...adapters.local_runtime.login_policy import compose_runtime_login_policy
from ...adapters.local_runtime.posix import posix_owner_uid
from ...adapters.local_runtime.posix_endpoint import PosixRuntimeEndpoint
from ...adapters.local_runtime.runtime_transport_cleanup import RuntimeTransportCleanup
from ...adapters.local_runtime.server import RuntimeTransportServer
from ...adapters.local_runtime.windows import WindowsRuntimeEndpoint
from ...adapters.local_runtime.windows_login import windows_login_inventory
from ...adapters.local_runtime.windows_token_elevation import (
    current_process_token_elevation_type,
    supervised_elevation_refused,
)
from ...application.runtime.contracts import (
    RuntimeExitReason,
    RuntimeRefusalCode,
    RuntimeRefusalError,
    RuntimeShutdownIncompleteError,
    runtime_refusal_exit_reason,
)
from ...application.runtime.login import RuntimeLoginInventory
from ...core.async_cleanup import AsyncResourceCleanupError, async_cleanup_failures, has_async_cleanup_failure
from ...core.child_console import isolate_child_consoles
from ...core.config import load_settings, override_settings
from ...core.diagnostic_log import diagnostic_error_fields, diagnostic_event, diagnostic_process, diagnostic_scope
from ...core.logging import configure_logging, get_logger
from ...core.startup_phase_log import startup_phase
from ...domain.calculations.registry.authority import published_authority_generation
from .profile_connections import RuntimeProfileConnections
from .shutdown import RuntimeShutdownEvent, RuntimeShutdownWatchdog, RuntimeStop, terminate_runtime
from .supervised_channel import (
    SupervisedRuntime,
    SupervisorChannel,
    route_diagnostics_to_redacted_logging,
    take_supervisor_streams,
)
from .supervised_protocol import RuntimeReady

_LOGGER = get_logger(__name__)


def _accept_console_interrupts() -> None:
    """Clear an inherited Windows "ignore Ctrl+C" flag so a console stop reaches the drain."""
    if sys.platform != "win32":
        return
    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    # A NULL handler with FALSE restores normal Ctrl+C processing for this
    # process. A launcher that started it in a new process group, or that
    # itself ignored Ctrl+C, would otherwise leave every console stop unseen.
    if not kernel32.SetConsoleCtrlHandler(None, False):
        _LOGGER.warning("runtime could not restore console Ctrl+C processing")


def _supervised_token_refused() -> bool:
    if sys.platform != "win32":
        return False
    return supervised_elevation_refused(current_process_token_elevation_type())


def _configure_runtime_logging(root: Path) -> None:
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
    attach: Callable[[RuntimeTransportServer], None] | None = None,
) -> None:
    try:
        server = RuntimeTransportServer(
            endpoint,
            product_version=installed_version,
            stop=stop,
            profiles=profiles,
            boot_id=boot_id,
            authority_generation=published_authority_generation(),
        )
        if attach is not None:
            attach(server)
        server.serve()
    except RuntimeShutdownIncompleteError:
        # Never release the owner lock while callbacks, constructors or
        # uncontained descendants still belong to this runtime.
        terminate_runtime(RuntimeExitReason.DRAIN_WATCHDOG)


def _serve_runtime_endpoint(
    options: argparse.Namespace,
    root: Path,
    endpoint: WindowsRuntimeEndpoint | PosixRuntimeEndpoint,
    installed_version: str,
    stop: RuntimeStop,
    previous: Mapping[signal.Signals, Any],
    supervision: SupervisedRuntime | None,
) -> None:
    if endpoint.storage_identity != options.storage_identity:
        raise RuntimeRefusalError(RuntimeRefusalCode.ROOT_MISMATCH)
    _configure_runtime_logging(root)
    for number in previous:
        signal.signal(number, lambda _number, _frame: stop.request(RuntimeExitReason.SIGNAL_STOP))
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
        os_owner_id=endpoint.os_owner_id if isinstance(endpoint, WindowsRuntimeEndpoint) else str(posix_owner_uid()),
    )
    attach = None
    publication = None
    if supervision is not None:
        ready = RuntimeReady(
            boot_id=boot_id,
            pid=os.getpid(),
            version=installed_version,
            storage_identity=endpoint.storage_identity,
            admission=login_policy.admission,
        )
        publication = RuntimeBootRecordPublication(
            storage_root=root,
            record=current_runtime_boot_record(
                boot_id=boot_id, version=installed_version, admission=login_policy.admission
            ),
        )
        attach = partial(supervision.attach, profiles=profiles, ready=ready, publish_boot_record=publication.publish)
    with startup_phase(_LOGGER, "registry_prepare"):
        profiles.prepare_registry()
    with RuntimeShutdownWatchdog(stop, timeout=RuntimeTransportServer.DRAIN_SECONDS + 2):
        try:
            _serve_transport(endpoint, installed_version, stop, profiles, boot_id, attach)
        finally:
            if publication is not None:
                _withdraw_boot_record(publication)


def _withdraw_boot_record(publication: RuntimeBootRecordPublication) -> None:
    try:
        publication.withdraw()
    except RuntimeRefusalError as error:
        # A record left behind names a dead process, which adoption refuses.
        _LOGGER.warning("runtime boot record was not removed", exc_info=error)


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


def _run_runtime_owner(
    options: argparse.Namespace,
    stop: RuntimeStop,
    previous: Mapping[signal.Signals, Any],
    supervision: SupervisedRuntime | None,
) -> RuntimeExitReason:
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
        _serve_runtime_endpoint(options, root, endpoint, installed_version, stop, previous, supervision)
    except BaseException as error:
        primary_errors.append(error)
        raise
    finally:
        _release_runtime_endpoint(endpoint, owner, primary_errors)
    # Serving returns only after a stop; a stop that named no reason is a defect.
    return stop.reason or RuntimeExitReason.UNEXPECTED_FAILURE


def run(options: argparse.Namespace) -> int:
    """Run one user/root owner with independent profile admission; return its exit reason code."""
    with diagnostic_process("runtime"), diagnostic_scope():
        diagnostic_event(_LOGGER, "runtime_process_started")
        try:
            exit_code = _run_process(options)
        except BaseException as error:
            diagnostic_event(
                _LOGGER,
                "runtime_process_failed",
                fields={
                    **diagnostic_error_fields(error),
                    "outcome": "failed",
                    "reason_code": "unexpected_runtime_failure",
                },
                level=40,
                primary_error=error,
            )
            raise
        diagnostic_event(
            _LOGGER,
            "runtime_process_exited",
            fields={"exit_code": exit_code, "outcome": "exited"},
        )
        return exit_code


def _run_process(options: argparse.Namespace) -> int:
    _accept_console_interrupts()
    stop = RuntimeStop()
    if not options.supervised:
        return _run_runtime(options, stop, None)
    # The manager's console stop must reach this process alone.
    isolate_child_consoles()
    exit_code = int(RuntimeExitReason.UNEXPECTED_FAILURE)
    supervision: SupervisedRuntime | None = None
    try:
        # Take the launch streams before anything can start a child process.
        supervision = SupervisedRuntime(stop, SupervisorChannel(take_supervisor_streams(), logger=_LOGGER))
        route_diagnostics_to_redacted_logging(_LOGGER)
        supervision.start()
        if _supervised_token_refused():
            # Refused before the endpoint is claimed; the supervisor stands down on this reason.
            _LOGGER.error("supervised runtime refused a full UAC-elevated token")
            exit_code = int(RuntimeExitReason.ELEVATED_TOKEN_REFUSED)
        else:
            exit_code = _run_runtime(options, stop, supervision)
    except Exception as error:
        # The supervisor receives only the reason code; the redacted log keeps the cause.
        _LOGGER.error("supervised runtime ended by an unexpected failure", exc_info=error)
    if supervision is not None:
        supervision.finish(exit_code)
    return exit_code


def _run_runtime(options: argparse.Namespace, stop: RuntimeStop, supervision: SupervisedRuntime | None) -> int:
    previous = {number: signal.getsignal(number) for number in (signal.SIGINT, signal.SIGTERM)}
    try:
        return int(_run_runtime_owner(options, stop, previous, supervision))
    except RuntimeRefusalError as error:
        diagnostic_event(
            _LOGGER,
            "runtime_owner_refused",
            fields={**diagnostic_error_fields(error), "reason_code": error.reason.value, "outcome": "refused"},
            level=30,
            primary_error=error,
        )
        if sys.platform == "win32" and has_async_cleanup_failure(error):
            raise
        sys.stderr.write(error.reason.value + "\n")
        return int(runtime_refusal_exit_reason(error.reason))
    except KeyboardInterrupt as error:
        if sys.platform == "win32" and has_async_cleanup_failure(error):
            raise
        return int(RuntimeExitReason.SIGNAL_STOP)
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)
