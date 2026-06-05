"""Runtime-routed roundtrip coverage for Google OAuth secure records."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from .....tests.secure_sql import isolated_runtime_profile
from .. import _session_store
from .._records import REQUIRED_SCOPES, DriveConfig, OAuthClient, OAuthMetadata, OAuthToken

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]
_BUCKET_ID = "google-session"


def test_google_oauth_records_roundtrip_through_active_bucket_runtime(tmp_path: Path) -> None:
    profile = "operator-google"
    issued_at = datetime(2026, 5, 26, 9, 0, 0, tzinfo=UTC)
    client = OAuthClient(
        client_id="desktop-client.apps.googleusercontent.com",
        client_secret="gcp-client-secret",
        project_id="aeat-vault",
        auth_uri="https://accounts.google.com/o/oauth2/auth",
        token_uri="https://oauth2.googleapis.com/token",
        auth_provider_x509_cert_url="https://www.googleapis.com/oauth2/v1/certs",
        redirect_uris=("http://127.0.0.1:8765/callback",),
    )
    token = OAuthToken(
        refresh_token="1//refresh-token",
        token_uri="https://oauth2.googleapis.com/token",
    )
    metadata = OAuthMetadata(
        account_email="operator@example.com",
        granted_scopes=REQUIRED_SCOPES,
        issued_at=issued_at,
        last_refresh_at=issued_at,
    )
    drive_config = DriveConfig(root_folder_id="drive-folder-id")

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        _session_store.save_client(profile, client)
        _session_store.save_token(profile, token)
        _session_store.save_metadata(profile, metadata)
        _session_store.save_drive_config(profile, drive_config)

        assert _session_store.load_client(profile) == client
        assert _session_store.load_token(profile) == token
        assert _session_store.load_metadata(profile) == metadata
        assert _session_store.load_drive_config(profile) == drive_config

        assert _session_store.delete_session(profile) == (True, True)
        assert _session_store.load_token(profile) is None
        assert _session_store.load_metadata(profile) is None
        assert _session_store.load_client(profile) == client
        assert _session_store.load_drive_config(profile) == drive_config
