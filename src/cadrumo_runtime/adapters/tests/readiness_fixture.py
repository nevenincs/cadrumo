"""Finite synthetic runtime for native launch-door and cancellation tests."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from threading import Timer
from uuid import uuid4

from cadrumo_client.contracts.contracts import ClientHello, RefusalCode, RefusalError, ServerHello
from cadrumo_client.transport.frame_io import read_document, write_document
from cadrumo_client.transport.posix_endpoint import PosixEndpoint
from cadrumo_client.transport.windows import WindowsEndpoint
from cadrumo_runtime.adapters.connection_handshake import accept_connection_handshake


def main() -> None:
    """Serve only nonsecret handshakes under a hard, independent lifetime bound."""
    lifetime = Timer(35, os._exit, args=(124,))
    lifetime.daemon = True
    lifetime.start()
    root, namespace = Path(sys.argv[1]), Path(sys.argv[2])
    version, mode = sys.argv[3:]
    endpoint = (
        WindowsEndpoint(storage_root=root)
        if sys.platform == "win32"
        else PosixEndpoint(storage_root=root, namespace=namespace)
    )
    identity = ServerHello(product_version=version, storage_identity=endpoint.storage_identity, boot_id=uuid4())
    try:
        endpoint.listen()
        print("ready", flush=True)
        while True:
            try:
                channel = endpoint.accept(timeout=2)
            except RefusalError as error:
                if error.reason is RefusalCode.DEADLINE_EXCEEDED:
                    continue
                raise
            try:
                if mode == "blocked":
                    read_document(channel, ClientHello, deadline=time.monotonic() + 5)
                    print("handshake", flush=True)
                    assert sys.stdin.readline() == "release\n"
                    write_document(channel, identity, deadline=time.monotonic() + 3)
                    try:
                        channel.read_exact(1, deadline=time.monotonic() + 3)
                    except RefusalError as error:
                        assert error.reason is RefusalCode.CONNECTION_CLOSED
                        print("late_closed", flush=True)
                    else:
                        raise AssertionError("unexpected data after cancelled readiness")
                    mode = "normal"
                else:
                    accept_connection_handshake(channel, identity=identity, deadline=time.monotonic() + 3)
            except RefusalError as error:
                if error.reason not in (RefusalCode.VERSION_MISMATCH, RefusalCode.CONNECTION_CLOSED):
                    raise
            finally:
                channel.close()
    finally:
        endpoint.close()
        lifetime.cancel()


if __name__ == "__main__":
    main()
