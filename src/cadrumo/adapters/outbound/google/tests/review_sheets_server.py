"""Local Sheets HTTP state for publication, failure and preserved-note tests."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import TYPE_CHECKING, Any, override
from urllib.parse import parse_qs, unquote, urlparse

import httplib2
from googleapiclient.discovery import build

if TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4.resources import SheetsResource


@dataclass
class ReviewSheetsEndpoint:
    service: SheetsResource
    cells: dict[str, dict[tuple[str, int, int], object]] = field(default_factory=dict)
    tabs: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    calls: list[tuple[str, str]] = field(default_factory=list)
    value_bodies: list[dict[str, Any]] = field(default_factory=list)
    fail_values: bool = False
    read_ranges: list[str] = field(default_factory=list)
    corrupt_baseline: bool = False
    after_values: Callable[[], None] | None = None


@contextmanager
def review_sheets_endpoint() -> Generator[ReviewSheetsEndpoint]:
    """Serve SDK requests over local state without a Google account or credential."""
    state: ReviewSheetsEndpoint

    class Handler(BaseHTTPRequestHandler):
        def _reply(self, status: int, body: object) -> None:
            encoded = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _identity(self) -> tuple[str, str]:
            suffix = unquote(urlparse(self.path).path).split("/spreadsheets/", 1)[1]
            identifier = str(re.split(r"[:/]", suffix, maxsplit=1)[0])
            state.cells.setdefault(identifier, {})
            state.tabs.setdefault(
                identifier,
                {"Sheet1": {"sheetId": 0, "title": "Sheet1", "gridProperties": {"rowCount": 1000, "columnCount": 26}}},
            )
            return identifier, suffix

        def do_GET(self) -> None:
            identifier, suffix = self._identity()
            state.calls.append(("GET", suffix))
            if "values:batchGet" in suffix:
                blocks = []
                for address in parse_qs(urlparse(self.path).query).get("ranges", []):
                    state.read_ranges.append(address)
                    match = re.fullmatch(r"'([^']+)'!([A-Z]+)([0-9]+)", address)
                    if match is not None:
                        column = 0
                        for letter in match[2]:
                            column = column * 26 + ord(letter) - ord("A") + 1
                        value = state.cells[identifier].get((match[1], int(match[3]), column), "")
                        if state.corrupt_baseline:
                            value = "corrupted baseline"
                        blocks.append({"range": address, "values": [[value]]})
                        continue
                    tab = address.split("!", 1)[0].strip("'")
                    selected = {key: value for key, value in state.cells[identifier].items() if key[0] == tab}
                    rows = max((key[1] for key in selected), default=0)
                    cols = max((key[2] for key in selected), default=0)
                    blocks.append(
                        {
                            "range": address,
                            "values": [
                                [selected.get((tab, row, col), "") for col in range(1, cols + 1)]
                                for row in range(1, rows + 1)
                            ],
                        }
                    )
                self._reply(200, {"valueRanges": blocks})
            else:
                self._reply(
                    200,
                    {
                        "spreadsheetId": identifier,
                        "spreadsheetUrl": f"https://docs.google.com/spreadsheets/d/{identifier}/edit",
                        "sheets": [{"properties": props} for props in state.tabs[identifier].values()],
                    },
                )

        def do_POST(self) -> None:
            if self.headers.get("X-HTTP-Method-Override") == "GET":
                # google-api-python-client uses its documented GET override
                # when a batch of exact ranges exceeds the URL length limit.
                query = self.rfile.read(int(self.headers["Content-Length"])).decode()
                self.path += ("&" if "?" in self.path else "?") + query
                self.do_GET()
                return
            identifier, suffix = self._identity()
            state.calls.append(("POST", suffix))
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if "values:batchUpdate" in suffix:
                state.value_bodies.append(body)
                if state.fail_values:
                    self._reply(503, {"error": {"code": 503, "message": "interrupted population"}})
                    return
                for block in body["data"]:
                    match = re.fullmatch(r"'([^']+)'!([A-Z]+)([0-9]+)", block["range"])
                    assert match is not None
                    col = 0
                    for letter in match[2]:
                        col = col * 26 + ord(letter) - ord("A") + 1
                    for dy, row in enumerate(block["values"]):
                        for dx, value in enumerate(row):
                            state.cells[identifier][(match[1], int(match[3]) + dy, col + dx)] = value
                if state.after_values is not None:
                    state.after_values()
                self._reply(200, {"spreadsheetId": identifier})
                return
            replies = []
            for request in body.get("requests", []):
                if "addSheet" in request:
                    props: dict[str, Any] = {
                        "sheetId": len(state.tabs[identifier]),
                        "gridProperties": {"rowCount": 1000, "columnCount": 26},
                        **request["addSheet"]["properties"],
                    }
                    state.tabs[identifier][props["title"]] = props
                    replies.append({"addSheet": {"properties": props}})
                elif "deleteSheet" in request:
                    target = request["deleteSheet"]["sheetId"]
                    state.tabs[identifier] = {
                        title: props for title, props in state.tabs[identifier].items() if props["sheetId"] != target
                    }
                    replies.append({})
                else:
                    replies.append({})
            self._reply(200, {"replies": replies})

        @override
        def log_message(self, format: str, *args: object) -> None:
            return

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        http = httplib2.Http()
        try:
            service = build(
                "sheets",
                "v4",
                http=http,
                cache_discovery=False,
                client_options={"api_endpoint": f"http://127.0.0.1:{server.server_port}/"},
            )
            state = ReviewSheetsEndpoint(service)
            yield state
        finally:
            http.close()
            server.shutdown()
            thread.join(timeout=2)
