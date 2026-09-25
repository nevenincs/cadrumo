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


class _ConcurrentHTTPServer(socketserver.ThreadingTCPServer):
    """A static server that answers overlapping requests instead of queueing them.

    Concurrency is load-bearing here, not a nicety. Pagefind's search worker
    fetches its metadata, wasm, index chunks and result fragments in parallel,
    and the browser holds several connections open to do it. A serial
    ``TCPServer`` accepts one of them and leaves the rest in the listen backlog
    until the in-flight response completes; the browser gives up on the queued
    connections and the worker surfaces the failure as a bare ``Failed to
    fetch``, which reads like a defect in the built index rather than in the
    fixture serving it.

    ``daemon_threads`` keeps a wedged request handler from outliving the test,
    and ``block_on_close`` stays at its threading default so shutdown still
    joins live handlers.
    """

    daemon_threads = True
    allow_reuse_address = True


@contextmanager
def serve_directory(directory: Path) -> Generator[tuple[socketserver.TCPServer, int]]:
    """Serve ``directory`` over HTTP on an ephemeral loopback port.

    Yields the running server and the port it bound. The server always shuts
    down cleanly on exit -- including on an exception inside the ``with``
    block -- by stopping the serve loop, closing the listening socket, and
    joining the serving thread, so no server thread or socket outlives a test.
    """
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    httpd = _ConcurrentHTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd, port
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)
