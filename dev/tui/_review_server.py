"""Run and stop the local TUI review HTTP server and its catalogue watcher."""

from __future__ import annotations

import socket
import sys
import threading
from functools import partial
from http.server import ThreadingHTTPServer

from ._review_requests import ReviewRequestHandler
from ._review_server_contracts import WATCH_INTERVAL_SECONDS
from ._review_state import ReviewState


class ReviewHTTPServer(ThreadingHTTPServer):
    """One thread per connection; event streams must not hold up shutdown."""

    daemon_threads = True
    # On Windows SO_REUSEADDR lets a second server bind a port already in use
    # and steal half its connections, so a clash must fail loudly instead.
    allow_reuse_address = sys.platform != "win32"

    def __init__(self, address: tuple[str, int], state: ReviewState) -> None:
        """Listen on ``address`` and answer every request against ``state``."""
        if ":" in address[0]:
            self.address_family = socket.AF_INET6
        super().__init__(address, partial(ReviewRequestHandler, state=state))
        self.state = state


def serve(server: ReviewHTTPServer, *, interval: float = WATCH_INTERVAL_SECONDS) -> None:
    """Watch the runs and answer requests until interrupted."""
    watcher = threading.Thread(target=server.state.watch, args=(interval,), name="tui-review-watch", daemon=True)
    watcher.start()
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        server.state.stop()
        server.server_close()
        watcher.join(timeout=interval * 2)
