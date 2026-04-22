"""Unit tests for the pure helpers in :mod:`aeat.auth`.

Network-touching code paths (OAuth flow, ADC acquisition, service
builders) are exercised by the live smoke test suite, never here.
Project rules forbid mocks, fakes, stubs, and patches in any test that
would otherwise hit Google APIs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from pydantic_settings import SettingsConfigDict

from .auth import (
    ADC_LOGIN_SCOPE_CSV,
    ADC_LOGIN_SCOPES,
    CLOUD_PLATFORM_SCOPE,
    DOCS_SCOPE,
    DRIVE_SCOPE,
    OPENID_SCOPE,
    REQUIRED_ADC_SCOPES,
    SCOPES,
    SHEETS_SCOPE,
    USERINFO_EMAIL_SCOPE,
    GoogleAuthPath,
    assert_credentials_have_scopes,
    inspect_google_auth,
    inspect_oauth_token_cache,
)
from .config import Settings

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]

_OAUTH_CLIENT_SECRET = "client-secret"  # noqa: S105 - test-only placeholder


@dataclass
class _ScopedCreds:
    """Minimal stand-in for a credentials object exposing a ``scopes`` list.

    Not a mock — a plain dataclass with the single attribute the helper
    inspects. Required because there is no way to construct a real
    ``google.auth.credentials.Credentials`` without performing an actual
    authentication.
    """

    scopes: list[str] | None


class IsolatedSettings(Settings):
    """Settings variant that does not read the on-disk env file."""

    model_config = SettingsConfigDict(env_file=None, env_file_encoding="utf-8")


class TestScopeConstants:
    """The default scope set must cover every surface the bootstrap touches."""

    def test_default_scopes_include_drive(self) -> None:
        assert DRIVE_SCOPE in SCOPES

    def test_default_scopes_include_sheets(self) -> None:
        assert SHEETS_SCOPE in SCOPES

    def test_default_scopes_include_docs(self) -> None:
        assert DOCS_SCOPE in SCOPES

    def test_default_scopes_include_cloud_platform(self) -> None:
        assert CLOUD_PLATFORM_SCOPE in SCOPES

    def test_default_scopes_include_userinfo_email(self) -> None:
        assert USERINFO_EMAIL_SCOPE in SCOPES

    def test_adc_login_scopes_include_openid_and_required_adc_scopes(self) -> None:
        assert [OPENID_SCOPE, *REQUIRED_ADC_SCOPES] == ADC_LOGIN_SCOPES

    def test_adc_login_scope_csv_matches_scope_order(self) -> None:
        assert ",".join(ADC_LOGIN_SCOPES) == ADC_LOGIN_SCOPE_CSV


class TestAssertCredentialsHaveScopes:
    """Behaviour of ``assert_credentials_have_scopes``."""

    def test_all_scopes_granted_returns_ok(self) -> None:
        creds = _ScopedCreds(scopes=[DRIVE_SCOPE, SHEETS_SCOPE])
        ok, missing = assert_credentials_have_scopes(creds, [DRIVE_SCOPE])
        assert ok is True
        assert missing == []

    def test_missing_scope_returns_not_ok_with_diff(self) -> None:
        creds = _ScopedCreds(scopes=[DRIVE_SCOPE])
        ok, missing = assert_credentials_have_scopes(
            creds,
            [DRIVE_SCOPE, SHEETS_SCOPE, DOCS_SCOPE],
        )
        assert ok is False
        assert missing == sorted([SHEETS_SCOPE, DOCS_SCOPE])

    def test_no_scopes_attribute_means_everything_missing(self) -> None:
        creds = _ScopedCreds(scopes=None)
        ok, missing = assert_credentials_have_scopes(creds, [DRIVE_SCOPE])
        assert ok is False
        assert missing == [DRIVE_SCOPE]

    def test_empty_required_set_is_trivially_ok(self) -> None:
        creds = _ScopedCreds(scopes=[])
        ok, missing = assert_credentials_have_scopes(creds, [])
        assert ok is True
        assert missing == []


class TestInspectGoogleAuth:
    """Deterministic auth-path inspection must match the UX contract."""

    def test_infers_desktop_oauth_when_only_oauth_is_complete(self, tmp_path: Path) -> None:
        settings = IsolatedSettings(
            google_oauth_client_id="client-id",
            google_oauth_client_secret=_OAUTH_CLIENT_SECRET,
            aeat_token_dir=tmp_path / ".tokens",
        )

        inspection = inspect_google_auth(settings, project_root=tmp_path)

        assert inspection.active_path == GoogleAuthPath.DESKTOP_OAUTH_LOCAL_DEV
        assert inspection.blocking_reason is None
        assert inspection.oauth_token_path == tmp_path / ".tokens" / "google_oauth_token.json"

    def test_requires_explicit_path_when_both_families_are_present(self, tmp_path: Path) -> None:
        service_account = tmp_path / "service-account.json"
        service_account.write_text("{}", encoding="utf-8")
        settings = IsolatedSettings(
            google_oauth_client_id="client-id",
            google_oauth_client_secret=_OAUTH_CLIENT_SECRET,
            google_application_credentials=str(service_account),
        )

        inspection = inspect_google_auth(settings, project_root=tmp_path)

        assert inspection.active_path is None
        assert inspection.is_ambiguous is True
        assert inspection.blocking_reason is not None
        assert "Set GOOGLE_AUTH_PATH" in inspection.blocking_reason

    def test_honours_explicit_service_account_selection(self, tmp_path: Path) -> None:
        service_account = tmp_path / "service-account.json"
        service_account.write_text("{}", encoding="utf-8")
        settings = IsolatedSettings(
            google_auth_path=GoogleAuthPath.SERVICE_ACCOUNT_AUTOMATION,
            google_oauth_client_id="client-id",
            google_oauth_client_secret=_OAUTH_CLIENT_SECRET,
            google_application_credentials=str(service_account),
        )

        inspection = inspect_google_auth(settings, project_root=tmp_path)

        assert inspection.active_path == GoogleAuthPath.SERVICE_ACCOUNT_AUTOMATION
        assert inspection.blocking_reason is None
        assert inspection.service_account_existing_path == service_account

    def test_blocks_when_explicit_service_account_key_is_missing(self, tmp_path: Path) -> None:
        settings = IsolatedSettings(
            google_auth_path=GoogleAuthPath.SERVICE_ACCOUNT_AUTOMATION,
            google_application_credentials=str(tmp_path / "missing.json"),
        )

        inspection = inspect_google_auth(settings, project_root=tmp_path)

        assert inspection.active_path == GoogleAuthPath.SERVICE_ACCOUNT_AUTOMATION
        assert inspection.blocking_reason is not None
        assert "does not exist" in inspection.blocking_reason


class TestInspectOauthTokenCache:
    """Desktop OAuth cache inspection must reject incomplete token files."""

    def test_missing_file_reports_missing(self, tmp_path: Path) -> None:
        issue = inspect_oauth_token_cache(tmp_path / "missing.json")
        assert issue == "repo-local CLI OAuth token missing"

    def test_missing_required_scope_is_reported(self, tmp_path: Path) -> None:
        token_path = tmp_path / "google_oauth_token.json"
        token_path.write_text(
            (
                '{"refresh_token": "refresh", "scopes": ['
                '"https://www.googleapis.com/auth/drive",'
                '"https://www.googleapis.com/auth/spreadsheets"'
                "]}"
            ),
            encoding="utf-8",
        )

        issue = inspect_oauth_token_cache(token_path)

        assert issue is not None
        assert "missing required scopes" in issue
