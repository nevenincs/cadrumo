"""Runtime-routed roundtrip coverage for Google OAuth secure records."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from .....core import GoogleCredentialSourceKind
from .....tests.secure_sql import isolated_runtime_profile
from .. import session_store
from ..impersonation import GoogleCredentialSourceSelection, GoogleImpersonationConfig
from ..records import REQUIRED_SCOPES, DriveConfig, OAuthClient, OAuthMetadata, OAuthToken

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]
_BUCKET_ID = "1a92e8a0-9da5-4712-8b71-a8aadd4eed42"  # was 'google-session'


def test_google_oauth_records_roundtrip_through_active_bucket_runtime(tmp_path: Path) -> None:
    profile = "operator-google"
    issued_at = datetime(2026, 5, 26, 9, 0, 0, tzinfo=UTC)
    opaque_refresh_token = " 1//refresh-token\t"
    client = OAuthClient(
        client_id="desktop-client.apps.googleusercontent.com",
        client_secret="gcp-client-secret",
        project_id="cadrumo-vault",
        auth_uri="https://accounts.google.com/o/oauth2/auth",
        token_uri="https://oauth2.googleapis.com/token",
        auth_provider_x509_cert_url="https://www.googleapis.com/oauth2/v1/certs",
        redirect_uris=("http://127.0.0.1:8765/callback",),
    )
    token = OAuthToken(
        refresh_token=opaque_refresh_token,
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
        session_store.save_client(profile, client)
        session_store.save_token(profile, token)
        session_store.save_metadata(profile, metadata)
        session_store.save_drive_config(profile, drive_config)

        assert session_store.load_client(profile) == client
        loaded_token = session_store.load_token(profile)
        assert loaded_token == token
        assert loaded_token is not None
        assert loaded_token.refresh_token == opaque_refresh_token
        loaded_metadata = session_store.load_metadata(profile)
        assert loaded_metadata == metadata
        assert loaded_metadata is not None
        assert loaded_metadata.issued_at.isoformat() == "2026-05-26T09:00:00+00:00"
        assert loaded_metadata.last_refresh_at.isoformat() == "2026-05-26T09:00:00+00:00"
        assert session_store.load_drive_config(profile) == drive_config

        assert session_store.delete_session(profile) == (True, True)
        assert session_store.load_token(profile) is None
        assert session_store.load_metadata(profile) is None
        assert session_store.load_client(profile) == client
        assert session_store.load_drive_config(profile) == drive_config


def test_credential_source_selection_defaults_to_none_when_never_persisted(tmp_path: Path) -> None:
    """A profile that has never opted into impersonation has no persisted record.

    The factory dispatch treats ``None`` as the OAuth-Desktop default, so a
    missing record is a valid, expected state — never an error.
    """
    profile = "operator-no-selection"
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="1bf98a9a-4323-4b10-bcfb-55ba9fd13edc"):
        assert session_store.load_credential_source_selection(profile) is None


def test_credential_source_selection_oauth_desktop_roundtrips(tmp_path: Path) -> None:
    profile = "operator-oauth-selection"
    selection = GoogleCredentialSourceSelection()

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="76d277c7-f5f3-4d6a-923e-c8daeeabd36c"):
        session_store.save_credential_source_selection(profile, selection)

        reloaded = session_store.load_credential_source_selection(profile)

    assert reloaded == selection
    assert reloaded is not None
    assert reloaded.kind is GoogleCredentialSourceKind.OAUTH_DESKTOP
    assert reloaded.impersonation is None


def test_credential_source_selection_impersonation_roundtrips_without_a_secret(tmp_path: Path) -> None:
    """The persisted impersonation selection carries only configuration, never a secret.

    Unlike ``OAuthClient``/``OAuthToken`` (which persist a long-lived
    ``client_secret``/``refresh_token``), the impersonation selection's
    serialised payload holds only the target SA email and scopes — there is
    no field here an operator or auditor should ever expect to be a secret,
    because the access token is re-derived from ADC on every use.
    """
    profile = "operator-impersonation-selection"
    config = GoogleImpersonationConfig(
        target_principal="aeat-export@example-project.iam.gserviceaccount.com",
        delegates=("delegate-a@example-project.iam.gserviceaccount.com",),
        subject="taxpayer@example-workspace-domain.com",
        lifetime_s=1800,
    )
    selection = GoogleCredentialSourceSelection(
        kind=GoogleCredentialSourceKind.SERVICE_ACCOUNT_IMPERSONATION,
        impersonation=config,
    )

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="6e5dd772-a3e1-41d8-b135-7fe8182f9eae"):
        session_store.save_credential_source_selection(profile, selection)

        reloaded = session_store.load_credential_source_selection(profile)

    assert reloaded == selection
    assert reloaded is not None
    assert reloaded.kind is GoogleCredentialSourceKind.SERVICE_ACCOUNT_IMPERSONATION
    assert reloaded.impersonation == config
    # No SA private key / access token field exists on the model at all —
    # the only persisted fields are target_principal, target_scopes,
    # delegates, subject, and lifetime_s (all non-secret configuration).
    assert set(config.model_dump().keys()) == {
        "target_principal",
        "target_scopes",
        "delegates",
        "subject",
        "lifetime_s",
    }
