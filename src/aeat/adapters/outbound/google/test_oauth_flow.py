"""Tests for the Google OAuth Desktop login flow."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from aeat.adapters.outbound.google._errors import (
    GoogleAuthScopeInsufficientError,
    GoogleAuthUnsecuredModeRefusedError,
)
from aeat.adapters.outbound.google._oauth_flow import (
    check_unsecured_mode_safety,
    credentials_to_records,
    run_login_flow,
)
from aeat.adapters.outbound.google._records import (
    DRIVE_FILE_SCOPE,
    REQUIRED_SCOPES,
    SHEETS_SCOPE,
    OAuthClient,
)
from aeat.core.config import SecretStoreBackend, Settings

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]


def _client() -> OAuthClient:
    return OAuthClient(
        client_id="1234.apps.googleusercontent.com",
        client_secret="GOCSPX-deadbeef",
        project_id="test-project-12345",
        auth_uri="https://accounts.google.com/o/oauth2/auth",
        token_uri="https://oauth2.googleapis.com/token",
        auth_provider_x509_cert_url="https://www.googleapis.com/oauth2/v1/certs",
        redirect_uris=("http://localhost",),
    )


def _patch_settings(monkeypatch: pytest.MonkeyPatch, backend: SecretStoreBackend) -> None:
    base_settings = Settings()
    settings = base_settings.model_copy(update={"aeat_secret_store_backend": backend})
    monkeypatch.setattr(
        "aeat.adapters.outbound.google._oauth_flow.load_settings",
        lambda: settings,
    )


def test_credentials_to_records_round_trip() -> None:
    issued = datetime(2026, 5, 14, 10, 0, tzinfo=UTC)
    token, metadata = credentials_to_records(
        refresh_token="1//deadbeef",
        token_uri="https://oauth2.googleapis.com/token",
        account_email="operator@example.com",
        granted_scopes=REQUIRED_SCOPES,
        issued_at=issued,
    )
    assert token.refresh_token == "1//deadbeef"
    assert metadata.account_email == "operator@example.com"
    assert metadata.issued_at == issued
    assert metadata.last_refresh_at == issued
    assert metadata.reauth_required is False
    assert metadata.granted_scopes == REQUIRED_SCOPES


def test_credentials_to_records_rejects_missing_drive_scope() -> None:
    with pytest.raises(GoogleAuthScopeInsufficientError) as exc_info:
        credentials_to_records(
            refresh_token="1//x",
            token_uri="https://oauth2.googleapis.com/token",
            account_email="operator@example.com",
            granted_scopes=(SHEETS_SCOPE,),
            issued_at=datetime(2026, 5, 14, tzinfo=UTC),
        )
    assert exc_info.value.code.code == "AUTH_GOOGLE_SCOPE_INSUFFICIENT"
    assert exc_info.value.context is not None
    assert exc_info.value.context["missing_scopes"] == [DRIVE_FILE_SCOPE]


def test_credentials_to_records_rejects_missing_sheets_scope() -> None:
    with pytest.raises(GoogleAuthScopeInsufficientError):
        credentials_to_records(
            refresh_token="1//x",
            token_uri="https://oauth2.googleapis.com/token",
            account_email="operator@example.com",
            granted_scopes=(DRIVE_FILE_SCOPE,),
            issued_at=datetime(2026, 5, 14, tzinfo=UTC),
        )


def test_credentials_to_records_refuses_empty_account_email() -> None:
    """Account email is required by `OAuthMetadata`'s min-length=1."""

    with pytest.raises(ValidationError):
        credentials_to_records(
            refresh_token="1//x",
            token_uri="https://oauth2.googleapis.com/token",
            account_email="",
            granted_scopes=REQUIRED_SCOPES,
            issued_at=datetime(2026, 5, 14, tzinfo=UTC),
        )


def test_check_unsecured_mode_safety_passes_when_backend_is_keyring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_settings(monkeypatch, SecretStoreBackend.KEYRING)
    check_unsecured_mode_safety("primary", "12345678Z")  # no exception (keyring backend)


def test_check_unsecured_mode_safety_passes_when_unsecured_with_empty_tax_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_settings(monkeypatch, SecretStoreBackend.UNSECURED)
    check_unsecured_mode_safety("primary", "")  # no tax id to check


def test_check_unsecured_mode_safety_passes_when_unsecured_with_synthetic_nif(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Synthetic test NIFs (per `_SYNTHETIC_TAX_IDS`) are allowed under unsecured."""

    _patch_settings(monkeypatch, SecretStoreBackend.UNSECURED)
    check_unsecured_mode_safety("test", "00000000T")  # synthetic placeholder


def test_check_unsecured_mode_safety_refuses_unsecured_with_real_nif(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`12345678Z` validates as a real NIF per Hacienda checksum."""

    _patch_settings(monkeypatch, SecretStoreBackend.UNSECURED)
    with pytest.raises(GoogleAuthUnsecuredModeRefusedError) as exc_info:
        check_unsecured_mode_safety("real", "12345678Z")
    assert exc_info.value.code.code == "REFUSED_GOOGLE_UNSECURED_MODE"
    assert exc_info.value.context == {"profile": "real", "backend": "unsecured"}


def test_run_login_flow_uses_injected_runner_and_clock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The `flow_runner` + `clock` seams cover the success path without network IO."""

    _patch_settings(monkeypatch, SecretStoreBackend.KEYRING)
    monkeypatch.setattr(
        "aeat.adapters.outbound.google._oauth_flow.resolve_active_tax_id",
        lambda profile: "",
    )

    issued = datetime(2026, 5, 14, 11, 0, tzinfo=UTC)
    captured: dict[str, Any] = {}

    def runner(client: OAuthClient) -> tuple[str, str, str, tuple[str, ...]]:
        captured["client_id"] = client.client_id
        return ("1//refreshXYZ", client.token_uri, "operator@example.com", REQUIRED_SCOPES)

    token, metadata = run_login_flow(
        _client(),
        "primary",
        flow_runner=runner,
        clock=lambda: issued,
    )

    assert captured["client_id"] == "1234.apps.googleusercontent.com"
    assert token.refresh_token == "1//refreshXYZ"
    assert metadata.account_email == "operator@example.com"
    assert metadata.issued_at == issued
    assert metadata.last_refresh_at == issued


def test_run_login_flow_runs_unsecured_check_before_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The runner must NOT execute when unsecured-mode safety refuses."""

    _patch_settings(monkeypatch, SecretStoreBackend.UNSECURED)
    monkeypatch.setattr(
        "aeat.adapters.outbound.google._oauth_flow.resolve_active_tax_id",
        lambda profile: "12345678Z",
    )

    runner_calls: list[OAuthClient] = []

    def runner(client: OAuthClient) -> tuple[str, str, str, tuple[str, ...]]:
        runner_calls.append(client)
        return ("x", "x", "x", REQUIRED_SCOPES)

    with pytest.raises(GoogleAuthUnsecuredModeRefusedError):
        run_login_flow(_client(), "real", flow_runner=runner, clock=lambda: datetime(2026, 5, 14, tzinfo=UTC))

    assert runner_calls == [], "flow_runner must not be called when unsecured-mode safety refuses"


def test_run_login_flow_propagates_scope_insufficient_from_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Partial-scope grants from the consent screen surface as `GoogleAuthScopeInsufficientError`."""

    _patch_settings(monkeypatch, SecretStoreBackend.KEYRING)
    monkeypatch.setattr(
        "aeat.adapters.outbound.google._oauth_flow.resolve_active_tax_id",
        lambda profile: "",
    )

    def runner(client: OAuthClient) -> tuple[str, str, str, tuple[str, ...]]:
        return ("1//x", client.token_uri, "operator@example.com", (SHEETS_SCOPE,))

    with pytest.raises(GoogleAuthScopeInsufficientError):
        run_login_flow(
            _client(),
            "primary",
            flow_runner=runner,
            clock=lambda: datetime(2026, 5, 14, tzinfo=UTC),
        )
