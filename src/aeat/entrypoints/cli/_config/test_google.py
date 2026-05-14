"""Tests for `aeat config google ...` Typer commands.

Exercises the four CLI commands end-to-end through Typer's `CliRunner`
with the OAuth backend's session store stubbed via monkeypatch. The
heavyweight integration paths (real loopback HTTP receiver, real Drive
API calls) live in the live-gated test module.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.adapters.outbound.google._records import REQUIRED_SCOPES, OAuthClient, OAuthMetadata, OAuthToken
from aeat.entrypoints.cli._config._google import google_app

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]


_RUNNER = CliRunner()


def _client_json_payload() -> dict[str, dict[str, object]]:
    return {
        "installed": {
            "client_id": "1234.apps.googleusercontent.com",
            "client_secret": "GOCSPX-fake",
            "project_id": "test-project-12345",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "redirect_uris": ["http://localhost"],
        }
    }


def _valid_metadata() -> OAuthMetadata:
    issued = datetime(2026, 5, 14, 10, 0, tzinfo=UTC)
    return OAuthMetadata(
        account_email="operator@example.com",
        granted_scopes=REQUIRED_SCOPES,
        issued_at=issued,
        last_refresh_at=issued,
    )


@pytest.fixture
def stub_session_store(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Replace `_session_store` calls with an in-memory map."""

    state: dict[str, object] = {"clients": {}, "tokens": {}, "metadata": {}}

    def save_client(profile: str, client: OAuthClient) -> None:
        state["clients"][profile] = client  # type: ignore[index]

    def load_client(profile: str) -> OAuthClient | None:
        return state["clients"].get(profile)  # type: ignore[union-attr]

    def save_token(profile: str, token: OAuthToken) -> None:
        state["tokens"][profile] = token  # type: ignore[index]

    def save_metadata(profile: str, metadata: OAuthMetadata) -> None:
        state["metadata"][profile] = metadata  # type: ignore[index]

    def load_metadata(profile: str) -> OAuthMetadata | None:
        return state["metadata"].get(profile)  # type: ignore[union-attr]

    def delete_session(profile: str) -> tuple[bool, bool]:
        token_present = profile in state["tokens"]  # type: ignore[operator]
        metadata_present = profile in state["metadata"]  # type: ignore[operator]
        state["tokens"].pop(profile, None)  # type: ignore[union-attr]
        state["metadata"].pop(profile, None)  # type: ignore[union-attr]
        return token_present, metadata_present

    monkeypatch.setattr("aeat.entrypoints.cli._config._google.save_client", save_client)
    monkeypatch.setattr("aeat.entrypoints.cli._config._google.load_client", load_client)
    monkeypatch.setattr("aeat.entrypoints.cli._config._google.save_token", save_token)
    monkeypatch.setattr("aeat.entrypoints.cli._config._google.save_metadata", save_metadata)
    monkeypatch.setattr("aeat.entrypoints.cli._config._google.load_metadata", load_metadata)
    monkeypatch.setattr("aeat.entrypoints.cli._config._google.delete_session", delete_session)
    return state


@pytest.fixture
def stub_profile_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    """Resolve profile from `--profile` override or fall back to a default."""

    def resolver(profile_override: str | None = None) -> str:
        override = (profile_override or "").strip()
        return override if override else "default"

    monkeypatch.setattr("aeat.entrypoints.cli._config._google.resolve_active_profile", resolver)


def test_register_persists_oauth_client(
    tmp_path: Path,
    stub_session_store: dict[str, object],
    stub_profile_binding: None,
) -> None:
    payload_path = tmp_path / "client.json"
    payload_path.write_text(json.dumps(_client_json_payload()), encoding="utf-8")

    result = _RUNNER.invoke(google_app, ["register", "--client-json", str(payload_path), "--profile", "primary"])

    assert result.exit_code == 0, result.stdout
    persisted = stub_session_store["clients"]["primary"]  # type: ignore[index]
    assert isinstance(persisted, OAuthClient)
    assert persisted.client_id == "1234.apps.googleusercontent.com"


def test_register_rejects_web_application_shape(
    tmp_path: Path,
    stub_session_store: dict[str, object],
    stub_profile_binding: None,
) -> None:
    """A `{"web": {...}}` Cloud Console payload must surface a refusal."""

    payload_path = tmp_path / "web_client.json"
    payload_path.write_text(json.dumps({"web": _client_json_payload()["installed"]}), encoding="utf-8")

    result = _RUNNER.invoke(google_app, ["register", "--client-json", str(payload_path)])

    assert result.exit_code != 0
    assert stub_session_store["clients"] == {}  # type: ignore[comparison-overlap]


def test_register_rejects_non_json_input(
    tmp_path: Path,
    stub_session_store: dict[str, object],
    stub_profile_binding: None,
) -> None:
    payload_path = tmp_path / "junk.json"
    payload_path.write_text("not json", encoding="utf-8")

    result = _RUNNER.invoke(google_app, ["register", "--client-json", str(payload_path)])

    assert result.exit_code != 0


def test_login_refuses_when_no_client_registered(
    stub_session_store: dict[str, object],
    stub_profile_binding: None,
) -> None:
    result = _RUNNER.invoke(google_app, ["login", "--profile", "primary"])

    assert result.exit_code != 0
    assert "no OAuth client registered" in result.stdout or "no OAuth client registered" in result.stderr


def test_login_refresh_only_refuses_when_no_metadata_present(
    stub_session_store: dict[str, object],
    stub_profile_binding: None,
) -> None:
    stub_session_store["clients"]["primary"] = OAuthClient.model_validate({**_client_json_payload()["installed"], "redirect_uris": ("http://localhost",)})  # type: ignore[index]

    result = _RUNNER.invoke(google_app, ["login", "--profile", "primary", "--refresh-only"])

    assert result.exit_code != 0


def test_login_refresh_only_returns_existing_session_summary(
    stub_session_store: dict[str, object],
    stub_profile_binding: None,
) -> None:
    stub_session_store["clients"]["primary"] = OAuthClient.model_validate({**_client_json_payload()["installed"], "redirect_uris": ("http://localhost",)})  # type: ignore[index]
    stub_session_store["metadata"]["primary"] = _valid_metadata()  # type: ignore[index]

    result = _RUNNER.invoke(google_app, ["login", "--profile", "primary", "--refresh-only"])

    assert result.exit_code == 0, result.stdout
    assert "operator@example.com" in result.stdout
    assert "mode\trefresh-only" in result.stdout


def test_login_runs_consent_flow_when_runner_is_stubbed(
    monkeypatch: pytest.MonkeyPatch,
    stub_session_store: dict[str, object],
    stub_profile_binding: None,
) -> None:
    """The CLI orchestrates client load → flow runner → token + metadata save."""

    stub_session_store["clients"]["primary"] = OAuthClient.model_validate({**_client_json_payload()["installed"], "redirect_uris": ("http://localhost",)})  # type: ignore[index]

    issued = datetime(2026, 5, 14, 11, 0, tzinfo=UTC)
    metadata = _valid_metadata().model_copy(update={"issued_at": issued, "last_refresh_at": issued})
    token = OAuthToken(refresh_token="1//refresh-NEW", token_uri="https://oauth2.googleapis.com/token")

    def stub_login_flow(client: OAuthClient, profile: str) -> tuple[OAuthToken, OAuthMetadata]:
        assert profile == "primary"
        assert client.client_id == "1234.apps.googleusercontent.com"
        return token, metadata

    monkeypatch.setattr("aeat.entrypoints.cli._config._google.run_login_flow", stub_login_flow)

    result = _RUNNER.invoke(google_app, ["login", "--profile", "primary"])

    assert result.exit_code == 0, result.stdout
    assert stub_session_store["tokens"]["primary"] == token  # type: ignore[index]
    assert stub_session_store["metadata"]["primary"].account_email == "operator@example.com"  # type: ignore[union-attr]
    assert "mode\tconsent" in result.stdout


def test_status_reports_absence_cleanly(
    stub_session_store: dict[str, object],
    stub_profile_binding: None,
) -> None:
    result = _RUNNER.invoke(google_app, ["status", "--profile", "primary"])

    assert result.exit_code == 0, result.stdout
    assert "client_registered\tFalse" in result.stdout
    assert "session_present\tFalse" in result.stdout


def test_status_reports_full_session_state(
    stub_session_store: dict[str, object],
    stub_profile_binding: None,
) -> None:
    stub_session_store["clients"]["primary"] = OAuthClient.model_validate({**_client_json_payload()["installed"], "redirect_uris": ("http://localhost",)})  # type: ignore[index]
    stub_session_store["metadata"]["primary"] = _valid_metadata()  # type: ignore[index]

    result = _RUNNER.invoke(google_app, ["status", "--profile", "primary"])

    assert result.exit_code == 0, result.stdout
    assert "operator@example.com" in result.stdout
    assert "client_registered\tTrue" in result.stdout
    assert "session_present\tTrue" in result.stdout
    assert "reauth_required\tFalse" in result.stdout


def test_logout_clears_token_and_metadata_but_preserves_client(
    stub_session_store: dict[str, object],
    stub_profile_binding: None,
) -> None:
    client = OAuthClient.model_validate({**_client_json_payload()["installed"], "redirect_uris": ("http://localhost",)})
    stub_session_store["clients"]["primary"] = client  # type: ignore[index]
    stub_session_store["tokens"]["primary"] = OAuthToken(  # type: ignore[index]
        refresh_token="1//refresh", token_uri="https://oauth2.googleapis.com/token"
    )
    stub_session_store["metadata"]["primary"] = _valid_metadata()  # type: ignore[index]

    result = _RUNNER.invoke(google_app, ["logout", "--profile", "primary"])

    assert result.exit_code == 0, result.stdout
    assert "primary" not in stub_session_store["tokens"]  # type: ignore[operator]
    assert "primary" not in stub_session_store["metadata"]  # type: ignore[operator]
    assert stub_session_store["clients"]["primary"] == client  # type: ignore[index]
    assert "client_preserved\tTrue" in result.stdout
