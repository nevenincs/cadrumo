"""Unit tests for the pure helpers in :mod:`aeat.auth`.

Network-touching code paths (OAuth flow, ADC acquisition, service
builders) are exercised by the live smoke test suite, never here.
Project rules forbid mocks, fakes, stubs, and patches in any test that
would otherwise hit Google APIs.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from .auth import (
    CLOUD_PLATFORM_SCOPE,
    DOCS_SCOPE,
    DRIVE_SCOPE,
    SCOPES,
    SHEETS_SCOPE,
    USERINFO_EMAIL_SCOPE,
    assert_credentials_have_scopes,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]


@dataclass
class _ScopedCreds:
    """Minimal stand-in for a credentials object exposing a ``scopes`` list.

    Not a mock — a plain dataclass with the single attribute the helper
    inspects. Required because there is no way to construct a real
    ``google.auth.credentials.Credentials`` without performing an actual
    authentication.
    """

    scopes: list[str] | None


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
