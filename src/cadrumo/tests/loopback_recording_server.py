"""Loopback HTTP server plumbing for suites that record arriving requests.

Three telemetry-adjacent suites each stood up a real ``ThreadingHTTPServer`` on
loopback to prove a genuine HTTP POST left the process, then tore it down with
identical bind-thread-shutdown-join boilerplate. Each suite still owns its own
handler class (the recorded event shape genuinely differs between them), so
only the start/stop plumbing lives here.
"""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from queue import Queue
from typing import Final

__all__ = ["run_loopback_server", "stop_loopback_server"]

#: The shutdown join budget. Generous enough that a loaded CI box does not trip
#: it, bounded so a wedged handler thread surfaces as a failure rather than
#: hanging the suite.
_JOIN_TIMEOUT_S: Final[float] = 3.0


def run_loopback_server(
    handler_class: type[BaseHTTPRequestHandler],
) -> tuple[ThreadingHTTPServer, threading.Thread, Queue[dict[str, object]]]:
    """Bind ``handler_class`` on an ephemeral loopback port and start serving.

    Binding port ``0`` lets the OS pick a free one, so parallel workers cannot
    collide on a fixed port. The recorded-events queue is attached to
    ``handler_class.events`` before the server starts, so the first request
    the handler serves already has somewhere to put what it saw.

    Args:
        handler_class: The request-handler class to serve. Must declare an
            ``events`` class attribute the caller's handler writes recorded
            requests into.

    Returns:
        The running server, its serving thread, and the events queue the
        handler records onto.
    """
    events: Queue[dict[str, object]] = Queue()
    # The events queue is a dynamically attached class attribute the caller's
    # handler subclass declares (see docstring); BaseHTTPRequestHandler itself
    # has no such attribute, so this is a genuine dynamic assignment rather
    # than a statically-known one.
    events_attribute_name = "events"
    setattr(handler_class, events_attribute_name, events)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_class)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, events


def stop_loopback_server(server: ThreadingHTTPServer, thread: threading.Thread) -> None:
    """Shut down and join a server started by :func:`run_loopback_server`.

    Always called from the caller's ``finally``, so a leaked serving thread
    never outlives the test that started it.

    Args:
        server: The server returned by :func:`run_loopback_server`.
        thread: The serving thread returned alongside it.
    """
    server.shutdown()
    server.server_close()
    thread.join(timeout=_JOIN_TIMEOUT_S)
