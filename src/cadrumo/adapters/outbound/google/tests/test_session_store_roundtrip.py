"""Runtime-routed roundtrip coverage for Google OAuth secure records."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....persistence.storage.tests.secure_sql import isolated_runtime_profile
from .. import session_store
from ..records import REQUIRED_SCOPES, DriveConfig, OAuthMetadata, OAuthToken

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]
_BUCKET_ID = "1a92e8a0-9da5-4712-8b71-a8aadd4eed42"  # was 'google-session'


def test_google_oauth_records_roundtrip_through_active_bucket_runtime(tmp_path: Path) -> None:
    profile = "operator-google"
    issued_at = datetime(2026, 5, 26, 9, 0, 0, tzinfo=UTC)
    opaque_refresh_token = " 1//refresh-token\t"
    token = OAuthToken(
        refresh_token=opaque_refresh_token,
        client_id="desktop-client.apps.googleusercontent.com",
        token_uri="https://oauth2.googleapis.com/token",
    )
    metadata = OAuthMetadata(
        account_email="operator@example.com",
        granted_scopes=REQUIRED_SCOPES,
        issued_at=issued_at,
    )
    drive_config = DriveConfig(root_folder_id="drive-folder-id")

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as runtime:
        session_store.save_session(profile, token, metadata, drive_config)

        raw_records = tuple(runtime.repository.iter_all_records_raw())
        token_rows = [row for row in raw_records if row.namespace == "cadrumo.google.oauth.token"]
        assert len(token_rows) == 1
        assert opaque_refresh_token.encode() not in token_rows[0].payload
        assert b"refresh_token" not in token_rows[0].payload

        loaded_token = session_store.load_token(profile)
        assert loaded_token == token
        assert loaded_token is not None
        assert loaded_token.refresh_token == opaque_refresh_token
        loaded_metadata = session_store.load_metadata(profile)
        assert loaded_metadata == metadata
        assert loaded_metadata is not None
        assert loaded_metadata.issued_at.isoformat() == "2026-05-26T09:00:00+00:00"
        assert session_store.load_drive_config(profile) == drive_config

        assert session_store.delete_session(profile) == (True, True)
        assert session_store.load_token(profile) is None
        assert session_store.load_metadata(profile) is None
        assert session_store.load_drive_config(profile) == drive_config
