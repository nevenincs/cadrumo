"""Tests for the Google OAuth credential refresh lifecycle."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from aeat.adapters.outbound.google._errors import (
    GoogleAuthExpiredError,
    GoogleAuthNetworkError,
    GoogleAuthRevokedError,
)
from aeat.adapters.outbound.google._records import REQUIRED_SCOPES, OAuthClient, OAuthMetadata, OAuthToken
from aeat.adapters.outbound.google._refresh import (
    ACCESS_TOKEN_REFRESH_BUFFER,
    TESTING_PROJECT_TOKEN_LIFETIME,
    TESTING_PROJECT_WARN_AFTER,
    detect_testing_project_warning,
    is_token_expired,
    mark_reauth_required,
    refresh_credentials,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]


def _client() -> OAuthClient:
    return OAuthClient(
        client_id="1234.apps.googleusercontent.com",
        client_secret="GOCSPX-fake",
        project_id="test-project",
        auth_uri="https://accounts.google.com/o/oauth2/auth",
        token_uri="https://oauth2.googleapis.com/token",
        auth_provider_x509_cert_url="https://www.googleapis.com/oauth2/v1/certs",
        redirect_uris=("http://localhost",),
    )


def _token() -> OAuthToken:
    return OAuthToken(refresh_token="1//refresh-original", token_uri="https://oauth2.googleapis.com/token")


def _metadata(*, issued_at: datetime, last_refresh_at: datetime, reauth_required: bool = False) -> OAuthMetadata:
    return OAuthMetadata(
        account_email="operator@example.com",
        granted_scopes=REQUIRED_SCOPES,
        issued_at=issued_at,
        last_refresh_at=last_refresh_at,
        reauth_required=reauth_required,
    )


def test_buffer_constants_match_spec() -> None:
    assert timedelta(minutes=5) == ACCESS_TOKEN_REFRESH_BUFFER
    assert timedelta(days=7) == TESTING_PROJECT_TOKEN_LIFETIME
    assert timedelta(days=6) == TESTING_PROJECT_WARN_AFTER


def test_is_token_expired_treats_none_expiry_as_expired() -> None:
    assert is_token_expired(access_token_expiry=None, now=datetime(2026, 5, 14, tzinfo=UTC))


def test_is_token_expired_returns_false_when_well_inside_validity_window() -> None:
    now = datetime(2026, 5, 14, 10, 0, tzinfo=UTC)
    expiry = now + timedelta(hours=1)
    assert not is_token_expired(access_token_expiry=expiry, now=now)


def test_is_token_expired_returns_true_inside_clock_skew_buffer() -> None:
    now = datetime(2026, 5, 14, 10, 0, tzinfo=UTC)
    expiry = now + timedelta(minutes=4)
    assert is_token_expired(access_token_expiry=expiry, now=now)


def test_is_token_expired_returns_true_at_exact_expiry() -> None:
    now = datetime(2026, 5, 14, 10, 0, tzinfo=UTC)
    assert is_token_expired(access_token_expiry=now, now=now)


def test_detect_testing_project_warning_returns_none_inside_warning_window() -> None:
    issued = datetime(2026, 5, 1, tzinfo=UTC)
    now = issued + timedelta(days=3)
    warning = detect_testing_project_warning(issued_at=issued, now=now, last_refresh_at=issued)
    assert warning is None


def test_detect_testing_project_warning_emits_on_first_crossing() -> None:
    issued = datetime(2026, 5, 1, tzinfo=UTC)
    now = issued + timedelta(days=6, hours=2)
    warning = detect_testing_project_warning(issued_at=issued, now=now, last_refresh_at=issued)
    assert warning is not None
    assert "7-day Testing-project cap" in warning
    assert "aeat config google login" in warning


def test_detect_testing_project_warning_quiet_after_first_crossing() -> None:
    """Once a previous refresh has already crossed the warning threshold,
    subsequent refreshes inside the same expired-window do NOT re-warn."""

    issued = datetime(2026, 5, 1, tzinfo=UTC)
    last_refresh = issued + timedelta(days=6, hours=12)
    now = issued + timedelta(days=6, hours=15)
    warning = detect_testing_project_warning(issued_at=issued, now=now, last_refresh_at=last_refresh)
    assert warning is None


def test_detect_testing_project_warning_returns_none_when_already_expired() -> None:
    """Past the 7-day cap, the credential is unrecoverable; the warning
    is moot. The caller should be raising `GoogleAuthExpiredError`
    instead — but the helper doesn't conflate the two paths."""

    issued = datetime(2026, 5, 1, tzinfo=UTC)
    now = issued + timedelta(days=8)
    warning = detect_testing_project_warning(issued_at=issued, now=now, last_refresh_at=issued)
    assert warning is None


def test_mark_reauth_required_returns_copy_with_flipped_flag() -> None:
    issued = datetime(2026, 5, 14, tzinfo=UTC)
    metadata = _metadata(issued_at=issued, last_refresh_at=issued, reauth_required=False)
    flipped = mark_reauth_required(metadata)
    assert flipped.reauth_required is True
    assert metadata.reauth_required is False  # original is frozen, untouched
    # Other fields preserved.
    assert flipped.account_email == metadata.account_email
    assert flipped.issued_at == metadata.issued_at


def test_refresh_credentials_returns_rotated_token_and_advances_last_refresh() -> None:
    issued = datetime(2026, 5, 14, 10, 0, tzinfo=UTC)
    now = issued + timedelta(minutes=30)
    metadata = _metadata(issued_at=issued, last_refresh_at=issued)

    def refresher(client: OAuthClient, token: OAuthToken) -> tuple[str, str, datetime]:
        return ("1//refresh-rotated", "ya29.access-token-new", now + timedelta(hours=1))

    new_token, new_metadata, access_token, warning = refresh_credentials(
        client=_client(),
        token=_token(),
        metadata=metadata,
        now=now,
        refresher=refresher,
    )
    assert new_token.refresh_token == "1//refresh-rotated"
    assert new_metadata.last_refresh_at == now
    assert new_metadata.reauth_required is False
    assert access_token == "ya29.access-token-new"
    assert warning is None


def test_refresh_credentials_propagates_warning_on_six_day_crossing() -> None:
    issued = datetime(2026, 5, 1, tzinfo=UTC)
    now = issued + timedelta(days=6, hours=2)
    metadata = _metadata(issued_at=issued, last_refresh_at=issued)

    def refresher(client: OAuthClient, token: OAuthToken) -> tuple[str, str, datetime]:
        return ("1//refresh-rotated", "ya29.x", now + timedelta(hours=1))

    _, _, _, warning = refresh_credentials(
        client=_client(),
        token=_token(),
        metadata=metadata,
        now=now,
        refresher=refresher,
    )
    assert warning is not None and "7-day" in warning


def test_refresh_credentials_attaches_marked_metadata_to_invalid_grant_exception() -> None:
    issued = datetime(2026, 5, 14, tzinfo=UTC)
    metadata = _metadata(issued_at=issued, last_refresh_at=issued)

    def refresher(client: OAuthClient, token: OAuthToken) -> tuple[str, str, datetime]:
        raise GoogleAuthRevokedError("invalid_grant", context={"reason": "Token has been expired or revoked."})

    with pytest.raises(GoogleAuthRevokedError) as exc_info:
        refresh_credentials(
            client=_client(),
            token=_token(),
            metadata=metadata,
            now=issued + timedelta(minutes=5),
            refresher=refresher,
        )
    assert exc_info.value.context is not None
    persisted = exc_info.value.context["metadata"]
    assert persisted["reauth_required"] is True


def test_refresh_credentials_refuses_when_already_reauth_required() -> None:
    issued = datetime(2026, 5, 14, tzinfo=UTC)
    metadata = _metadata(issued_at=issued, last_refresh_at=issued, reauth_required=True)

    def refresher(client: OAuthClient, token: OAuthToken) -> tuple[str, str, datetime]:
        pytest.fail("refresher must not be called when reauth_required is True")

    with pytest.raises(GoogleAuthExpiredError) as exc_info:
        refresh_credentials(
            client=_client(),
            token=_token(),
            metadata=metadata,
            now=issued + timedelta(minutes=5),
            refresher=refresher,
        )
    assert exc_info.value.suggestion == "aeat config google login"


def test_refresh_credentials_translates_oserror_into_network_error() -> None:
    issued = datetime(2026, 5, 14, tzinfo=UTC)
    metadata = _metadata(issued_at=issued, last_refresh_at=issued)

    def refresher(client: OAuthClient, token: OAuthToken) -> tuple[str, str, datetime]:
        raise OSError("connection refused")

    with pytest.raises(GoogleAuthNetworkError) as exc_info:
        refresh_credentials(
            client=_client(),
            token=_token(),
            metadata=metadata,
            now=issued + timedelta(minutes=5),
            refresher=refresher,
        )
    assert "connection refused" in str(exc_info.value)


def test_refresh_credentials_propagates_other_google_auth_errors_unchanged() -> None:
    """A `GoogleAuthError` subclass other than Revoked passes through verbatim."""

    issued = datetime(2026, 5, 14, tzinfo=UTC)
    metadata = _metadata(issued_at=issued, last_refresh_at=issued)

    def refresher(client: OAuthClient, token: OAuthToken) -> tuple[str, str, datetime]:
        raise GoogleAuthNetworkError("transient")

    with pytest.raises(GoogleAuthNetworkError, match="transient"):
        refresh_credentials(
            client=_client(),
            token=_token(),
            metadata=metadata,
            now=issued + timedelta(minutes=5),
            refresher=refresher,
        )
