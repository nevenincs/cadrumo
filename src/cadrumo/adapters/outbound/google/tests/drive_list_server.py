"""Local Drive ``files.list`` endpoint for google-api-python-client request tests."""

from __future__ import annotations

import json
from collections.abc import Generator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import override
from urllib.parse import urlparse

import httplib2
from googleapiclient.discovery import build


@dataclass(frozen=True)
class DriveFilesListEndpoint:
    service: object
    requested_queries: list[str] = field(default_factory=list)


@contextmanager
def drive_files_list_endpoint(
    *,
    pages: Sequence[Mapping[str, object]],
    status: int = 200,
) -> Generator[DriveFilesListEndpoint]:
    """Serve ``files.list`` responses (optionally paginated) through a real client resource.

    ``pages`` is served in order, one JSON body per ``files.list`` call —
    supporting a ``nextPageToken``-driven pagination test without any real
    Drive network traffic.
    """
    requested_queries: list[str] = []
    remaining_pages = list(pages)

    class DriveFilesListRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            requested_queries.append(parsed.query)
            body = json.dumps(remaining_pages.pop(0) if remaining_pages else {"files": []}).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        @override
        def log_message(self, format: str, *args: object) -> None:
            return

    with ThreadingHTTPServer(("127.0.0.1", 0), DriveFilesListRequestHandler) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        transport = httplib2.Http()
        try:
            root_url = f"http://127.0.0.1:{server.server_port}/"
            service = build(
                "drive",
                "v3",
                http=transport,
                cache_discovery=False,
                client_options={"api_endpoint": f"{root_url}drive/v3/"},
            )
            yield DriveFilesListEndpoint(service=service, requested_queries=requested_queries)
        finally:
            transport.close()
            server.shutdown()
            thread.join(timeout=2)
