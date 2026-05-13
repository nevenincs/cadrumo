"""Tests for the Google OAuth Desktop record models and error hierarchy.

Every record asserts its frozen + strict + extra-forbid contract along
with the small set of inline `field_validator` rules that gate the
data shape. The error hierarchy is exercised through the
`bind_error_code` registration contract: every leaf must have a
distinct stable error code registered in the adapters error registry,
or the import would raise at module load.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from aeat.adapters.outbound.google._errors import (
    GoogleAuthBrowserOpenError,
    GoogleAuthClientNotRegisteredError,
    GoogleAuthClientRevokedError,
    GoogleAuthError,
    GoogleAuthExpiredError,
    GoogleAuthKeychainLockedError,
    GoogleAuthLoopbackBindError,
    GoogleAuthNetworkError,
    GoogleAuthProfileUnboundError,
    GoogleAuthRevokedError,
    GoogleAuthScopeInsufficientError,
    GoogleAuthUnsecuredModeRefusedError,
    GoogleAuthValidationError,
)
from aeat.adapters.outbound.google._records import (
    DRIVE_FILE_SCOPE,
    REQUIRED_SCOPES,
    SHEETS_SCOPE,
    DriveAppProperties,
    OAuthClient,
    OAuthMetadata,
    OAuthToken,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]


def _valid_client_kwargs() -> dict[str, object]:
    return {
        "client_id": "1234.apps.googleusercontent.com",
        "client_secret": "GOCSPX-deadbeef",
        "project_id": "test-project-12345",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "redirect_uris": ("http://localhost",),
    }


def _valid_metadata_kwargs() -> dict[str, object]:
    return {
        "account_email": "operator@example.com",
        "granted_scopes": REQUIRED_SCOPES,
        "issued_at": datetime(2026, 5, 14, 9, 0, tzinfo=timezone.utc),
        "last_refresh_at": datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc),
    }


def test_required_scopes_contains_drive_and_sheets() -> None:
    assert DRIVE_FILE_SCOPE in REQUIRED_SCOPES
    assert SHEETS_SCOPE in REQUIRED_SCOPES
    assert len(REQUIRED_SCOPES) == 2


def test_oauth_client_round_trips_through_strict_validation() -> None:
    client = OAuthClient(**_valid_client_kwargs())
    reloaded = OAuthClient.model_validate_json(client.model_dump_json())
    assert reloaded == client


def test_oauth_client_rejects_non_https_auth_uri() -> None:
    kwargs = _valid_client_kwargs()
    kwargs["auth_uri"] = "http://accounts.google.com/o/oauth2/auth"
    with pytest.raises(ValidationError, match="HTTPS"):
        OAuthClient(**kwargs)


def test_oauth_client_is_frozen() -> None:
    client = OAuthClient(**_valid_client_kwargs())
    with pytest.raises(ValidationError, match="frozen"):
        client.client_id = "other.apps.googleusercontent.com"  # type: ignore[misc]


def test_oauth_client_rejects_extra_fields() -> None:
    kwargs = _valid_client_kwargs()
    kwargs["unexpected"] = "value"
    with pytest.raises(ValidationError, match="Extra"):
        OAuthClient(**kwargs)


def test_oauth_client_rejects_empty_client_secret() -> None:
    kwargs = _valid_client_kwargs()
    kwargs["client_secret"] = ""
    with pytest.raises(ValidationError, match="at least 1"):
        OAuthClient(**kwargs)


def test_oauth_token_minimum_shape() -> None:
    token = OAuthToken(refresh_token="1//deadbeef", token_uri="https://oauth2.googleapis.com/token")
    assert token.refresh_token == "1//deadbeef"


def test_oauth_token_is_frozen() -> None:
    token = OAuthToken(refresh_token="1//deadbeef", token_uri="https://oauth2.googleapis.com/token")
    with pytest.raises(ValidationError, match="frozen"):
        token.refresh_token = "1//rotated"  # type: ignore[misc]


def test_oauth_token_rejects_empty_refresh() -> None:
    with pytest.raises(ValidationError, match="at least 1"):
        OAuthToken(refresh_token="", token_uri="https://oauth2.googleapis.com/token")


def test_oauth_metadata_round_trip() -> None:
    metadata = OAuthMetadata(**_valid_metadata_kwargs())
    assert metadata.reauth_required is False
    assert SHEETS_SCOPE in metadata.granted_scopes


def test_oauth_metadata_requires_drive_and_sheets_scopes() -> None:
    kwargs = _valid_metadata_kwargs()
    kwargs["granted_scopes"] = (DRIVE_FILE_SCOPE,)
    with pytest.raises(ValidationError, match="missing required scopes"):
        OAuthMetadata(**kwargs)


def test_oauth_metadata_rejects_empty_scope_tuple() -> None:
    kwargs = _valid_metadata_kwargs()
    kwargs["granted_scopes"] = ()
    with pytest.raises(ValidationError, match="at least 1"):
        OAuthMetadata(**kwargs)


def test_oauth_metadata_reauth_required_round_trips() -> None:
    kwargs = _valid_metadata_kwargs()
    kwargs["reauth_required"] = True
    metadata = OAuthMetadata(**kwargs)
    assert metadata.reauth_required is True


def test_drive_app_properties_round_trip() -> None:
    payload = DriveAppProperties(
        namespace="ledger_transaction",
        object_key_hmac="abc123def456",
        revision=1,
        source_hash="sha256-deadbeef",
        written_at=datetime(2026, 5, 14, tzinfo=timezone.utc),
    )
    reloaded = DriveAppProperties.model_validate_json(payload.model_dump_json())
    assert reloaded == payload
    assert reloaded.schema_version == "1"


def test_drive_app_properties_rejects_revision_below_one() -> None:
    with pytest.raises(ValidationError, match="greater than or equal to 1"):
        DriveAppProperties(
            namespace="ledger_transaction",
            object_key_hmac="abc",
            revision=0,
            source_hash="sha256-x",
            written_at=datetime(2026, 5, 14, tzinfo=timezone.utc),
        )


def test_google_auth_error_hierarchy_is_unified() -> None:
    """Every leaf error must subclass `GoogleAuthError` for unified catch."""

    for leaf in (
        GoogleAuthBrowserOpenError,
        GoogleAuthClientNotRegisteredError,
        GoogleAuthClientRevokedError,
        GoogleAuthExpiredError,
        GoogleAuthKeychainLockedError,
        GoogleAuthLoopbackBindError,
        GoogleAuthNetworkError,
        GoogleAuthProfileUnboundError,
        GoogleAuthRevokedError,
        GoogleAuthScopeInsufficientError,
        GoogleAuthUnsecuredModeRefusedError,
        GoogleAuthValidationError,
    ):
        assert issubclass(leaf, GoogleAuthError), leaf.__name__


def test_google_auth_validation_error_is_value_error_subclass() -> None:
    """Validation error doubles as `ValueError` for pydantic compatibility."""

    assert issubclass(GoogleAuthValidationError, ValueError)


def test_every_leaf_carries_a_registered_error_code() -> None:
    """Each leaf class binds to a distinct stable error code at import."""

    leaves = (
        GoogleAuthError,
        GoogleAuthValidationError,
        GoogleAuthClientNotRegisteredError,
        GoogleAuthClientRevokedError,
        GoogleAuthRevokedError,
        GoogleAuthExpiredError,
        GoogleAuthScopeInsufficientError,
        GoogleAuthNetworkError,
        GoogleAuthLoopbackBindError,
        GoogleAuthBrowserOpenError,
        GoogleAuthUnsecuredModeRefusedError,
        GoogleAuthKeychainLockedError,
        GoogleAuthProfileUnboundError,
    )
    codes = {leaf.code.code for leaf in leaves}
    assert len(codes) == len(leaves), f"duplicate codes: {codes}"
    for leaf in leaves:
        assert leaf.code.code.startswith(("AUTH_GOOGLE", "REFUSED_GOOGLE", "FAIL_GOOGLE", "LOCKED_GOOGLE"))


def test_google_auth_error_constructs_with_context_and_suggestion() -> None:
    """Verify the AeatError constructor signature flows through cleanly."""

    err = GoogleAuthRevokedError(
        "Refresh token revoked",
        context={"profile": "default"},
        suggestion="aeat config google login --profile default",
    )
    assert err.context == {"profile": "default"}
    assert err.suggestion == "aeat config google login --profile default"
