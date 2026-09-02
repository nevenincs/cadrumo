"""Shared ephemeral-port HTTP server for the browser-driven docs gates.

Underscore-prefixed so it is never collected as a test module. Every gate that
drives a real browser against a built docs tree needs the same throwaway
static-file server; this is the one definition, consolidated from five
byte-identical copies that had drifted apart only in name.
"""

from __future__ import annotations

import http.server
import socketserver
import threading
from collections.abc import Generator
from contextlib import contextmanager
from functools import partial
from pathlib import Path


@contextmanager
def serve_directory(directory: Path) -> Generator[tuple[socketserver.TCPServer, int]]:
    """Serve ``directory`` over HTTP on an ephemeral loopback port.

    Yields the running server and the port it bound. The server always shuts
    down cleanly on exit -- including on an exception inside the ``with``
    block -- by stopping the serve loop, closing the listening socket, and
    joining the serving thread, so no server thread or socket outlives a test.
    """
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd, port
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)
