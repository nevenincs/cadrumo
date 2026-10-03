"""Compose native runtime ownership and bounded public transport readiness."""

from __future__ import annotations

import argparse
import signal
import sys
from collections.abc import Callable
from contextlib import ExitStack
from functools import partial
from importlib.metadata import version
from pathlib import Path
from threading import Event
from uuid import uuid4

from cadrumo.adapters.local_runtime.runtime_manager_composition import installed_runtime_binding

from ...adapters.local_runtime.linux_login import linux_login_inventory
from ...adapters.local_runtime.linux_managed_stop import LinuxManagedRuntimeStop
from ...adapters.local_runtime.posix import PosixRuntimeEndpoint, posix_owner_uid
from ...adapters.local_runtime.server import RuntimeTransportServer
from ...adapters.local_runtime.windows import WindowsRuntimeEndpoint
from ...adapters.local_runtime.windows_login import windows_login_inventory
from ...adapters.local_runtime.windows_managed_stop import WindowsManagedRuntimeStop
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError, RuntimeShutdownIncompleteError
from ...application.runtime.login import RuntimeLoginInventory
from .profile_connections import RuntimeProfileConnections
from .shutdown import RuntimeShutdownWatchdog, terminate_runtime


def run(arguments: list[str] | None = None) -> int:
    """Run one user/root owner; a manager argument never grants profile authority."""
    parser = argparse.ArgumentParser(prog="cadrumo-runtime", allow_abbrev=False)
    parser.add_argument("--storage-root", required=True, type=Path)
    parser.add_argument("--storage-identity", required=True)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--managed-session", action="store_true")
    options = parser.parse_args(arguments)
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
        try:
            if endpoint.storage_identity != options.storage_identity:
                raise RuntimeRefusalError(RuntimeRefusalCode.ROOT_MISMATCH)
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
                    binding = installed_runtime_binding(root=root, endpoint=endpoint, product_version=installed_version)
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
        finally:
            endpoint.close()
        return 0
    except RuntimeRefusalError as error:
        sys.stderr.write(error.reason.value + "\n")
        return 2
    except KeyboardInterrupt:
        return 0
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)
