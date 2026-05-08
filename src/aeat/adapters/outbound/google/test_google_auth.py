"""Tests for the Google auth status surface."""

from __future__ import annotations

import pytest

from . import (
    GoogleAuthPath,
    GoogleAuthUnavailableError,
    get_credentials_for_scopes,
    inspect_google_auth,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]


def test_inspect_google_auth_reports_fail_closed_status() -> None:
    status = inspect_google_auth()

    assert status.configured is False
    assert status.supported_paths == tuple(GoogleAuthPath)
    assert "No Google credential backend" in status.detail


def test_get_credentials_for_scopes_rejects_empty_scope_set() -> None:
    with pytest.raises(ValueError, match="at least one Google OAuth scope"):
        get_credentials_for_scopes([" ", ""])


def test_get_credentials_for_scopes_fails_closed_without_fabricating_credentials() -> None:
    with pytest.raises(GoogleAuthUnavailableError, match="not configured") as exc_info:
        get_credentials_for_scopes(
            ["https://www.googleapis.com/auth/drive.metadata.readonly"],
            path=GoogleAuthPath.DESKTOP_OAUTH_LOCAL_DEV,
        )

    assert "desktop-oauth-local-dev" in str(exc_info.value)
