"""Tests for the Google OAuth Desktop record models and error hierarchy.

Every record asserts its frozen + strict + extra-forbid contract along
with the small set of inline `field_validator` rules that gate the
data shape. The error hierarchy is exercised through the
`bind_error_code` registration contract: every leaf must have a
distinct stable error code registered in the adapters error registry,
or the import would raise at module load.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import Literal, TypedDict

import pytest
from pydantic import ValidationError

from ..errors import (
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
from .._records import (
    DRIVE_FILE_SCOPE,
    REQUIRED_SCOPES,
    SHEETS_SCOPE,
    DriveAppProperties,
    OAuthClient,
    OAuthMetadata,
    OAuthToken,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


class _ClientKwargs(TypedDict):
    client_id: str
    client_secret: str
    project_id: str
    auth_uri: str
    token_uri: str
    auth_provider_x509_cert_url: str
    redirect_uris: tuple[str, ...]


class _MetadataKwargs(TypedDict):
    account_email: str
    granted_scopes: tuple[str, ...]
    issued_at: datetime
    last_refresh_at: datetime


def _valid_client_kwargs() -> _ClientKwargs:
    return {
        "client_id": "1234.apps.googleusercontent.com",
        "client_secret": "GOCSPX-deadbeef",
        "project_id": "test-project-12345",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "redirect_uris": ("http://localhost",),
    }


def _valid_metadata_kwargs() -> _MetadataKwargs:
    return {
        "account_email": "operator@example.com",
        "granted_scopes": REQUIRED_SCOPES,
        "issued_at": datetime(2026, 5, 14, 9, 0, tzinfo=UTC),
        "last_refresh_at": datetime(2026, 5, 14, 12, 0, tzinfo=UTC),
    }


def test_required_scopes_contains_drive_and_sheets() -> None:
    assert DRIVE_FILE_SCOPE in REQUIRED_SCOPES
    assert SHEETS_SCOPE in REQUIRED_SCOPES
    assert len(REQUIRED_SCOPES) == 4


def test_oauth_client_round_trips_through_strict_validation() -> None:
    client = OAuthClient(**_valid_client_kwargs())
    reloaded = OAuthClient.model_validate_json(client.model_dump_json())
    assert reloaded == client


def test_oauth_client_rejects_non_https_auth_uri() -> None:
    kwargs = _valid_client_kwargs()
    kwargs["auth_uri"] = "http://accounts.google.com/o/oauth2/auth"
    with pytest.raises(ValidationError, match="HTTPS"):
        OAuthClient(**kwargs)


@pytest.mark.parametrize(
    ("field", "endpoint"),
    (
        ("auth_uri", "https://"),
        ("auth_uri", "https://?redirect=x"),
        ("auth_uri", "https://evil.example/oauth"),
        ("auth_uri", "https://operator@accounts.google.com/oauth"),
        ("auth_uri", "https://accounts.google.com:8443/oauth"),
        ("token_uri", "http://127.0.0.1/token"),
        ("token_uri", "file:///tmp/token"),
        ("auth_provider_x509_cert_url", "https://evil.example/certs"),
    ),
)
def test_oauth_client_refuses_malformed_or_untrusted_endpoints(
    field: Literal["auth_uri", "token_uri", "auth_provider_x509_cert_url"], endpoint: str
) -> None:
    """Persisted client endpoints must remain canonical Google HTTPS origins."""

    kwargs = _valid_client_kwargs()
    kwargs[field] = endpoint

    with pytest.raises(ValidationError):
        OAuthClient(**kwargs)


def test_oauth_client_is_frozen() -> None:
    client = OAuthClient(**_valid_client_kwargs())
    with pytest.raises(ValidationError, match="frozen"):
        client.client_id = "other.apps.googleusercontent.com"


def test_oauth_client_rejects_extra_fields() -> None:
    data: dict[str, object] = {**_valid_client_kwargs(), "unexpected": "value"}
    with pytest.raises(ValidationError, match="Extra"):
        OAuthClient.model_validate(data)


def test_oauth_client_rejects_empty_client_secret() -> None:
    kwargs = _valid_client_kwargs()
    kwargs["client_secret"] = ""
    with pytest.raises(ValidationError, match="at least 1"):
        OAuthClient(**kwargs)


def test_oauth_token_minimum_shape() -> None:
    token = OAuthToken(refresh_token="1//deadbeef", token_uri="https://oauth2.googleapis.com/token")
    assert token.refresh_token == "1//deadbeef"


@pytest.mark.parametrize(
    "endpoint", ("https://evil.example/token", "https://oauth2.googleapis.com:444/token", "file:///tmp/token")
)
def test_oauth_token_refuses_untrusted_or_malformed_token_endpoint(endpoint: str) -> None:
    """A refresh token may never persist an endpoint outside Google OAuth's canonical origin."""

    with pytest.raises(ValidationError):
        OAuthToken(refresh_token="1//deadbeef", token_uri=endpoint)


def test_oauth_token_is_frozen() -> None:
    token = OAuthToken(refresh_token="1//deadbeef", token_uri="https://oauth2.googleapis.com/token")
    with pytest.raises(ValidationError, match="frozen"):
        token.refresh_token = "1//rotated"


def test_oauth_token_rejects_empty_refresh() -> None:
    with pytest.raises(ValidationError, match="at least 1"):
        OAuthToken(refresh_token="", token_uri="https://oauth2.googleapis.com/token")


@pytest.mark.parametrize("refresh_token", (" ", "\t\r\n"))
def test_oauth_token_rejects_whitespace_only_refresh(refresh_token: str) -> None:
    """A refresh credential must carry opaque token bytes, not only whitespace."""

    with pytest.raises(ValidationError, match="non-whitespace"):
        OAuthToken(refresh_token=refresh_token, token_uri="https://oauth2.googleapis.com/token")


def test_oauth_metadata_round_trip() -> None:
    metadata = OAuthMetadata(**_valid_metadata_kwargs())
    reloaded = OAuthMetadata.model_validate_json(metadata.model_dump_json())

    assert reloaded == metadata
    assert metadata.reauth_required is False
    assert SHEETS_SCOPE in metadata.granted_scopes
    assert metadata.issued_at.isoformat() == "2026-05-14T09:00:00+00:00"
    assert metadata.last_refresh_at.isoformat() == "2026-05-14T12:00:00+00:00"


@pytest.mark.parametrize(
    ("field", "invalid_instant"),
    (
        ("issued_at", datetime(2026, 5, 14, 9, 0)),
        ("issued_at", datetime(2026, 5, 14, 10, 0, tzinfo=timezone(timedelta(hours=1)))),
        ("last_refresh_at", datetime(2026, 5, 14, 9, 0)),
        ("last_refresh_at", datetime(2026, 5, 14, 10, 0, tzinfo=timezone(timedelta(hours=1)))),
    ),
)
def test_oauth_metadata_refuses_ambiguous_audit_instants(field: str, invalid_instant: datetime) -> None:
    """Both persisted OAuth audit instants must be explicitly UTC."""

    payload: dict[str, object] = dict(_valid_metadata_kwargs())
    payload[field] = invalid_instant

    with pytest.raises(ValidationError, match=r"datetime must be in UTC|datetime must be timezone-aware"):
        OAuthMetadata.model_validate(payload)


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
    base = _valid_metadata_kwargs()
    metadata = OAuthMetadata(**base, reauth_required=True)
    assert metadata.reauth_required is True


def test_drive_app_properties_round_trip() -> None:
    payload = DriveAppProperties(
        cadrumo_vault_app="cadrumo",
        namespace="ledger_transaction",
        object_key_hmac="abc123def456",
        content_hash="sha256-deadbeef",
    )
    reloaded = DriveAppProperties.model_validate_json(payload.model_dump_json(by_alias=True))
    assert reloaded == payload
    assert payload.model_dump(by_alias=True)["cadrumo_vault_app"] == "cadrumo"


def test_drive_app_properties_rejects_missing_runtime_storage_metadata() -> None:
    with pytest.raises(ValidationError):
        DriveAppProperties.model_validate(
            {
                "namespace": "ledger_transaction",
                "object_key_hmac": "abc",
                "content_hash": "sha256-x",
            },
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


def test_google_auth_validation_error_is_not_value_error_subclass() -> None:
    """GoogleAuthValidationError must NOT be a ValueError subclass (MRO leak removed)."""

    assert not issubclass(GoogleAuthValidationError, ValueError)


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


def test_google_auth_error_constructs_with_factual_context_only() -> None:
    """Google adapter errors retain facts without a legacy recovery field."""

    err = GoogleAuthRevokedError(
        "Refresh token revoked",
        context={"profile": "default"},
    )
    assert err.context == {"profile": "default"}
    assert not hasattr(err, "suggestion")
