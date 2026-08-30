"""Google API response TypedDict contracts."""

import pytest

from ..api import GoogleApiResponseBody, GoogleDriveFile, GoogleSheetsRange, GoogleSpreadsheet

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def test_google_api_typeddicts_importable() -> None:
    for cls in (GoogleDriveFile, GoogleSheetsRange, GoogleSpreadsheet):
        assert hasattr(cls, "__annotations__"), f"{cls.__name__} lacks __annotations__"
        assert hasattr(cls, "__required_keys__"), f"{cls.__name__} lacks __required_keys__"
    assert GoogleApiResponseBody is not None


def test_google_drive_file_required_id_field() -> None:
    assert "id" in GoogleDriveFile.__required_keys__, "GoogleDriveFile.id is not marked as required"


def test_google_sheets_range_required_range_field() -> None:
    assert "range" in GoogleSheetsRange.__required_keys__, "GoogleSheetsRange.range is not marked as required"


def test_google_spreadsheet_required_spreadsheet_id_field() -> None:
    assert "spreadsheetId" in GoogleSpreadsheet.__required_keys__, (
        "GoogleSpreadsheet.spreadsheetId is not marked as required"
    )
