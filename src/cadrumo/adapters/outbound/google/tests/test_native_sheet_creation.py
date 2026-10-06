"""Exercise direct native creation through real Drive and Sheets client resources."""

from __future__ import annotations

import json
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import TYPE_CHECKING, override
from urllib.parse import urlparse

import httplib2
import pytest
from googleapiclient.discovery import build

from ...storage.errors import OutboundStorageNetworkError, OutboundStorageValidationError
from ..calc_sheets_apply import _create_spreadsheet
from ..drive_entries import OWNERSHIP_KEY, OWNERSHIP_VALUE

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3.resources import DriveResource
    from googleapiclient._apis.sheets.v4.resources import SheetsResource

pytestmark = [pytest.mark.integration, pytest.mark.hex_outbound_adapter]


@dataclass
class _Endpoint:
    drive: DriveResource
    sheets: SheetsResource
    created: list[dict[str, object]] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)


@contextmanager
def _endpoint(*, create_status: int = 200, missing_id: bool = False, sheets_status: int = 200) -> Generator[_Endpoint]:
    created: list[dict[str, object]] = []
    calls: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def _reply(self, status: int, document: dict[str, object]) -> None:
            payload = json.dumps(document).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_POST(self) -> None:
            calls.append(f"POST {urlparse(self.path).path}")
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            created.append(body)
            response: dict[str, object] = {} if missing_id else {"id": "created-sheet"}
            if create_status != 200:
                response = {"error": {"code": create_status, "message": "synthetic uncertain response"}}
            self._reply(create_status, response)

        def do_GET(self) -> None:
            calls.append(f"GET {urlparse(self.path).path}")
            if sheets_status != 200:
                self._reply(sheets_status, {"error": {"code": sheets_status, "message": "synthetic failure"}})
                return
            self._reply(
                200,
                {
                    "spreadsheetId": "created-sheet",
                    "spreadsheetUrl": "https://docs.google.com/spreadsheets/d/created-sheet/edit",
                    "sheets": [{"properties": {"sheetId": 0, "title": "Sheet1"}}],
                },
            )

        @override
        def log_message(self, format: str, *args: object) -> None:
            return

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        transport = httplib2.Http()
        try:
            root = f"http://127.0.0.1:{server.server_port}/"
            drive = build("drive", "v3", http=transport, cache_discovery=False, client_options={"api_endpoint": root})
            sheets = build("sheets", "v4", http=transport, cache_discovery=False, client_options={"api_endpoint": root})
            yield _Endpoint(drive, sheets, created, calls)
        finally:
            transport.close()
            server.shutdown()
            thread.join(timeout=2)


def test_native_sheet_is_owned_and_parented_before_first_sheets_request() -> None:
    with _endpoint() as endpoint:
        result = _create_spreadsheet(endpoint.drive, endpoint.sheets, parent_id="managed-folder", title="Synthetic")

        assert result["spreadsheetId"] == "created-sheet"
        assert endpoint.created == [
            {
                "name": "Synthetic",
                "mimeType": "application/vnd.google-apps.spreadsheet",
                "parents": ["managed-folder"],
                "appProperties": {OWNERSHIP_KEY: OWNERSHIP_VALUE},
            }
        ]
        assert len(endpoint.calls) == 2
        assert endpoint.calls[0].endswith("/files")
        assert endpoint.calls[1].endswith("/spreadsheets/created-sheet")


@pytest.mark.parametrize("missing_id", [False, True])
def test_uncertain_native_creation_is_not_replayed_or_followed_by_content(missing_id: bool) -> None:
    with _endpoint(create_status=200 if missing_id else 503, missing_id=missing_id) as endpoint:
        with pytest.raises((OutboundStorageNetworkError, OutboundStorageValidationError)) as raised:
            _create_spreadsheet(endpoint.drive, endpoint.sheets, parent_id="managed-folder", title="Synthetic")

        assert raised.value.context is not None and raised.value.context["effect_uncertain"] is True
        assert len(endpoint.created) == 1
        assert len(endpoint.calls) == 1


def test_failed_post_create_structure_read_retains_marked_artifact() -> None:
    with _endpoint(sheets_status=400) as endpoint:
        with pytest.raises(OutboundStorageNetworkError):
            _create_spreadsheet(endpoint.drive, endpoint.sheets, parent_id="managed-folder", title="Synthetic")

        assert len(endpoint.created) == 1
        assert endpoint.created[0]["parents"] == ["managed-folder"]
        assert len(endpoint.calls) == 2
        assert all(not call.startswith("DELETE") for call in endpoint.calls)
