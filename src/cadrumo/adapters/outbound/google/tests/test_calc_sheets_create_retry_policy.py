"""Drive and Sheets creates are sent once; reads and updates keep client retries."""

from __future__ import annotations

from typing import Any, cast

import httplib2
import pytest
from googleapiclient.errors import HttpError

from ...storage.errors import OutboundStorageNetworkError
from ..calc_sheets_apply import _create_folder, _create_spreadsheet, _find_folder
from ..drive_entries import OWNERSHIP_KEY, OWNERSHIP_VALUE

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_CLIENT_RETRIES = 3


class _Request:
    def __init__(self, calls: list[tuple[str, int]], name: str, result: dict[str, Any], *, fail: bool) -> None:
        self._calls = calls
        self._name = name
        self._result = result
        self._fail = fail

    def execute(self, http: object = None, num_retries: int = 0) -> dict[str, Any]:
        self._calls.append((self._name, num_retries))
        if self._fail:
            raise HttpError(httplib2.Response({"status": "503", "reason": "unavailable"}), b"unavailable")
        return self._result


class _Resource:
    """Records the retry budget each named request is executed with."""

    def __init__(self, *, fail: frozenset[str] = frozenset()) -> None:
        self.calls: list[tuple[str, int]] = []
        self.creates: list[dict[str, object]] = []
        self._fail = fail

    def _request(self, name: str, result: dict[str, Any]) -> _Request:
        return _Request(self.calls, name, result, fail=name in self._fail)

    def files(self) -> _Resource:
        return self

    def spreadsheets(self) -> _Resource:
        return self

    def create(self, **kwargs: object) -> _Request:
        self.creates.append(kwargs)
        return self._request("create", {"id": "created", "spreadsheetId": "sheet-1"})

    def list(self, **_kwargs: object) -> _Request:
        return self._request("list", {"files": []})

    def get(self, **_kwargs: object) -> _Request:
        return self._request("get", {"parents": ["root"]})

    def update(self, **_kwargs: object) -> _Request:
        return self._request("update", {"id": "sheet-1"})


def test_folder_create_is_sent_once_and_a_transient_failure_is_uncertain() -> None:
    drive = _Resource(fail=frozenset({"create"}))

    with pytest.raises(OutboundStorageNetworkError) as raised:
        _create_folder(cast(Any, drive), parent_id="parent", name="folder")

    assert drive.calls == [("create", 0)]
    assert raised.value.context == {"action": "drive.files.create.folder", "effect_uncertain": True}


def test_spreadsheet_create_is_sent_once_and_a_transient_failure_is_uncertain() -> None:
    drive = _Resource(fail=frozenset({"create"}))
    sheets = _Resource()

    with pytest.raises(OutboundStorageNetworkError) as raised:
        _create_spreadsheet(cast(Any, drive), cast(Any, sheets), parent_id="parent", title="book")

    assert drive.calls == [("create", 0)]
    assert sheets.calls == []
    assert raised.value.context == {"action": "drive.files.create.spreadsheet", "effect_uncertain": True}


def test_spreadsheet_creation_includes_destination_and_marker_in_one_request() -> None:
    drive = _Resource()
    sheets = _Resource()

    _create_spreadsheet(cast(Any, drive), cast(Any, sheets), parent_id="parent", title="book")

    assert drive.calls == [("create", 0)]
    assert drive.creates == [
        {
            "body": {
                "name": "book",
                "mimeType": "application/vnd.google-apps.spreadsheet",
                "parents": ["parent"],
                "appProperties": {OWNERSHIP_KEY: OWNERSHIP_VALUE},
            },
            "fields": "id",
        }
    ]
    assert sheets.calls == [("get", _CLIENT_RETRIES)]


def test_folder_lookup_keeps_client_retries() -> None:
    drive = _Resource()

    assert _find_folder(cast(Any, drive), parent_id="parent", name="folder") is None

    assert drive.calls == [("list", _CLIENT_RETRIES)]
