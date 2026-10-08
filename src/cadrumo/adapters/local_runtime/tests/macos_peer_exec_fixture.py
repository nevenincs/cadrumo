"""One bounded synthetic Unix peer executes a fresh interpreter on command."""

from __future__ import annotations

import os
import socket
import sys


def _unix_channel() -> socket.socket:
    if sys.platform != "win32":
        return socket.socket(socket.AF_UNIX)
    raise RuntimeError("requires native Unix socket")


def main() -> int:
    if sys.platform == "win32" or len(sys.argv) not in (2, 3):
        return 2
    if len(sys.argv) == 2:
        with _unix_channel() as channel:
            channel.settimeout(5)
            channel.connect(sys.argv[1])
            channel.sendall(b"ready")
            if channel.recv(8) != b"exec":
                return 2
            os.set_inheritable(channel.fileno(), True)
            os.execv(  # noqa: S606 - fixed isolated interpreter and owning synthetic fixture
                sys.executable, [sys.executable, "-I", __file__, sys.argv[1], str(channel.fileno())]
            )
    with socket.socket(fileno=int(sys.argv[2])) as channel:
        channel.settimeout(5)
        channel.sendall(b"again")
        return 0 if channel.recv(8) == b"done" else 2


if __name__ == "__main__":
    raise SystemExit(main())
