"""Compose native runtime ownership and bounded public transport readiness."""

from __future__ import annotations

import argparse
import signal
import sys
from importlib.metadata import version
from pathlib import Path
from threading import Event
from uuid import uuid4

from ...adapters.local_runtime.posix import PosixRuntimeEndpoint
from ...adapters.local_runtime.server import RuntimeTransportServer
from ...adapters.local_runtime.windows import WindowsRuntimeEndpoint
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from .profile_connections import RuntimeProfileConnections


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
            profiles = RuntimeProfileConnections(
                storage_root=root,
                storage_identity=endpoint.storage_identity,
                runtime_boot_id=boot_id,
                stop=stop,
            )
            RuntimeTransportServer(
                endpoint, product_version=installed_version, stop=stop, profiles=profiles, boot_id=boot_id
            ).serve()
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
