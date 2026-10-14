"""Finite-lived synthetic IPC owner used only by native subprocess tests."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from threading import Timer

from ...contracts.contracts import RefusalCode, RefusalError
from ..posix_endpoint import PosixEndpoint
from ..windows import WindowsEndpoint


def main() -> None:
    """Wait for a launch barrier, claim the test root, then wait for shutdown."""
    lifetime = Timer(20, os._exit, args=(124,))
    lifetime.daemon = True
    lifetime.start()
    root, namespace = map(Path, sys.argv[1:])
    endpoint = (
        WindowsEndpoint(storage_root=root)
        if sys.platform == "win32"
        else PosixEndpoint(storage_root=root, namespace=namespace)
    )
    try:
        print("waiting", flush=True)
        if sys.stdin.readline() != "start\n":
            return
        try:
            endpoint.listen()
        except RefusalError as error:
            if error.reason is not RefusalCode.OWNER_BUSY:
                raise
            print("busy", flush=True)
            return
        print("ready", flush=True)
        sys.stdin.readline()
    finally:
        endpoint.close()
        lifetime.cancel()


if __name__ == "__main__":
    main()
