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
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import TYPE_CHECKING, Any, override
from urllib.parse import parse_qs, urlparse

import httplib2
from googleapiclient.discovery import build
from googleapiclient.http import HttpRequest

from .....core.type_guards import is_str_keyed_dict

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
    payloads: dict[str, bytes] = field(default_factory=dict)
    create_statuses: list[int] = field(default_factory=list)
    update_queries: list[dict[str, list[str]]] = field(default_factory=list)
    update_statuses: list[int] = field(default_factory=list)


@contextmanager
def drive_files_endpoint(
    *, entries: Sequence[Mapping[str, object]] = (), create_status: int = 200
) -> Generator[DriveFilesEndpoint]:
    """Serve Drive ``files`` calls over ``entries``, recording every call and created body."""
    stored: list[dict[str, object]] = [dict(entry) for entry in entries]
    created_bodies: list[dict[str, object]] = []
    calls: list[str] = []
    payloads: dict[str, bytes] = {}

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
            if parsed.path.endswith("/generateIds"):
                calls.append("files.generateIds")
                self._reply(200, {"ids": [f"generated-{len(created_bodies) + 1}"]})
                return
            if parsed.path.rstrip("/").endswith("/files"):
                calls.append("files.list")
                query = parse_qs(parsed.query).get("q", [""])[0]
                matched = _OWNED_ENTRY_QUERY.match(query)
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
                    else _matching_entries(stored, query)
                )
                self._reply(200, {"files": found})
                return
            media = parse_qs(parsed.query).get("alt") == ["media"]
            calls.append("files.get_media" if media else "files.get")
            file_id = parsed.path.rsplit("/", maxsplit=1)[-1]
            if file_id == "root":
                self._reply(404, {"error": {"code": 404, "message": "My Drive is not readable with drive.file."}})
                return
            entry = next((item for item in stored if item.get("id") == file_id), None)
            if entry is None:
                self._reply(404, {"error": {"code": 404, "message": f"File not found: {file_id}."}})
                return
            if media:
                body = payloads.get(file_id, b"")
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self._reply(200, entry)

        def _body(self) -> tuple[dict[str, object], bytes | None]:
            raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            content_type = self.headers.get("Content-Type", "")
            if content_type.startswith("multipart/"):
                message = BytesParser(policy=default).parsebytes(f"Content-Type: {content_type}\r\n\r\n".encode() + raw)
                parts = tuple(message.iter_parts())
                metadata = parts[0].get_payload(decode=True)
                payload = parts[1].get_payload(decode=True)
                assert isinstance(metadata, bytes) and isinstance(payload, bytes)
                document: object = json.loads(metadata)
                assert is_str_keyed_dict(document)
                return document, payload
            document = json.loads(raw or b"{}")
            assert is_str_keyed_dict(document)
            return document, None

        def do_POST(self) -> None:
            calls.append("files.create")
            body, payload = self._body()
            created_bodies.append(body)
            created = {
                "id": f"created-{len(created_bodies)}",
                "trashed": False,
                "ownedByMe": True,
                "modifiedTime": "2026-10-05T12:00:00Z",
                **body,
            }
            stored.append(created)
            if payload is not None:
                payloads[str(created["id"])] = payload
                created["size"] = str(len(payload))
            status = state.create_statuses.pop(0) if state.create_statuses else create_status
            self._reply(status, created if status == 200 else {"error": {"code": status}})

        def do_PATCH(self) -> None:
            calls.append("files.update")
            parsed = urlparse(self.path)
            identifier = parsed.path.rsplit("/", maxsplit=1)[-1]
            query = parse_qs(parsed.query)
            state.update_queries.append(query)
            entry = next(item for item in stored if item.get("id") == identifier)
            body, payload = self._body()
            entry.update(body)
            removed = set(",".join(query.get("removeParents", [])).split(",")) - {""}
            added = tuple(filter(None, ",".join(query.get("addParents", [])).split(",")))
            if removed or added:
                entry["parents"] = list(
                    dict.fromkeys([parent for parent in _parents(entry) if parent not in removed] + list(added))
                )
            if payload is not None:
                payloads[identifier] = payload
                entry["size"] = str(len(payload))
            status = state.update_statuses.pop(0) if state.update_statuses else 200
            self._reply(status, entry if status == 200 else {"error": {"code": status}})

        def do_DELETE(self) -> None:
            calls.append("files.delete")
            identifier = urlparse(self.path).path.rsplit("/", maxsplit=1)[-1]
            stored[:] = [entry for entry in stored if entry.get("id") != identifier]
            payloads.pop(identifier, None)
            self._reply(200, {})

        @override
        def log_message(self, format: str, *args: object) -> None:
            return

    with ThreadingHTTPServer(("127.0.0.1", 0), DriveFilesRequestHandler) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        transport = httplib2.Http()
        try:

            def local_request(http: Any, postproc: Any, uri: str, *args: Any, **kwargs: Any) -> HttpRequest:
                # The SDK hardcodes HTTPS for multipart uploads even when its
                # discovery endpoint is HTTP. Keep those requests on this fixture.
                uri = uri.replace(f"https://127.0.0.1:{server.server_port}/", f"http://127.0.0.1:{server.server_port}/")
                return HttpRequest(http, postproc, uri, *args, **kwargs)

            service = build(
                "drive",
                "v3",
                http=transport,
                cache_discovery=False,
                requestBuilder=local_request,
                client_options={"api_endpoint": f"http://127.0.0.1:{server.server_port}/drive/v3/"},
            )
            state = DriveFilesEndpoint(
                service=service, entries=stored, created_bodies=created_bodies, calls=calls, payloads=payloads
            )
            yield state
        finally:
            transport.close()
            server.shutdown()
            thread.join(timeout=2)


def _parents(entry: Mapping[str, object]) -> tuple[object, ...]:
    parents = entry.get("parents")
    return tuple(parents) if isinstance(parents, list) else ()


def _matching_entries(entries: list[dict[str, object]], query: str) -> list[dict[str, object]]:
    parent = re.search(r"'([^']+)' in parents", query)
    if parent is None:
        raise AssertionError("fixture refuses account-wide Drive listing")
    name = re.search(r"name\s*=\s*'([^']+)'", query)
    prefix = re.search(r"name contains '([^']+)'", query)
    mime = re.search(r"mimeType\s*=\s*'([^']+)'", query)
    markers = tuple(re.finditer(r"appProperties has \{ key='([^']+)' and value='([^']+)' \}", query))
    return [
        entry
        for entry in entries
        if parent[1] in _parents(entry)
        and entry.get("trashed") is not True
        and (name is None or entry.get("name") == name[1])
        and (prefix is None or str(entry.get("name", "")).startswith(prefix[1]))
        and (mime is None or entry.get("mimeType") == mime[1])
        and (
            not markers
            or (
                is_str_keyed_dict(props := entry.get("appProperties"))
                and all(props.get(marker[1]) == marker[2] for marker in markers)
            )
        )
    ]
