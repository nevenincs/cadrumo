"""Finite synthetic runtime for native launch-door and cancellation tests."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from threading import Timer
from uuid import uuid4

from cadrumo.application.runtime.contracts import (
    RuntimeClientHello,
    RuntimeRefusalCode,
    RuntimeRefusalError,
    RuntimeServerHello,
)

from ..framing import accept_runtime_handshake
from ..posix_endpoint import PosixRuntimeEndpoint
from ..runtime_frame_io import read_document, write_document
from ..windows import WindowsRuntimeEndpoint


def main() -> None:
    """Serve only nonsecret handshakes under a hard, independent lifetime bound."""
    lifetime = Timer(35, os._exit, args=(124,))
    lifetime.daemon = True
    lifetime.start()
    root, namespace = Path(sys.argv[1]), Path(sys.argv[2])
    version, mode = sys.argv[3:]
    endpoint = (
        WindowsRuntimeEndpoint(storage_root=root)
        if sys.platform == "win32"
        else PosixRuntimeEndpoint(storage_root=root, namespace=namespace)
    )
    identity = RuntimeServerHello(product_version=version, storage_identity=endpoint.storage_identity, boot_id=uuid4())
    try:
        endpoint.listen()
        print("ready", flush=True)
        while True:
            try:
                channel = endpoint.accept(timeout=2)
            except RuntimeRefusalError as error:
                if error.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED:
                    continue
                raise
            try:
                if mode == "blocked":
                    read_document(channel, RuntimeClientHello, deadline=time.monotonic() + 5)
                    print("handshake", flush=True)
                    assert sys.stdin.readline() == "release\n"
                    write_document(channel, identity, deadline=time.monotonic() + 3)
                    try:
                        channel.read_exact(1, deadline=time.monotonic() + 3)
                    except RuntimeRefusalError as error:
                        assert error.reason is RuntimeRefusalCode.CONNECTION_CLOSED
                        print("late_closed", flush=True)
                    else:
                        raise AssertionError("unexpected data after cancelled readiness")
                    mode = "normal"
                else:
                    accept_runtime_handshake(channel, identity=identity, deadline=time.monotonic() + 3)
            except RuntimeRefusalError as error:
                if error.reason not in (RuntimeRefusalCode.VERSION_MISMATCH, RuntimeRefusalCode.CONNECTION_CLOSED):
                    raise
            finally:
                channel.close()
    finally:
        endpoint.close()
        lifetime.cancel()


if __name__ == "__main__":
    main()
