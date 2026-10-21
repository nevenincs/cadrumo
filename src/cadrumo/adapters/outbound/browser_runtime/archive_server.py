"""A loopback download host that offers the vendor installer only archives Cadrumo has verified.

The vendor installer still downloads, extracts and marks each build in turn, so
the cache keeps exactly the layout the bundled Playwright launches from and a
build finished before an interruption stays finished. Its download host is
pointed here. A request for a pinned path fetches and verifies that archive the
first time it is asked for (see :mod:`.archive_fetch`) and serves the verified
copy; any other request is answered ``404``. A fetch that failed is answered
``502`` on every later request rather than tried again behind the setup's own
retry policy, and the failure is kept for the run to report.

Every response is hashed as it is sent and its final chunk is held back until
the bytes sent hash to the pin; on a mismatch the connection is dropped short,
so the installer sees a truncated download and extracts nothing.
"""

from __future__ import annotations

import hashlib
import socket
import threading
from collections.abc import Callable, Sequence
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import TracebackType
from typing import Final, Self, override
from urllib.parse import urlsplit

from ....application.browser_archive_pins import BrowserArchivePin
from ....application.dependency_transfer import DependencyTransferError
from ....core.errors.hierarchy import InternalInvariantError

__all__ = ["ArchiveFetcher", "VerifiedArchiveServer"]

_CHUNK_BYTES: Final = 1024 * 1024
_LOOPBACK: Final = "127.0.0.1"

#: Downloads one pinned archive and returns the file that matched it, or raises the classified failure.
type ArchiveFetcher = Callable[[BrowserArchivePin], Path]


class _Archive:
    """One pinned archive: fetched at most once, then either its verified file or why it failed."""

    def __init__(self, pin: BrowserArchivePin) -> None:
        self.pin = pin
        self.lock = threading.Lock()
        self.path: Path | None = None
        self.failure: DependencyTransferError | None = None


class _Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, pins: Sequence[BrowserArchivePin], fetch: ArchiveFetcher) -> None:
        super().__init__((_LOOPBACK, 0), _Handler)
        self.archives = {f"/{pin.path}": _Archive(pin) for pin in pins}
        self.fetch = fetch
        self.lock = threading.Lock()
        self.refused = 0
        self.mismatched = 0
        self.failure: DependencyTransferError | None = None

    def count(self, *, refused: int = 0, mismatched: int = 0) -> None:
        with self.lock:
            self.refused += refused
            self.mismatched += mismatched

    def staged(self, archive: _Archive) -> Path | None:
        """Return the verified file for ``archive``, fetching it the first time; ``None`` once it failed."""
        with archive.lock:
            if archive.path is None and archive.failure is None:
                try:
                    archive.path = self.fetch(archive.pin)
                except DependencyTransferError as failure:
                    archive.failure = failure
                    with self.lock:
                        self.failure = self.failure or failure
            return archive.path


class _Handler(BaseHTTPRequestHandler):
    def _host(self) -> _Server:
        if not isinstance(self.server, _Server):
            raise InternalInvariantError("an archive request reached a server that holds no archives")
        return self.server

    def do_GET(self) -> None:
        host = self._host()
        archive = host.archives.get(urlsplit(self.path).path)
        if archive is None:
            host.count(refused=1)
            self.send_error(404)
            return
        path = host.staged(archive)
        if path is None:
            self.send_error(502)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Length", str(archive.pin.download_bytes))
        self.end_headers()
        if not self._send_verified(archive.pin, path):
            host.count(mismatched=1)
            self.close_connection = True
            self.connection.shutdown(socket.SHUT_RDWR)

    def _send_verified(self, pin: BrowserArchivePin, path: Path) -> bool:
        """Send the file, keeping its last chunk back until everything read hashes to the pin."""
        digest = hashlib.sha256()
        sent = 0
        held = b""
        with path.open("rb") as file:
            while chunk := file.read(_CHUNK_BYTES):
                if held:
                    self.wfile.write(held)
                    sent += len(held)
                digest.update(chunk)
                held = chunk
        if sent + len(held) != pin.download_bytes or digest.hexdigest() != pin.sha256:
            return False
        self.wfile.write(held)
        return True

    @override
    def log_message(self, format: str, *args: object) -> None:
        del format, args


class VerifiedArchiveServer:
    """Serves pinned archives on a loopback port, fetching each on first request, while the context is open."""

    def __init__(self, pins: Sequence[BrowserArchivePin], fetch: ArchiveFetcher) -> None:
        """Bind a loopback port that answers each pin's path and nothing else."""
        self._server = _Server(pins, fetch)
        self._thread = threading.Thread(target=self._server.serve_forever, name="browser-archive-server", daemon=True)

    @property
    def origin(self) -> str:
        """The download host the vendor installer is given."""
        host, port = self._server.server_address[:2]
        return f"http://{host!s}:{port}"

    @property
    def refused(self) -> int:
        """Requests for anything other than a pinned path."""
        return self._server.refused

    @property
    def mismatched(self) -> int:
        """Responses cut short because the staged file no longer matched its pin."""
        return self._server.mismatched

    @property
    def failure(self) -> DependencyTransferError | None:
        """The first fetch that failed, if any did."""
        return self._server.failure

    def __enter__(self) -> Self:
        """Start answering requests."""
        self._thread.start()
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, traceback: TracebackType | None
    ) -> None:
        """Stop answering and release the port."""
        self._server.shutdown()
        self._server.server_close()
        self._thread.join()
