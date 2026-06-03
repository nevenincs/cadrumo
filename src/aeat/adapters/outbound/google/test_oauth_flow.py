"""Tests for Google OAuth flow failure translation."""

from __future__ import annotations

from pathlib import Path

import pytest

from ....core.config import override_settings
from ....core.i18n import tr
from ....tests.secure_sql import isolated_runtime_profile
from ._errors import GoogleAuthBrowserOpenError, GoogleAuthNetworkError, GoogleAuthProfileUnboundError
from ._oauth_flow import _raise_local_server_error, resolve_active_tax_id, run_login_flow
from ._records import OAuthClient

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]


def _valid_oauth_client() -> OAuthClient:
    return OAuthClient(
        client_id="1234.apps.googleusercontent.com",
        client_secret="GOCSPX-deadbeef",
        project_id="test-project-12345",
        auth_uri="https://accounts.google.com/o/oauth2/auth",
        token_uri="https://oauth2.googleapis.com/token",
        auth_provider_x509_cert_url="https://www.googleapis.com/oauth2/v1/certs",
        redirect_uris=("http://localhost",),
    )


def test_local_server_error_classifier_routes_browser_failures() -> None:
    upstream = RuntimeError("webbrowser launcher failed")

    with pytest.raises(GoogleAuthBrowserOpenError) as raised:
        _raise_local_server_error(upstream)

    assert raised.value.__cause__ is upstream
    assert raised.value.translated_message == "adapters.google.oauth_flow.errors.browser_launcher_refused"


def test_local_server_error_classifier_routes_network_failures() -> None:
    upstream = RuntimeError("transport connection refused")

    with pytest.raises(GoogleAuthNetworkError) as raised:
        _raise_local_server_error(upstream)

    assert raised.value.__cause__ is upstream
    assert raised.value.translated_message == "adapters.google.oauth_flow.errors.endpoint_unreachable"


def test_local_server_error_classifier_wraps_unclassified_failures() -> None:
    upstream = RuntimeError("access denied")

    with pytest.raises(GoogleAuthNetworkError) as raised:
        _raise_local_server_error(upstream)

    assert raised.value.__cause__ is upstream
    assert raised.value.context == {"error_type": "RuntimeError"}


def test_resolve_active_tax_id_refuses_missing_profile_bucket(tmp_path: Path) -> None:
    with (
        override_settings(
            aeat_active_profile="missing-profile",
            aeat_local_storage_root=tmp_path,
            aeat_secret_store_backend="unsecured",
        ),
        pytest.raises(GoogleAuthProfileUnboundError) as raised,
    ):
        resolve_active_tax_id("missing-profile")

    assert raised.value.context == {
        "profile": "missing-profile",
        "reason": "profile_bucket_manifest_missing",
    }
    assert raised.value.translated_message == "adapters.google.oauth_flow.errors.profile_state_unresolved"
    assert raised.value.suggestion == tr("adapters.google.oauth_flow.suggestions.repair_profile_state")


def test_login_flow_refuses_missing_profile_record_before_oauth_network(tmp_path: Path) -> None:
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id="google-profile-missing") as profile,
        override_settings(aeat_secret_store_backend="unsecured"),
        pytest.raises(GoogleAuthProfileUnboundError) as raised,
    ):
        run_login_flow(_valid_oauth_client(), profile.bucket_id)

    assert raised.value.context == {
        "profile": "google-profile-missing",
        "bucket_id": "google-profile-missing",
        "reason": "profile_record_missing",
    }
    assert raised.value.translated_message == "adapters.google.oauth_flow.errors.profile_state_unresolved"
    assert raised.value.suggestion == tr("adapters.google.oauth_flow.suggestions.repair_profile_state")
