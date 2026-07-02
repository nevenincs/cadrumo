"""Local Drive media endpoint for google-api-python-client request tests."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import urlparse

from googleapiclient.discovery import build_from_document

from .._document_link_resolver import _DriveService


@dataclass(frozen=True)
class DriveMediaEndpoint:
    service: _DriveService
    requested_paths: list[str]


@contextmanager
def drive_media_endpoint(*, payload: bytes, status: int = 200) -> Iterator[DriveMediaEndpoint]:
    """Serve Drive media bytes through a real google-api-python-client resource."""
    requested_paths: list[str] = []

    class DriveMediaRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            requested_paths.append(self.path)
            self.send_response(status)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            return

    with ThreadingHTTPServer(("127.0.0.1", 0), DriveMediaRequestHandler) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            root_url = f"http://127.0.0.1:{server.server_port}/"
            service = build_from_document(
                json.dumps(_drive_media_discovery_document(root_url=root_url)),
                credentials=None,
            )
            yield DriveMediaEndpoint(service=service, requested_paths=requested_paths)
        finally:
            server.shutdown()
            thread.join(timeout=2)


@dataclass(frozen=True)
class DriveFilesListEndpoint:
    service: _DriveService
    requested_queries: list[str] = field(default_factory=list)


@contextmanager
def drive_files_list_endpoint(
    *,
    pages: list[dict[str, object]],
    status: int = 200,
) -> Iterator[DriveFilesListEndpoint]:
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

        def log_message(self, format: str, *args: object) -> None:
            return

    with ThreadingHTTPServer(("127.0.0.1", 0), DriveFilesListRequestHandler) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            root_url = f"http://127.0.0.1:{server.server_port}/"
            service = build_from_document(
                json.dumps(_drive_files_list_discovery_document(root_url=root_url)),
                credentials=None,
            )
            yield DriveFilesListEndpoint(service=service, requested_queries=requested_queries)
        finally:
            server.shutdown()
            thread.join(timeout=2)


def _drive_media_discovery_document(*, root_url: str) -> dict[str, object]:
    return {
        "kind": "discovery#restDescription",
        "discoveryVersion": "v1",
        "id": "drive:v3",
        "name": "drive",
        "version": "v3",
        "title": "Drive API",
        "rootUrl": root_url,
        "servicePath": "drive/v3/",
        "baseUrl": f"{root_url}drive/v3/",
        "basePath": "/drive/v3/",
        "batchPath": "batch/drive/v3",
        "schemas": {
            "File": {
                "id": "File",
                "type": "object",
            },
        },
        "resources": {
            "files": {
                "methods": {
                    "get": {
                        "id": "drive.files.get",
                        "path": "files/{fileId}",
                        "flatPath": "files/{fileId}",
                        "httpMethod": "GET",
                        "parameterOrder": ["fileId"],
                        "parameters": {
                            "fileId": {
                                "type": "string",
                                "required": True,
                                "location": "path",
                            },
                        },
                        "response": {"$ref": "File"},
                        "supportsMediaDownload": True,
                        "useMediaDownloadService": True,
                        "scopes": ["https://www.googleapis.com/auth/drive.file"],
                    },
                },
            },
        },
    }


def _drive_files_list_discovery_document(*, root_url: str) -> dict[str, object]:
    return {
        "kind": "discovery#restDescription",
        "discoveryVersion": "v1",
        "id": "drive:v3",
        "name": "drive",
        "version": "v3",
        "title": "Drive API",
        "rootUrl": root_url,
        "servicePath": "drive/v3/",
        "baseUrl": f"{root_url}drive/v3/",
        "basePath": "/drive/v3/",
        "batchPath": "batch/drive/v3",
        "schemas": {
            "FileList": {
                "id": "FileList",
                "type": "object",
            },
        },
        "resources": {
            "files": {
                "methods": {
                    "list": {
                        "id": "drive.files.list",
                        "path": "files",
                        "flatPath": "files",
                        "httpMethod": "GET",
                        "parameters": {
                            "q": {"type": "string", "location": "query"},
                            "fields": {"type": "string", "location": "query"},
                            "pageSize": {"type": "integer", "location": "query"},
                            "pageToken": {"type": "string", "location": "query"},
                        },
                        "response": {"$ref": "FileList"},
                        "scopes": ["https://www.googleapis.com/auth/drive.file"],
                    },
                },
            },
        },
    }
