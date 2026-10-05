"""Local Drive ``files`` endpoint holding a small in-memory tree.

Serves ``files.list``, ``files.get`` and ``files.create`` to a real
google-api-python-client resource, so a test can watch what a find-or-create
sequence sends and leaves behind without any Drive network traffic.
"""

from __future__ import annotations

import json
import re
from collections.abc import Generator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import TYPE_CHECKING, override
from urllib.parse import parse_qs, urlparse

import httplib2
from googleapiclient.discovery import build

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3.resources import DriveResource

_OWNED_ENTRY_QUERY = re.compile(
    r"^'(?P<parent>[^']*)' in parents and name = '(?P<name>[^']*)' "
    r"and mimeType = '(?P<mime>[^']*)' and trashed = false$"
)


@dataclass(frozen=True)
class DriveFilesEndpoint:
    service: DriveResource
    entries: list[dict[str, object]] = field(default_factory=list)
    created_bodies: list[dict[str, object]] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)


@contextmanager
def drive_files_endpoint(*, entries: Sequence[Mapping[str, object]] = ()) -> Generator[DriveFilesEndpoint]:
    """Serve Drive ``files`` calls over ``entries``, recording every call and created body."""
    stored: list[dict[str, object]] = [dict(entry) for entry in entries]
    created_bodies: list[dict[str, object]] = []
    calls: list[str] = []

    class DriveFilesRequestHandler(BaseHTTPRequestHandler):
        def _reply(self, status: int, document: Mapping[str, object]) -> None:
            body = json.dumps(dict(document)).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path.rstrip("/").endswith("/files"):
                calls.append("files.list")
                matched = _OWNED_ENTRY_QUERY.match(parse_qs(parsed.query).get("q", [""])[0])
                found = (
                    [
                        entry
                        for entry in stored
                        if matched["parent"] in _parents(entry)
                        and entry.get("name") == matched["name"]
                        and entry.get("mimeType") == matched["mime"]
                        and entry.get("trashed") is not True
                    ]
                    if matched is not None
                    else []
                )
                self._reply(200, {"files": found})
                return
            calls.append("files.get")
            file_id = parsed.path.rsplit("/", maxsplit=1)[-1]
            entry = next((item for item in stored if item.get("id") == file_id), None)
            if entry is None:
                self._reply(404, {"error": {"code": 404, "message": f"File not found: {file_id}."}})
                return
            self._reply(200, entry)

        def do_POST(self) -> None:
            calls.append("files.create")
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            created_bodies.append(body)
            created = {"id": f"created-{len(created_bodies)}", **body}
            stored.append(created)
            self._reply(200, created)

        @override
        def log_message(self, format: str, *args: object) -> None:
            return

    with ThreadingHTTPServer(("127.0.0.1", 0), DriveFilesRequestHandler) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        transport = httplib2.Http()
        try:
            service = build(
                "drive",
                "v3",
                http=transport,
                cache_discovery=False,
                client_options={"api_endpoint": f"http://127.0.0.1:{server.server_port}/drive/v3/"},
            )
            yield DriveFilesEndpoint(service=service, entries=stored, created_bodies=created_bodies, calls=calls)
        finally:
            transport.close()
            server.shutdown()
            thread.join(timeout=2)


def _parents(entry: Mapping[str, object]) -> tuple[object, ...]:
    parents = entry.get("parents")
    return tuple(parents) if isinstance(parents, list) else ()
