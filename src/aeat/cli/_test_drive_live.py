"""Live smoke tests for the Drive sub-app.

These hit real Drive APIs against the scratch folder provisioned by
``aeat bootstrap``. They are gated behind ``AEAT_LIVE_TESTS_ENABLED``
and the presence of ``AEAT_SCRATCH_FOLDER_ID``. Project rules forbid
mocks of any kind in this module.
"""

from __future__ import annotations

import io
from typing import Any

import pytest
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

from aeat.cli._live import (
    cleanup_files,
    drive_service,
    requires_live_enabled,
    requires_scratch_folder,
    unique_prefix,
)


@pytest.mark.live
class TestDriveLiveRoundTrip:
    """End-to-end Drive round-trip in the scratch folder."""

    def test_create_list_download_delete(self) -> None:
        requires_live_enabled()
        folder_id = requires_scratch_folder()

        drive: Any = drive_service()
        prefix = unique_prefix()
        filename = f"{prefix}.txt"
        payload = b"hello from aeat live tests"

        media = MediaIoBaseUpload(io.BytesIO(payload), mimetype="text/plain", resumable=False)
        created = (
            drive.files()
            .create(
                body={"name": filename, "parents": [folder_id], "mimeType": "text/plain"},
                media_body=media,
                fields="id, name, mimeType",
            )
            .execute()
        )
        file_id = created["id"]

        try:
            assert created["name"] == filename
            assert created["mimeType"] == "text/plain"

            listing = (
                drive.files()
                .list(
                    q=f"'{folder_id}' in parents and name='{filename}' and trashed=false",
                    fields="files(id, name)",
                )
                .execute()
            )
            names = [f["name"] for f in listing.get("files", [])]
            assert filename in names

            buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(buffer, drive.files().get_media(fileId=file_id))
            done = False
            while not done:
                _status, done = downloader.next_chunk()
            assert buffer.getvalue() == payload
        finally:
            cleanup_files(drive, [file_id])

        listing_after = (
            drive.files()
            .list(
                q=f"'{folder_id}' in parents and name='{filename}' and trashed=false",
                fields="files(id, name)",
            )
            .execute()
        )
        assert all(f["name"] != filename for f in listing_after.get("files", []))
